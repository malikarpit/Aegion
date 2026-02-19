"""
Aegion Formal State Machine Definitions.

Doctrine: "State transitions are explicit. Invalid transitions are hard failures."

Defines state machines for all critical lifecycles:
- Proposal: draft → pending → approved/rejected → superseded
- Decision: proposed → approved → active → superseded/revoked
- Session: initializing → active → paused → terminated
- Incident: triggered → investigating → mitigating → resolved/escalated
- Pipeline: created → running → completed/failed/cancelled

Invalid transitions raise StateTransitionError.
"""

from enum import Enum
from typing import Dict, Set, Optional, Callable, Any
from datetime import datetime, timezone

from ..core.logging import logger


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, entity_type: str, entity_id: str, current: str, target: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.current_state = current
        self.target_state = target
        super().__init__(
            f"Invalid {entity_type} transition: '{current}' → '{target}' "
            f"for {entity_id}"
        )


class StateMachine:
    """
    Generic state machine with configurable transitions and guards.

    Usage:
        sm = StateMachine(
            name="Proposal",
            transitions={
                "draft":    {"pending"},
                "pending":  {"approved", "rejected"},
                "approved": {"superseded"},
                "rejected": set(),
                "superseded": set(),
            },
        )
        sm.transition("proposal-123", "draft", "pending")  # OK
        sm.transition("proposal-123", "draft", "approved")  # StateTransitionError!
    """

    def __init__(
        self,
        name: str,
        transitions: Dict[str, Set[str]],
        terminal_states: Optional[Set[str]] = None,
    ):
        self.name = name
        self._transitions = transitions
        self._terminal_states = terminal_states or {
            state for state, targets in transitions.items() if not targets
        }
        self._guards: Dict[str, Callable] = {}

    @property
    def all_states(self) -> Set[str]:
        """All defined states."""
        states = set(self._transitions.keys())
        for targets in self._transitions.values():
            states.update(targets)
        return states

    @property
    def terminal_states(self) -> Set[str]:
        """States with no outgoing transitions."""
        return self._terminal_states

    def is_terminal(self, state: str) -> bool:
        """Check if a state is terminal (no further transitions possible)."""
        return state in self._terminal_states

    def valid_transitions(self, current_state: str) -> Set[str]:
        """Get the set of valid target states from the current state."""
        return self._transitions.get(current_state, set())

    def can_transition(self, current_state: str, target_state: str) -> bool:
        """Check if a transition is valid without executing it."""
        return target_state in self._transitions.get(current_state, set())

    def add_guard(self, transition_key: str, guard: Callable[[str, str], bool]):
        """
        Add a guard function for a specific transition.

        Guard receives (entity_id, context) and must return True to allow.
        transition_key format: "from_state→to_state"
        """
        self._guards[transition_key] = guard

    def transition(
        self,
        entity_id: str,
        current_state: str,
        target_state: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Execute a state transition.

        Returns the new state if valid.
        Raises StateTransitionError if invalid.
        """
        # Check if transition is defined
        if not self.can_transition(current_state, target_state):
            raise StateTransitionError(
                entity_type=self.name,
                entity_id=entity_id,
                current=current_state,
                target=target_state,
            )

        # Check guards
        guard_key = f"{current_state}→{target_state}"
        guard = self._guards.get(guard_key)
        if guard and not guard(entity_id, context or {}):
            raise StateTransitionError(
                entity_type=f"{self.name}(guard)",
                entity_id=entity_id,
                current=current_state,
                target=target_state,
            )

        # Log transition
        logger.info(
            f"{self.name} state transition",
            entity_id=entity_id,
            from_state=current_state,
            to_state=target_state,
        )

        return target_state


# ──────────────────────────────────────────────────────────────────────────
# Predefined State Machines
# ──────────────────────────────────────────────────────────────────────────


class ProposalState(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


PROPOSAL_LIFECYCLE = StateMachine(
    name="Proposal",
    transitions={
        "draft":      {"pending"},
        "pending":    {"approved", "rejected"},
        "approved":   {"superseded"},
        "rejected":   set(),            # Terminal
        "superseded": set(),            # Terminal
    },
)


class DecisionState(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"


DECISION_LIFECYCLE = StateMachine(
    name="Decision",
    transitions={
        "proposed":   {"approved", "rejected"},
        "approved":   {"active", "revoked"},
        "active":     {"superseded", "revoked"},
        "rejected":   set(),            # Terminal
        "superseded": set(),            # Terminal
        "revoked":    set(),            # Terminal
    },
)


class SessionState(str, Enum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    TERMINATED = "terminated"


SESSION_LIFECYCLE = StateMachine(
    name="Session",
    transitions={
        "initializing": {"active", "terminated"},
        "active":       {"paused", "terminated"},
        "paused":       {"active", "terminated"},
        "terminated":   set(),          # Terminal
    },
)


class IncidentState(str, Enum):
    TRIGGERED = "triggered"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


INCIDENT_LIFECYCLE = StateMachine(
    name="Incident",
    transitions={
        "triggered":     {"investigating", "escalated"},
        "investigating": {"mitigating", "resolved", "escalated"},
        "mitigating":    {"resolved", "escalated"},
        "resolved":      set(),          # Terminal
        "escalated":     {"investigating", "mitigating", "resolved"},
    },
)


class PipelineState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


PIPELINE_LIFECYCLE = StateMachine(
    name="Pipeline",
    transitions={
        "created":   {"running", "cancelled"},
        "running":   {"completed", "failed", "cancelled"},
        "completed": set(),             # Terminal
        "failed":    {"created"},       # Retry
        "cancelled": set(),             # Terminal
    },
)


class ADRState(str, Enum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


ADR_LIFECYCLE = StateMachine(
    name="ADR",
    transitions={
        "draft":       {"proposed"},
        "proposed":    {"accepted", "deprecated"},
        "accepted":    {"deprecated", "superseded"},
        "deprecated":  set(),           # Terminal
        "superseded":  set(),           # Terminal
    },
)


# ──────────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────────

LIFECYCLE_REGISTRY: Dict[str, StateMachine] = {
    "proposal": PROPOSAL_LIFECYCLE,
    "decision": DECISION_LIFECYCLE,
    "session":  SESSION_LIFECYCLE,
    "incident": INCIDENT_LIFECYCLE,
    "pipeline": PIPELINE_LIFECYCLE,
    "adr":      ADR_LIFECYCLE,
}


def get_lifecycle(entity_type: str) -> StateMachine:
    """Get a lifecycle state machine by entity type."""
    sm = LIFECYCLE_REGISTRY.get(entity_type)
    if not sm:
        raise ValueError(f"Unknown lifecycle type: {entity_type}")
    return sm
