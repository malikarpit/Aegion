"""
Aegion In-Process Event Bus Adapter.

Implements EventBusPort for Phase 1-2 (single-process deployment).
Synchronous event delivery within the same process.

Migration path:
- Phase 3: Cloud Pub/Sub
- Phase 5: Apache Kafka
"""

from typing import Callable, Dict, List
import asyncio
from collections import defaultdict
import uuid

from ...ports.events import (
    EventBusPort,
    Event,
    EventCategory,
    EventTypes,
)
from ...core.logging import logger


class InProcessEventBus(EventBusPort):
    """
    In-memory event bus for Phase 1-2.
    Delivers events synchronously within the same process.
    """
    
    def __init__(self):
        self._handlers: Dict[str, List[tuple[str, Callable]]] = defaultdict(list)
        self._subscriptions: Dict[str, tuple[str, Callable]] = {}
    
    async def publish(self, event: Event) -> None:
        """Publish event to all matching handlers."""
        handlers = self._handlers.get(event.event_type, [])
        
        logger.debug(
            f"Publishing event {event.event_type} to {len(handlers)} handlers",
            event_id=event.event_id,
            event_type=event.event_type
        )
        
        for sub_id, handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(
                    f"Handler failed for event {event.event_id}: {e}",
                    event_id=event.event_id,
                    subscription_id=sub_id
                )
    
    async def subscribe(
        self, 
        event_type: str, 
        handler: Callable[[Event], None]
    ) -> str:
        """Subscribe to event type. Returns subscription ID."""
        sub_id = str(uuid.uuid4())
        
        self._handlers[event_type].append((sub_id, handler))
        self._subscriptions[sub_id] = (event_type, handler)
        
        logger.debug(
            f"Subscribed to {event_type}",
            subscription_id=sub_id
        )
        
        return sub_id
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        if subscription_id not in self._subscriptions:
            return False
        
        event_type, handler = self._subscriptions[subscription_id]
        self._handlers[event_type] = [
            (sid, h) for sid, h in self._handlers[event_type]
            if sid != subscription_id
        ]
        
        del self._subscriptions[subscription_id]
        return True
    
    async def publish_batch(self, events: List[Event]) -> None:
        """Publish multiple events."""
        for event in events:
            await self.publish(event)

    # ------------------------------------------------------------------
    # Transactional outbox convenience (P2-019)
    # ------------------------------------------------------------------

    def set_outbox(self, outbox) -> None:
        """Inject a TransactionalOutboxPort for critical-event delivery."""
        self._outbox = outbox

    async def publish_via_outbox(
        self, event: Event, transaction_id: str
    ) -> None:
        """
        Enqueue an event through the transactional outbox instead of
        publishing directly.  The OutboxWorker will relay it later.
        """
        if not hasattr(self, '_outbox') or self._outbox is None:
            # Fallback: no outbox configured, publish directly
            logger.warning(
                "No outbox configured, publishing event directly",
                event_id=event.event_id,
            )
            await self.publish(event)
            return

        await self._outbox.enqueue(event, transaction_id)


# Singleton instance for Phase 1
_event_bus: InProcessEventBus = None


def get_event_bus() -> InProcessEventBus:
    """Get the singleton event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = InProcessEventBus()
    return _event_bus
