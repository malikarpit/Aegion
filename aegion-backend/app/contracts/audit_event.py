"""
Aegion Data Contracts - Audit Event.

Doctrine: "Every action leaves a trace."
Append-only audit log with full provenance.

From Memory Persistence Doctrine:
- M-4 Audit & Lineage: Accountability log. Who/When/Why. Append-only.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from ..core.time import TimeAuthority, AuditTime


class AuditCategory(str, Enum):
    """Categories of audit events."""
    SESSION = "session"
    DECISION = "decision"
    GOVERNANCE = "governance"
    AI = "ai"
    EVIDENCE = "evidence"
    SECURITY = "security"
    SYSTEM = "system"


class AuditSeverity(str, Enum):
    """Severity level for audit events."""
    INFO = "info"          # Normal operations
    WARNING = "warning"    # Unusual but not error
    ERROR = "error"        # Operation failed
    CRITICAL = "critical"  # Security or governance violation


class AuditAction(str, Enum):
    """Standard audit actions."""
    # Session actions
    SESSION_STARTED = "session.started"
    SESSION_CLOSED = "session.closed"
    SESSION_DISTILLED = "session.distilled"
    SESSION_EXPIRED = "session.expired"
    
    # Decision actions
    DECISION_PROPOSED = "decision.proposed"
    DECISION_APPROVED = "decision.approved"
    DECISION_REJECTED = "decision.rejected"
    DECISION_SUPERSEDED = "decision.superseded"
    DECISION_APPLIED = "decision.applied"
    
    # Governance actions
    FREEZE_ACTIVATED = "governance.freeze.activated"
    FREEZE_DEACTIVATED = "governance.freeze.deactivated"
    POLICY_REGISTERED = "governance.policy.registered"
    POLICY_ACTIVATED = "governance.policy.activated"
    INVARIANT_VIOLATED = "governance.invariant.violated"
    
    # AI actions
    COUNCIL_INVOKED = "ai.council.invoked"
    COUNCIL_COMPLETED = "ai.council.completed"
    COUNCIL_ABSTAINED = "ai.council.abstained"
    EVIDENCE_CLASSIFIED = "ai.evidence.classified"
    
    # Security actions
    AUTH_SUCCESS = "security.auth.success"
    AUTH_FAILURE = "security.auth.failure"
    AUTH_BLOCKED = "security.auth.blocked"
    PERMISSION_DENIED = "security.permission.denied"
    
    # System actions
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    CONFIG_CHANGED = "system.config.changed"
    
    # Remote Run actions
    REMOTE_RUN_TRIGGERED = "run.triggered"


class AuditEvent(BaseModel):
    """
    Immutable audit event.
    Once created, cannot be modified or deleted.
    """
    # Identity
    event_id: str = Field(..., description="Unique event ID (UUID)")
    
    # Timing (from TimeAuthority)
    timestamp: AuditTime = Field(
        default_factory=TimeAuthority.now,
        description="UTC timestamp from TimeAuthority"
    )
    
    # Classification
    category: AuditCategory
    action: AuditAction
    severity: AuditSeverity = Field(default=AuditSeverity.INFO)
    
    # Provenance (Who did what to whom)
    actor_id: str = Field(..., description="Who performed the action")
    actor_type: str = Field(
        default="user",
        description="Type: 'user' | 'system' | 'ai_child' | 'ai_parent' | 'sentinel'"
    )
    
    # Target
    target_type: str = Field(..., description="Type of target (session, decision, etc)")
    target_id: str = Field(..., description="ID of the target")
    
    # Context
    session_id: Optional[str] = Field(None, description="Related session, if any")
    workspace_id: Optional[str] = Field(None, description="Related workspace")
    
    # Justification (WHY)
    justification: str = Field(..., description="Why this action was taken")
    
    # Outcome
    success: bool = Field(default=True, description="Did the action succeed?")
    error_message: Optional[str] = Field(None, description="Error if failed")
    
    # Additional data
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured data"
    )
    
    # Evidence chain
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="Evidence supporting this action"
    )
    
    # Supersession tracking
    supersedes_event_id: Optional[str] = Field(
        None,
        description="If this event supersedes another"
    )
    
    # ---------- Integrity / Tamper-Resistance ----------
    prev_hash: Optional[str] = Field(
        None,
        description="SHA-256 hash of the previous event in the chain (genesis = None)"
    )
    event_hash: Optional[str] = Field(
        None,
        description="SHA-256 of canonical content fields (set by AuditChain.append)"
    )
    signature: Optional[str] = Field(
        None,
        description="HMAC-SHA256 of event_hash using the server signing key"
    )
    
    def canonical_bytes(self) -> bytes:
        """Deterministic byte representation for hashing (excludes integrity fields)."""
        import json
        canonical = {
            "event_id": self.event_id,
            "timestamp": str(self.timestamp),
            "category": self.category.value,
            "action": self.action.value,
            "severity": self.severity.value,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "justification": self.justification,
            "success": self.success,
            "error_message": self.error_message,
            "evidence_ids": sorted(self.evidence_ids),
            "supersedes_event_id": self.supersedes_event_id,
            "prev_hash": self.prev_hash,
        }
        return json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode('utf-8')
    
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "example": {
                "event_id": "audit-123",
                "timestamp": "2026-02-09T10:00:00Z",
                "category": "decision",
                "action": "decision.approved",
                "severity": "info",
                "actor_id": "user-456",
                "actor_type": "user",
                "target_type": "decision",
                "target_id": "decision-789",
                "session_id": "session-abc",
                "justification": "Reviewed and verified test coverage meets requirements",
                "success": True,
                "evidence_ids": ["evidence-001", "evidence-002"],
                "prev_hash": None,
                "event_hash": "a1b2c3...",
                "signature": "d4e5f6..."
            }
        }
    )


class AuditEventBuilder:
    """
    Builder for creating audit events with proper defaults.
    Ensures all required fields are set.
    """
    
    def __init__(self, action: AuditAction):
        self._action = action
        self._category = self._infer_category(action)
        self._data: Dict[str, Any] = {}
    
    @staticmethod
    def _infer_category(action: AuditAction) -> AuditCategory:
        """Infer category from action prefix."""
        prefix = action.value.split('.')[0]
        mapping = {
            'session': AuditCategory.SESSION,
            'decision': AuditCategory.DECISION,
            'governance': AuditCategory.GOVERNANCE,
            'ai': AuditCategory.AI,
            'security': AuditCategory.SECURITY,
            'system': AuditCategory.SYSTEM,
        }
        return mapping.get(prefix, AuditCategory.SYSTEM)
    
    def with_actor(self, actor_id: str, actor_type: str = "user") -> "AuditEventBuilder":
        self._data['actor_id'] = actor_id
        self._data['actor_type'] = actor_type
        return self
    
    def with_target(self, target_type: str, target_id: str) -> "AuditEventBuilder":
        self._data['target_type'] = target_type
        self._data['target_id'] = target_id
        return self
    
    def with_session(self, session_id: str) -> "AuditEventBuilder":
        self._data['session_id'] = session_id
        return self
    
    def with_justification(self, justification: str) -> "AuditEventBuilder":
        self._data['justification'] = justification
        return self
    
    def with_evidence(self, evidence_ids: List[str]) -> "AuditEventBuilder":
        self._data['evidence_ids'] = evidence_ids
        return self
    
    def with_failure(self, error: str) -> "AuditEventBuilder":
        self._data['success'] = False
        self._data['error_message'] = error
        self._data['severity'] = AuditSeverity.ERROR
        return self
    
    def build(self) -> AuditEvent:
        import uuid
        return AuditEvent(
            event_id=str(uuid.uuid4()),
            category=self._category,
            action=self._action,
            **self._data
        )
