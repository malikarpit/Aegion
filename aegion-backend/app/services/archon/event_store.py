"""
Aegion Event Store — Append-Only Event Sourcing.

Doctrine: "State is a projection. Events are the truth."

Provides:
- Append-only event store with sequential ordering
- Domain event types for all governance operations
- Event replay: rebuild state from any point in the event log
- Point-in-time recovery for Chronos time-travel queries
- Snapshot support for efficient replay from recent checkpoints
"""

import uuid
import json
import hashlib
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import defaultdict

from ...core.logging import logger
from ...core.time import TimeAuthority


# ────────────────────────────────────────────────
# Domain Event Types
# ────────────────────────────────────────────────


class DomainEventType(str, Enum):
    """All domain events in the Aegion system."""
    # Proposal lifecycle
    PROPOSAL_CREATED = "proposal.created"
    PROPOSAL_UPDATED = "proposal.updated"
    PROPOSAL_WITHDRAWN = "proposal.withdrawn"

    # Decision lifecycle
    DECISION_APPROVED = "decision.approved"
    DECISION_REJECTED = "decision.rejected"
    DECISION_SUPERSEDED = "decision.superseded"
    DECISION_EXPIRED = "decision.expired"

    # Evidence lifecycle
    EVIDENCE_SUBMITTED = "evidence.submitted"
    EVIDENCE_CLASSIFIED = "evidence.classified"
    EVIDENCE_REVOKED = "evidence.revoked"
    EVIDENCE_STALE = "evidence.marked_stale"

    # Governance
    FREEZE_ACTIVATED = "governance.freeze_activated"
    FREEZE_DEACTIVATED = "governance.freeze_deactivated"
    POLICY_UPDATED = "governance.policy_updated"
    INVARIANT_VIOLATED = "governance.invariant_violated"
    TIER_ESCALATED = "governance.tier_escalated"

    # Graph
    NODE_CREATED = "graph.node_created"
    NODE_UPDATED = "graph.node_updated"
    EDGE_CREATED = "graph.edge_created"
    EDGE_REMOVED = "graph.edge_removed"

    # System
    SNAPSHOT_CREATED = "system.snapshot_created"
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"


# ────────────────────────────────────────────────
# Domain Event
# ────────────────────────────────────────────────


@dataclass(frozen=True)
class DomainEvent:
    """
    Immutable domain event — the fundamental unit of truth.

    Each event captures:
    - What happened (event_type)
    - When it happened (timestamp, sequence)
    - Who caused it (actor_id)
    - What was affected (aggregate_type, aggregate_id)
    - The complete data (payload)
    - Causal chain (causation_id, correlation_id)
    """
    event_id: str
    event_type: DomainEventType
    timestamp: datetime
    sequence: int                    # Global monotonic sequence number
    aggregate_type: str              # e.g., "proposal", "decision", "evidence"
    aggregate_id: str                # ID of the affected entity
    payload: Dict[str, Any]          # Full event data
    actor_id: str = ""               # Who triggered this
    workspace_id: str = ""           # Workspace context
    causation_id: Optional[str] = None    # Event that caused this
    correlation_id: Optional[str] = None  # Top-level operation ID
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_hash: Optional[str] = None      # SHA-256 of canonical content

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "payload": self.payload,
            "actor_id": self.actor_id,
            "workspace_id": self.workspace_id,
            "causation_id": self.causation_id,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
            "event_hash": self.event_hash,
        }


def _compute_event_hash(event: DomainEvent) -> str:
    """Compute SHA-256 hash of event's canonical content."""
    canonical = json.dumps({
        "event_type": event.event_type.value,
        "timestamp": event.timestamp.isoformat(),
        "sequence": event.sequence,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "payload": event.payload,
        "actor_id": event.actor_id,
    }, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ────────────────────────────────────────────────
# Aggregate Snapshot
# ────────────────────────────────────────────────


@dataclass
class AggregateSnapshot:
    """
    Snapshot of an aggregate's state at a specific point in time.

    Used to optimize replay — start from snapshot instead of genesis.
    """
    aggregate_type: str
    aggregate_id: str
    state: Dict[str, Any]
    at_sequence: int
    at_timestamp: datetime
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "state": self.state,
            "at_sequence": self.at_sequence,
            "at_timestamp": self.at_timestamp.isoformat(),
        }


