"""
Aegion Audit Store Service.

Queryable structured audit log with replay capability.

Feature: Cloud task immutable audit trail + replay.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
import uuid

from ..core.logging import logger


class AuditAction(str, Enum):
    """Standard audit actions."""
    # Governance
    PROPOSAL_CREATED = "proposal_created"
    PROPOSAL_APPROVED = "proposal_approved"
    PROPOSAL_REJECTED = "proposal_rejected"
    FREEZE_ACTIVATED = "freeze_activated"
    FREEZE_DEACTIVATED = "freeze_deactivated"

    # Tasks
    TASK_CREATED = "task_created"
    TASK_RUN_STARTED = "task_run_started"
    TASK_RUN_COMPLETED = "task_run_completed"
    TASK_RUN_FAILED = "task_run_failed"

    # Checkpoints
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_ROLLED_BACK = "checkpoint_rolled_back"

    # Sessions
    SESSION_CREATED = "session_created"
    SESSION_RECOVERED = "session_recovered"

    # Security
    AI_ENABLED = "ai_enabled"
    AI_DISABLED = "ai_disabled"
    GRANT_CREATED = "grant_created"
    GRANT_REVOKED = "grant_revoked"

    # Remote
    REMOTE_RUN_TRIGGERED = "remote_run_triggered"
    REMOTE_RUN_COMPLETED = "remote_run_completed"

    # Tools
    TOOL_REGISTERED = "tool_registered"
    TOOL_INVOKED = "tool_invoked"
    TERMINAL_EXECUTED = "terminal_executed"

    # Custom
    CUSTOM = "custom"


class AuditEntry(BaseModel):
    """A single immutable audit log entry."""
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: str
    actor: str  # user_id or "system"
    target: Optional[str] = None  # resource being acted on
    target_type: Optional[str] = None  # e.g. "task", "proposal", "checkpoint"
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None
    task_id: Optional[str] = None

    # Details
    metadata: Dict[str, Any] = Field(default_factory=dict)
    justification: Optional[str] = None

    # Timing
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Immutability marker
    sequence_number: int = 0


class AuditStore:
    """
    Queryable in-memory audit store.

    Entries are append-only (immutable). Each entry gets a monotonic
    sequence number for ordering and replay support.
    """

    def __init__(self):
        self._entries: List[AuditEntry] = []
        self._sequence: int = 0

    def record(
        self,
        action: str,
        actor: str,
        target: Optional[str] = None,
        target_type: Optional[str] = None,
        session_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        justification: Optional[str] = None,
    ) -> AuditEntry:
        """Record an immutable audit entry."""
        self._sequence += 1
        entry = AuditEntry(
            action=action,
            actor=actor,
            target=target,
            target_type=target_type,
            session_id=session_id,
            workspace_id=workspace_id,
            task_id=task_id,
            metadata=metadata or {},
            justification=justification,
            sequence_number=self._sequence,
        )
        self._entries.append(entry)
        logger.info(f"Audit #{self._sequence}: {action} by {actor} on {target}")
        return entry

    def query(
        self,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        target: Optional[str] = None,
        target_type: Optional[str] = None,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Query audit entries with filters."""
        results = list(self._entries)

        if action:
            results = [e for e in results if e.action == action]
        if actor:
            results = [e for e in results if e.actor == actor]
        if target:
            results = [e for e in results if e.target == target]
        if target_type:
            results = [e for e in results if e.target_type == target_type]
        if task_id:
            results = [e for e in results if e.task_id == task_id]
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        if workspace_id:
            results = [e for e in results if e.workspace_id == workspace_id]
        if since:
            results = [e for e in results if e.timestamp >= since]
        if until:
            results = [e for e in results if e.timestamp <= until]

        # Latest first
        results.sort(key=lambda e: e.sequence_number, reverse=True)
        return results[:limit]

    def get_replay_log(self, task_id: str) -> List[AuditEntry]:
        """Get all audit entries for a task in chronological order (for replay)."""
        entries = [e for e in self._entries if e.task_id == task_id]
        entries.sort(key=lambda e: e.sequence_number)
        return entries

    def count(self, action: Optional[str] = None) -> int:
        """Count audit entries, optionally by action."""
        if action:
            return sum(1 for e in self._entries if e.action == action)
        return len(self._entries)

    def stats(self) -> Dict[str, Any]:
        """Get aggregate statistics."""
        from collections import Counter
        action_counts = Counter(e.action for e in self._entries)
        actor_counts = Counter(e.actor for e in self._entries)
        return {
            "total_entries": len(self._entries),
            "actions": dict(action_counts.most_common(20)),
            "top_actors": dict(actor_counts.most_common(10)),
            "sequence": self._sequence,
        }


# Singleton
_audit_store: Optional[AuditStore] = None


def get_audit_store() -> AuditStore:
    global _audit_store
    if _audit_store is None:
        _audit_store = AuditStore()
    return _audit_store
