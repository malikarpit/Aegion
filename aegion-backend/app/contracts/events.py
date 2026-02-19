"""
Aegion Event Streaming Hardening.

Doctrine: "Events are facts. Facts are versioned, ordered, and complete."

Provides:
- Versioned event schemas with schema registry
- Backpressure handling for slow consumers
- Idempotent event delivery with deduplication
- Stream reconnection support (Last-Event-ID)
"""

from typing import Optional, Dict, Any, Set, List, Type
from enum import Enum
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from collections import defaultdict
import asyncio

from ..core.logging import logger


# ──────────────────────────────────────────────────────────────────────────
# Event Versioning
# ──────────────────────────────────────────────────────────────────────────

class EventVersion(str, Enum):
    V1 = "1.0"
    V2 = "2.0"


class VersionedEvent(BaseModel):
    """Base class for versioned events."""
    event_id: str
    event_type: str
    version: str = EventVersion.V1
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    workspace_id: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────
# Schema Registry
# ──────────────────────────────────────────────────────────────────────────

class EventSchemaEntry(BaseModel):
    """Schema definition for an event type."""
    event_type: str
    version: str
    description: str
    payload_schema: Dict[str, str]  # field_name -> type description
    deprecated: bool = False


class EventSchemaRegistry:
    """
    Registry of known event schemas.

    Validates events against their registered schema.
    Tracks schema versions for backward compatibility.
    """

    def __init__(self):
        self._schemas: Dict[str, Dict[str, EventSchemaEntry]] = defaultdict(dict)

    def register(self, entry: EventSchemaEntry):
        """Register an event schema."""
        self._schemas[entry.event_type][entry.version] = entry

    def validate(self, event: VersionedEvent) -> bool:
        """Check if an event conforms to its registered schema."""
        versions = self._schemas.get(event.event_type)
        if not versions:
            return True  # Unknown event types pass (extensibility)

        schema = versions.get(event.version)
        if not schema:
            return True  # Unknown version passes

        # Check required fields exist in payload
        for field_name in schema.payload_schema:
            if field_name not in event.payload:
                logger.warning(
                    f"Event missing field {field_name}",
                    event_type=event.event_type,
                    version=event.version,
                )
                return False

        return True

    def list_schemas(self) -> List[EventSchemaEntry]:
        """List all registered schemas."""
        result = []
        for versions in self._schemas.values():
            result.extend(versions.values())
        return result


# Register core Aegion event schemas
_registry = EventSchemaRegistry()


def _register_core_schemas():
    """Register built-in Aegion event schemas."""
    schemas = [
        EventSchemaEntry(
            event_type="session.started",
            version="1.0",
            description="A new coding session was started",
            payload_schema={
                "session_id": "str",
                "workspace_id": "str",
                "user_id": "str",
            },
        ),
        EventSchemaEntry(
            event_type="proposal.created",
            version="1.0",
            description="A governance proposal was created",
            payload_schema={
                "proposal_id": "str",
                "title": "str",
                "tier": "str",
            },
        ),
        EventSchemaEntry(
            event_type="proposal.decided",
            version="1.0",
            description="A governance proposal was decided",
            payload_schema={
                "proposal_id": "str",
                "decision": "str",
                "decision_id": "str",
            },
        ),
        EventSchemaEntry(
            event_type="decision.superseded",
            version="1.0",
            description="A decision was superseded by a newer one",
            payload_schema={
                "original_decision_id": "str",
                "new_decision_id": "str",
            },
        ),
        EventSchemaEntry(
            event_type="evidence.recorded",
            version="1.0",
            description="Evidence was recorded in the knowledge graph",
            payload_schema={
                "evidence_id": "str",
                "evidence_type": "str",
            },
        ),
        EventSchemaEntry(
            event_type="incident.triggered",
            version="1.0",
            description="A governance incident was triggered",
            payload_schema={
                "incident_id": "str",
                "severity": "str",
                "trigger": "str",
            },
        ),
        EventSchemaEntry(
            event_type="freeze.activated",
            version="1.0",
            description="System freeze was activated",
            payload_schema={
                "freeze_id": "str",
                "reason": "str",
                "actor_id": "str",
            },
        ),
    ]
    for s in schemas:
        _registry.register(s)