# ────────────────────────────────────────────────
# Event Store
# ────────────────────────────────────────────────


class EventStore:
    """
    Append-only event store with sequential ordering.

    Core guarantee: events are strictly ordered by sequence number.
    Once appended, events are immutable and permanent.

    Usage:
        store = EventStore()
        event = store.append(
            event_type=DomainEventType.PROPOSAL_CREATED,
            aggregate_type="proposal",
            aggregate_id="prop-123",
            payload={"title": "Refactor auth", "tier": "T1"},
            actor_id="user-456",
        )
        # Replay all proposal events
        events = store.get_events_for_aggregate("proposal", "prop-123")

        # Time-travel: get state at a specific point
        events = store.get_events_before(some_timestamp)
    """

    def __init__(self):
        self._events: List[DomainEvent] = []
        self._sequence: int = 0
        self._snapshots: Dict[str, AggregateSnapshot] = {}  # key = "type:id"
        self._projections: Dict[str, Callable] = {}          # name -> projection fn
        self._index_by_aggregate: Dict[str, List[int]] = defaultdict(list)
        self._index_by_type: Dict[str, List[int]] = defaultdict(list)
        self._index_by_correlation: Dict[str, List[int]] = defaultdict(list)

    # ── Append ───────────────────────────────────

    def append(
        self,
        event_type: DomainEventType,
        aggregate_type: str,
        aggregate_id: str,
        payload: Dict[str, Any],
        actor_id: str = "",
        workspace_id: str = "",
        causation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DomainEvent:
        """
        Append a new event to the store.

        Returns the sealed, immutable DomainEvent with sequence and hash assigned.
        """
        self._sequence += 1
        now = TimeAuthority.now()

        event = DomainEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=now.utc_iso if hasattr(now, 'utc_iso') else datetime.now(timezone.utc),
            sequence=self._sequence,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            actor_id=actor_id,
            workspace_id=workspace_id,
            causation_id=causation_id,
            correlation_id=correlation_id or str(uuid.uuid4()),
            metadata=metadata or {},
        )

        # Compute integrity hash
        event = DomainEvent(
            **{**event.__dict__, "event_hash": _compute_event_hash(event)}
        )

        # Store
        idx = len(self._events)
        self._events.append(event)

        # Index
        agg_key = f"{aggregate_type}:{aggregate_id}"
        self._index_by_aggregate[agg_key].append(idx)
        self._index_by_type[event_type.value].append(idx)
        if event.correlation_id:
            self._index_by_correlation[event.correlation_id].append(idx)

        logger.debug(
            f"Event stored: seq={event.sequence} type={event.event_type.value} "
            f"aggregate={agg_key}"
        )

        # ── Persist to Supabase timeline_events (best-effort) ──
        try:
            from ...db.supabase_client import get_supabase_client
            get_supabase_client().table("timeline_events").insert({
                "workspace_id": event.workspace_id,
                "event_type": event.event_type.value,
                "title": f"{event.aggregate_type}.{event.event_type.value}",
                "actor": event.actor_id,
                "entity_id": event.aggregate_id,
                "entity_type": event.aggregate_type,
                "metadata": {
                    "event_id": event.event_id,
                    "sequence": event.sequence,
                    "payload": event.payload,
                    "causation_id": event.causation_id,
                    "correlation_id": event.correlation_id,
                    "event_hash": event.event_hash,
                },
            }).execute()
        except Exception as exc:
            logger.warning(f"Event persistence to timeline_events failed (non-fatal): {exc}")

        return event

    # ── Queries ───────────────────────────────────

    def get_events_for_aggregate(
        self,
        aggregate_type: str,
        aggregate_id: str,
        after_sequence: int = 0,
    ) -> List[DomainEvent]:
        """Get all events for an aggregate, optionally after a sequence number."""
        key = f"{aggregate_type}:{aggregate_id}"
        indices = self._index_by_aggregate.get(key, [])
        return [
            self._events[i] for i in indices
            if self._events[i].sequence > after_sequence
        ]

    def get_events_by_type(
        self, event_type: DomainEventType
    ) -> List[DomainEvent]:
        """Get all events of a specific type."""
        indices = self._index_by_type.get(event_type.value, [])
        return [self._events[i] for i in indices]

    def get_events_by_correlation(
        self, correlation_id: str
    ) -> List[DomainEvent]:
        """Get all events in a causal chain (same correlation ID)."""
        indices = self._index_by_correlation.get(correlation_id, [])
        return [self._events[i] for i in indices]

    def get_events_before(
        self, timestamp: datetime
    ) -> List[DomainEvent]:
        """Get all events before a timestamp (for time-travel)."""
        return [e for e in self._events if e.timestamp <= timestamp]

    def get_events_in_range(
        self,
        start_seq: int,
        end_seq: int,
    ) -> List[DomainEvent]:
        """Get events in a sequence range [start, end] inclusive."""
        return [
            e for e in self._events
            if start_seq <= e.sequence <= end_seq
        ]

    def get_all_events(self) -> List[DomainEvent]:
        """Get all events (full replay)."""
        return list(self._events)

    @property
    def current_sequence(self) -> int:
        return self._sequence

    @property
    def event_count(self) -> int:
        return len(self._events)

    # ── Replay / Projection ──────────────────────

    def replay(
        self,
        aggregate_type: str,
        aggregate_id: str,
        projection_fn: Callable[[Dict[str, Any], DomainEvent], Dict[str, Any]],
        initial_state: Optional[Dict[str, Any]] = None,
        up_to_sequence: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Rebuild aggregate state by replaying events through a projection function.

        Args:
            aggregate_type: Type of aggregate to replay
            aggregate_id: ID of the aggregate
            projection_fn: (state, event) -> new_state
            initial_state: Starting state (default: empty dict)
            up_to_sequence: Stop replay at this sequence (for time-travel)

        Returns:
            The projected state after all events are applied.
        """
        state = dict(initial_state or {})

        # Start from snapshot if available
        snap_key = f"{aggregate_type}:{aggregate_id}"
        snapshot = self._snapshots.get(snap_key)
        after_seq = 0

        if snapshot and (up_to_sequence is None or snapshot.at_sequence <= up_to_sequence):
            state = dict(snapshot.state)
            after_seq = snapshot.at_sequence

        # Get events after snapshot
        events = self.get_events_for_aggregate(
            aggregate_type, aggregate_id, after_sequence=after_seq
        )

        # Apply events
        for event in events:
            if up_to_sequence is not None and event.sequence > up_to_sequence:
                break
            state = projection_fn(state, event)

        return state

    def create_snapshot(
        self,
        aggregate_type: str,
        aggregate_id: str,
        state: Dict[str, Any],
    ) -> AggregateSnapshot:
        """Create a snapshot of current aggregate state for faster replay."""
        snap = AggregateSnapshot(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            state=state,
            at_sequence=self._sequence,
            at_timestamp=datetime.now(timezone.utc),
        )
        key = f"{aggregate_type}:{aggregate_id}"
        self._snapshots[key] = snap

        # Record snapshot as an event too
        self.append(
            event_type=DomainEventType.SNAPSHOT_CREATED,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload={"snapshot_id": snap.snapshot_id, "at_sequence": snap.at_sequence},
            actor_id="system",
        )

        logger.info(
            f"Snapshot created for {key} at sequence {snap.at_sequence}"
        )
        return snap

    # ── Point-in-Time Recovery ───────────────────

    def recover_state_at(
        self,
        aggregate_type: str,
        aggregate_id: str,
        timestamp: datetime,
        projection_fn: Callable[[Dict[str, Any], DomainEvent], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Recover aggregate state as it was at a specific timestamp.

        This is the Chronos time-travel mechanism: given any past
        timestamp, reconstruct exactly what the state looked like.
        """
        # Find the sequence number at this timestamp
        events_before = [
            e for e in self.get_events_for_aggregate(aggregate_type, aggregate_id)
            if e.timestamp <= timestamp
        ]

        if not events_before:
            return {}

        last_seq = events_before[-1].sequence

        return self.replay(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            projection_fn=projection_fn,
            up_to_sequence=last_seq,
        )

    # ── Integrity ────────────────────────────────

    def verify_integrity(self) -> Tuple[bool, List[str]]:
        """Check that all stored events have valid hashes."""
        errors = []
        for event in self._events:
            expected = _compute_event_hash(event)
            if event.event_hash and event.event_hash != expected:
                errors.append(
                    f"Hash mismatch for event {event.event_id} "
                    f"(seq={event.sequence}): expected {expected[:12]}, "
                    f"got {event.event_hash[:12]}"
                )
        return len(errors) == 0, errors

    # ── Export ────────────────────────────────────

    def export_events(
        self,
        start_seq: int = 1,
        end_seq: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Export events as serializable dicts."""
        end = end_seq or self._sequence
        return [
            e.to_dict() for e in self._events
            if start_seq <= e.sequence <= end
        ]

    def stats(self) -> Dict[str, Any]:
        """Get event store statistics."""
        type_counts: Dict[str, int] = defaultdict(int)
        for e in self._events:
            type_counts[e.event_type.value] += 1

        return {
            "total_events": len(self._events),
            "current_sequence": self._sequence,
            "snapshot_count": len(self._snapshots),
            "aggregate_count": len(self._index_by_aggregate),
            "event_type_distribution": dict(type_counts),
        }


# ────────────────────────────────────────────────
# Standard Projection Functions
# ────────────────────────────────────────────────

def proposal_projection(
    state: Dict[str, Any], event: DomainEvent
) -> Dict[str, Any]:
    """Standard projection for Proposal aggregates."""
    state = dict(state)

    if event.event_type == DomainEventType.PROPOSAL_CREATED:
        state.update({
            "id": event.aggregate_id,
            "status": "pending",
            "created_at": event.timestamp.isoformat(),
            "created_by": event.actor_id,
            **event.payload,
        })

    elif event.event_type == DomainEventType.DECISION_APPROVED:
        state["status"] = "approved"
        state["approved_at"] = event.timestamp.isoformat()
        state["approved_by"] = event.actor_id

    elif event.event_type == DomainEventType.DECISION_REJECTED:
        state["status"] = "rejected"
        state["rejected_at"] = event.timestamp.isoformat()
        state["rejected_by"] = event.actor_id

    elif event.event_type == DomainEventType.PROPOSAL_WITHDRAWN:
        state["status"] = "withdrawn"
        state["withdrawn_at"] = event.timestamp.isoformat()

    return state


def evidence_projection(
    state: Dict[str, Any], event: DomainEvent
) -> Dict[str, Any]:
    """Standard projection for Evidence aggregates."""
    state = dict(state)

    if event.event_type == DomainEventType.EVIDENCE_SUBMITTED:
        state.update({
            "id": event.aggregate_id,
            "status": "active",
            "submitted_at": event.timestamp.isoformat(),
            "submitted_by": event.actor_id,
            **event.payload,
        })

    elif event.event_type == DomainEventType.EVIDENCE_CLASSIFIED:
        state["classification"] = event.payload.get("classification")

    elif event.event_type == DomainEventType.EVIDENCE_REVOKED:
        state["status"] = "revoked"
        state["revoked_at"] = event.timestamp.isoformat()

    elif event.event_type == DomainEventType.EVIDENCE_STALE:
        state["status"] = "stale"
        state["stale_at"] = event.timestamp.isoformat()

    return state


# ────────────────────────────────────────────────
# Singleton
# ────────────────────────────────────────────────

_event_store: Optional[EventStore] = None


def get_event_store() -> EventStore:
    """Get the global EventStore singleton."""
    global _event_store
    if _event_store is None:
        _event_store = EventStore()
    return _event_store
