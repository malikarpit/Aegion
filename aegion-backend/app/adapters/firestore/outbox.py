"""
Aegion Firestore Transactional Outbox Adapter .

Implements TransactionalOutboxPort for exactly-once-ish event publishing.

Doctrine: "Critical events survive crashes."

Flow:
1. Service calls enqueue() within its business transaction
2. Event is written to `event_outbox` Firestore collection with status=pending
3. Background OutboxWorker polls process_pending(), publishes via EventBusPort,
   then marks events as published

This avoids the dual-write problem where the DB commits but the event publish fails.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
import json

from ...ports.events import TransactionalOutboxPort, Event, EventCategory
from ...core.logging import logger


class FirestoreOutbox(TransactionalOutboxPort):
    """
    Firestore-backed transactional outbox.

    Collection: event_outbox
    Document schema:
        - event_id: str
        - event_type: str
        - payload: dict (serialised Event)
        - status: "pending" | "published" | "failed"
        - transaction_id: str
        - created_at: datetime
        - published_at: datetime | None
        - retry_count: int
        - last_error: str | None
    """

    COLLECTION = "event_outbox"
    MAX_RETRIES = 5

    def __init__(self, event_bus=None):
        """
        Args:
            event_bus: An EventBusPort instance used to actually publish events
                       during process_pending(). Injected to avoid circular deps.
        """
        self._event_bus = event_bus
        self._db = None

    @property
    def db(self):
        """Lazy Firestore client initialisation."""
        if self._db is None:
            from google.cloud import firestore
            self._db = firestore.AsyncClient()
        return self._db

    # ------------------------------------------------------------------
    # TransactionalOutboxPort interface
    # ------------------------------------------------------------------

    async def enqueue(self, event: Event, transaction_id: str) -> None:
        """
        Persist an event in the outbox with status 'pending'.

        Call this inside the same Firestore transaction as your business write
        so they commit atomically.
        """
        doc_ref = self.db.collection(self.COLLECTION).document(event.event_id)
        await doc_ref.set({
            "event_id": event.event_id,
            "event_type": event.event_type,
            "category": event.category.value,
            "payload": event.payload,
            "metadata": event.metadata,
            "source": event.source,
            "session_id": event.session_id,
            "workspace_id": event.workspace_id,
            "actor_id": event.actor_id,
            "transaction_id": transaction_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "published_at": None,
            "retry_count": 0,
            "last_error": None,
        })

        logger.debug(
            "Event enqueued in outbox",
            event_id=event.event_id,
            event_type=event.event_type,
            transaction_id=transaction_id,
        )

    async def process_pending(self) -> int:
        """
        Query pending events, publish them, and mark as published.

        Returns the count of successfully published events.
        """
        if self._event_bus is None:
            logger.warning("OutboxWorker: no event_bus configured, skipping")
            return 0

        query = (
            self.db.collection(self.COLLECTION)
            .where("status", "==", "pending")
            .where("retry_count", "<", self.MAX_RETRIES)
            .order_by("created_at")
            .limit(50)
        )

        docs = [doc async for doc in query.stream()]
        published = 0

        for doc in docs:
            data = doc.to_dict()
            event_id = data["event_id"]

            try:
                # Reconstruct Event
                event = Event(
                    event_id=event_id,
                    category=EventCategory(data["category"]),
                    event_type=data["event_type"],
                    timestamp=data["created_at"],
                    source=data.get("source", "outbox-relay"),
                    payload=data.get("payload", {}),
                    metadata=data.get("metadata", {}),
                    session_id=data.get("session_id"),
                    workspace_id=data.get("workspace_id"),
                    actor_id=data.get("actor_id"),
                )

                await self._event_bus.publish(event)
                await self.mark_published(event_id)
                published += 1

            except Exception as e:
                logger.error(
                    f"Outbox publish failed for {event_id}: {e}",
                    event_id=event_id,
                )
                # Increment retry count
                await doc.reference.update({
                    "retry_count": data.get("retry_count", 0) + 1,
                    "last_error": str(e),
                })

        if published > 0:
            logger.info(f"Outbox relay: published {published}/{len(docs)} events")

        return published

    async def mark_published(self, event_id: str) -> None:
        """Mark an event as successfully published."""
        doc_ref = self.db.collection(self.COLLECTION).document(event_id)
        await doc_ref.update({
            "status": "published",
            "published_at": datetime.now(timezone.utc),
        })