_register_core_schemas()


def get_event_schema_registry() -> EventSchemaRegistry:
    return _registry


# ──────────────────────────────────────────────────────────────────────────
# Backpressure Handler
# ──────────────────────────────────────────────────────────────────────────

class BackpressureStrategy(str, Enum):
    DROP_OLDEST = "drop_oldest"     # Drop oldest events when full
    DROP_NEWEST = "drop_newest"     # Reject new events when full
    BLOCK = "block"                 # Block producer until space available


class BackpressureConfig(BaseModel):
    """Configuration for event queue backpressure."""
    max_queue_size: int = 1000
    strategy: BackpressureStrategy = BackpressureStrategy.DROP_OLDEST
    warn_threshold: float = 0.8  # Warn when queue is 80% full


class EventQueue:
    """
    Bounded event queue with configurable backpressure.

    Prevents slow consumers from causing unbounded memory growth.
    """

    def __init__(self, config: Optional[BackpressureConfig] = None):
        self.config = config or BackpressureConfig()
        self._queue: asyncio.Queue = asyncio.Queue(
            maxsize=self.config.max_queue_size
        )
        self._dropped_count: int = 0

    async def put(self, event: VersionedEvent) -> bool:
        """
        Add event to the queue with backpressure handling.

        Returns True if event was queued, False if dropped.
        """
        # Check warning threshold
        usage = self._queue.qsize() / self.config.max_queue_size
        if usage >= self.config.warn_threshold:
            logger.warning(
                "Event queue nearing capacity",
                usage_pct=f"{usage:.0%}",
                queue_size=self._queue.qsize(),
                max_size=self.config.max_queue_size,
            )

        if self._queue.full():
            if self.config.strategy == BackpressureStrategy.DROP_OLDEST:
                try:
                    self._queue.get_nowait()
                    self._dropped_count += 1
                except asyncio.QueueEmpty:
                    pass
            elif self.config.strategy == BackpressureStrategy.DROP_NEWEST:
                self._dropped_count += 1
                return False
            # BLOCK strategy: will block on put below

        try:
            if self.config.strategy == BackpressureStrategy.BLOCK:
                await asyncio.wait_for(self._queue.put(event), timeout=5.0)
            else:
                self._queue.put_nowait(event)
            return True
        except (asyncio.QueueFull, asyncio.TimeoutError):
            self._dropped_count += 1
            return False

    async def get(self, timeout: float = 30.0) -> Optional[VersionedEvent]:
        """Get next event from queue with timeout."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    @property
    def dropped_count(self) -> int:
        return self._dropped_count

    @property
    def size(self) -> int:
        return self._queue.qsize()


# ──────────────────────────────────────────────────────────────────────────
# Idempotency / Deduplication
# ──────────────────────────────────────────────────────────────────────────

class EventDeduplicator:
    """
    Tracks processed event IDs to prevent duplicate delivery.

    Uses a sliding window of recent event IDs.
    """

    def __init__(self, window_size: int = 10000):
        self._seen: Set[str] = set()
        self._ordered: List[str] = []
        self._window_size = window_size
        self._lock = asyncio.Lock()

    async def is_duplicate(self, event_id: str) -> bool:
        """Check if an event has already been processed."""
        async with self._lock:
            return event_id in self._seen

    async def mark_processed(self, event_id: str):
        """Record that an event has been processed."""
        async with self._lock:
            if event_id not in self._seen:
                self._seen.add(event_id)
                self._ordered.append(event_id)

                # Evict oldest entries beyond window
                while len(self._ordered) > self._window_size:
                    old_id = self._ordered.pop(0)
                    self._seen.discard(old_id)

    async def get_last_event_id(self) -> Optional[str]:
        """Get the most recently processed event ID (for reconnection)."""
        async with self._lock:
            return self._ordered[-1] if self._ordered else None
