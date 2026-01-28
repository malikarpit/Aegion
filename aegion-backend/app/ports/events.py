"""
Aegion Events Port (Abstract Interface).

This is the hexagonal architecture PORT for event-driven messaging.
Implementations (adapters) include:
- InProcessEventBus (Phase 1-2): Synchronous, same process
- PubSubAdapter (Phase 3-4): Google Cloud Pub/Sub
- KafkaAdapter (Phase 5+): Apache Kafka for enterprise scale

Doctrine: Events are for cross-service communication.
All governance-critical events must be logged to AuditLog first.
"""

from abc import ABC, abstractmethod
from typing import Callable, Dict, Any, Optional, List
from enum import Enum
from pydantic import BaseModel
from datetime import datetime


class EventCategory(str, Enum):
    """Categories of events for routing."""
    SESSION = "session"
    DECISION = "decision"
    GOVERNANCE = "governance"
    AI = "ai"
    AUDIT = "audit"
    SYSTEM = "system"


class Event(BaseModel):
    """Base event structure."""
    event_id: str
    category: EventCategory
    event_type: str  # e.g., "session.started", "decision.approved"
    timestamp: datetime
    source: str  # Service that emitted the event
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = {}
    
    # Governance fields
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None
    actor_id: Optional[str] = None


# Alias for backward compatibility and clarity
EventMessage = Event


class EventHandler(ABC):
    """Base class for event handlers."""
    
    @abstractmethod
    async def handle(self, event: Event) -> None:
        """Handle an event. Must be idempotent."""
        pass
    
    @property
    @abstractmethod
    def event_types(self) -> List[str]:
        """Event types this handler subscribes to."""
        pass


class EventBusPort(ABC):
    """
    Abstract interface for event bus.
    Enables loose coupling between services.
    """
    
    @abstractmethod
    async def publish(self, event: Event) -> None:
        """
        Publish an event.
        Event is delivered to all registered handlers.
        """
        pass
    
    @abstractmethod
    async def subscribe(
        self, 
        event_type: str, 
        handler: Callable[[Event], None]
    ) -> str:
        """
        Subscribe to an event type.
        Returns subscription ID for unsubscribe.
        """
        pass
    
    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        pass
    
    @abstractmethod
    async def publish_batch(self, events: List[Event]) -> None:
        """Publish multiple events atomically."""
        pass


class TransactionalOutboxPort(ABC):
    """
    Transactional outbox pattern for reliable event publishing.
    Ensures events are published exactly-once even if service crashes.
    Phase 3+ for production reliability.
    """
    
    @abstractmethod
    async def enqueue(self, event: Event, transaction_id: str) -> None:
        """
        Enqueue event in outbox within a database transaction.
        Event is published only after transaction commits.
        """
        pass
    
    @abstractmethod
    async def process_pending(self) -> int:
        """
        Process pending events in outbox.
        Called by background worker.
        Returns number of events processed.
        """
        pass
    
    @abstractmethod
    async def mark_published(self, event_id: str) -> None:
        """Mark an event as successfully published."""
        pass


# Standard event types (for consistency)
class EventTypes:
    """Standard event type constants."""
    
    # Session events
    SESSION_STARTED = "session.started"
    SESSION_CLOSED = "session.closed"
    SESSION_DISTILLED = "session.distilled"
    
    # Decision events
    DECISION_PROPOSED = "decision.proposed"
    DECISION_APPROVED = "decision.approved"
    DECISION_REJECTED = "decision.rejected"
    DECISION_SUPERSEDED = "decision.superseded"
    
    # Governance events
    FREEZE_ACTIVATED = "governance.freeze_activated"
    FREEZE_DEACTIVATED = "governance.freeze_deactivated"
    POLICY_UPDATED = "governance.policy_updated"
    
    # AI events
    COUNCIL_INVOKED = "ai.council_invoked"
    COUNCIL_COMPLETED = "ai.council_completed"
    EVIDENCE_CLASSIFIED = "ai.evidence_classified"
    
    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    HEALTH_CHECK = "system.health_check"
