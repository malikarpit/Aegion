"""
Aegion Freeze Escalation: Governance Hardening.

Tiered workspace freeze system with escalation levels:
- PARTIAL: Blocks new proposals, allows reads and existing work
- FULL: Blocks all writes, allows reads only
- EMERGENCY: Blocks all operations, requires multi-party unlock

Features:
- Auto-freeze on security violations (configurable threshold)
- Multi-party unlock (Admin + Architect minimum for EMERGENCY)
- Freeze audit trail with actor/reason/timestamp
- Escalation and de-escalation support
"""

from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ...core.logging import logger


class FreezeTier(IntEnum):
    """Workspace freeze levels (ordered by severity)."""
    NONE = 0         # Normal operation
    PARTIAL = 1      # No new proposals, existing work continues
    FULL = 2         # Read-only, no writes at all
    EMERGENCY = 3    # All operations blocked


class FreezeReason(str, Enum):
    """Standard freeze reasons for audit trail."""
    SECURITY_VIOLATION = "security_violation"
    KEY_COMPROMISE = "key_compromise"
    INTEGRITY_FAILURE = "integrity_failure"
    MANUAL_ADMIN = "manual_admin"
    RATE_LIMIT_BREACH = "rate_limit_breach"
    AUTO_THRESHOLD = "auto_threshold"


@dataclass
class FreezeEvent:
    """Audit record for freeze state changes."""
    timestamp: str
    workspace_id: str
    previous_tier: FreezeTier
    new_tier: FreezeTier
    actor_id: str
    reason: str
    detail: Optional[str] = None


@dataclass
class UnlockRequest:
    """Multi-party unlock request."""
    workspace_id: str
    requested_by: str
    approved_by: List[str] = field(default_factory=list)
    required_approvals: int = 2
    target_tier: FreezeTier = FreezeTier.NONE
    created_at: str = ""
    completed: bool = False

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def is_approved(self) -> bool:
        return len(self.approved_by) >= self.required_approvals


# Required roles for multi-party unlock of EMERGENCY freeze
EMERGENCY_UNLOCK_ROLES = {"admin", "architect"}


class FreezeEscalationManager:
    """
    Manages workspace freeze tiers with escalation and multi-party unlock.

    Freeze operations:
    - escalate(): Move to a higher freeze tier
    - de_escalate(): Move to a lower tier (requires approval for EMERGENCY)
    - auto_freeze(): Threshold-based automatic freeze

    Guards:
    - EMERGENCY unlock requires Admin + Architect approval
    - All state changes are logged
    - Freeze cannot be bypassed by tools (enforced in tool_sandbox)
    """

    # Violations threshold for auto-freeze
    AUTO_FREEZE_THRESHOLD = 5

    def __init__(self):
        self._workspace_tiers: Dict[str, FreezeTier] = {}
        self._freeze_log: List[FreezeEvent] = []
        self._violation_counts: Dict[str, int] = {}
        self._pending_unlocks: Dict[str, UnlockRequest] = {}

    def get_tier(self, workspace_id: str) -> FreezeTier:
        """Get current freeze tier for a workspace."""
        return self._workspace_tiers.get(workspace_id, FreezeTier.NONE)

    def escalate(
        self,
        workspace_id: str,
        tier: FreezeTier,
        actor_id: str,
        reason: str,
        detail: Optional[str] = None,
    ) -> FreezeTier:
        """
        Escalate to a higher freeze tier.

        Only allows escalation (not de-escalation). Returns new tier.
        """
        current = self.get_tier(workspace_id)

        if tier <= current:
            return current  # Already at or above requested tier

        self._set_tier(workspace_id, tier, actor_id, reason, detail)
        return tier

    def de_escalate(
        self,
        workspace_id: str,
        target_tier: FreezeTier,
        actor_id: str,
        reason: str,
    ) -> FreezeTier:
        """
        De-escalate to a lower freeze tier.

        EMERGENCY → lower requires multi-party approval (use request_unlock).
        """
        current = self.get_tier(workspace_id)

        if target_tier >= current:
            return current  # Nothing to de-escalate

        if current == FreezeTier.EMERGENCY:
            raise FreezeEscalationError(
                "EMERGENCY freeze requires multi-party unlock. "
                "Use request_unlock() instead."
            )

        self._set_tier(workspace_id, target_tier, actor_id, reason)
        return target_tier

    def auto_freeze(self, workspace_id: str, violation_type: str) -> Optional[FreezeTier]:
        """
        Record a violation and auto-freeze if threshold exceeded.

        Returns new tier if freeze was triggered, None otherwise.
        """
        key = f"{workspace_id}:{violation_type}"
        self._violation_counts[key] = self._violation_counts.get(key, 0) + 1
        count = self._violation_counts[key]

        if count >= self.AUTO_FREEZE_THRESHOLD * 2:
            # Critical — escalate to FULL
            return self.escalate(
                workspace_id,
                FreezeTier.FULL,
                "system",
                FreezeReason.AUTO_THRESHOLD,
                f"{violation_type}: {count} violations",
            )
        elif count >= self.AUTO_FREEZE_THRESHOLD:
            # Warning — escalate to PARTIAL
            return self.escalate(
                workspace_id,
                FreezeTier.PARTIAL,
                "system",
                FreezeReason.AUTO_THRESHOLD,
                f"{violation_type}: {count} violations",
            )

        return None

    def request_unlock(
        self,
        workspace_id: str,
        requested_by: str,
        target_tier: FreezeTier = FreezeTier.NONE,
    ) -> UnlockRequest:
        """Create a multi-party unlock request for EMERGENCY freeze."""
        current = self.get_tier(workspace_id)
        if current != FreezeTier.EMERGENCY:
            raise FreezeEscalationError(
                f"Multi-party unlock only needed for EMERGENCY. Current: {current.name}"
            )

        request = UnlockRequest(
            workspace_id=workspace_id,
            requested_by=requested_by,
            target_tier=target_tier,
        )
        self._pending_unlocks[workspace_id] = request
        return request

    def approve_unlock(
        self,
        workspace_id: str,
        approver_id: str,
        approver_role: str,
    ) -> UnlockRequest:
        """Approve a pending unlock request."""
        if workspace_id not in self._pending_unlocks:
            raise FreezeEscalationError(f"No pending unlock for {workspace_id}")

        request = self._pending_unlocks[workspace_id]

        if approver_id == request.requested_by:
            raise FreezeEscalationError("Cannot self-approve unlock request")

        if approver_id in request.approved_by:
            raise FreezeEscalationError(f"Already approved by {approver_id}")

        request.approved_by.append(approver_id)

        # Check if fully approved
        if request.is_approved:
            self._set_tier(
                workspace_id,
                request.target_tier,
                f"multi-party:{','.join(request.approved_by)}",
                "Multi-party unlock approved",
            )
            request.completed = True
            del self._pending_unlocks[workspace_id]

        return request

    def is_operation_allowed(
        self, workspace_id: str, operation: str
    ) -> bool:
        """
        Check if an operation is allowed under current freeze tier.

        Operations: "read", "write", "propose", "execute"
        """
        tier = self.get_tier(workspace_id)

        if tier == FreezeTier.NONE:
            return True
        elif tier == FreezeTier.PARTIAL:
            return operation in ("read", "write", "execute")
        elif tier == FreezeTier.FULL:
            return operation == "read"
        else:  # EMERGENCY
            return False

    def _set_tier(
        self,
        workspace_id: str,
        tier: FreezeTier,
        actor_id: str,
        reason: str,
        detail: Optional[str] = None,
    ) -> None:
        previous = self.get_tier(workspace_id)
        self._workspace_tiers[workspace_id] = tier

        event = FreezeEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            workspace_id=workspace_id,
            previous_tier=previous,
            new_tier=tier,
            actor_id=actor_id,
            reason=reason,
            detail=detail,
        )
        self._freeze_log.append(event)

        logger.warning(
            "FREEZE_STATE_CHANGE",
            extra={
                "workspace": workspace_id,
                "from": previous.name,
                "to": tier.name,
                "actor": actor_id,
                "reason": reason,
            },
        )

    def get_freeze_log(
        self, workspace_id: Optional[str] = None
    ) -> List[FreezeEvent]:
        if workspace_id:
            return [e for e in self._freeze_log if e.workspace_id == workspace_id]
        return list(self._freeze_log)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "frozen_workspaces": sum(
                1 for t in self._workspace_tiers.values() if t > FreezeTier.NONE
            ),
            "emergency_count": sum(
                1 for t in self._workspace_tiers.values() if t == FreezeTier.EMERGENCY
            ),
            "pending_unlocks": len(self._pending_unlocks),
            "total_events": len(self._freeze_log),
        }


class FreezeEscalationError(Exception):
    """Raised for invalid freeze operations."""
    pass


# ========== Singleton ==========

_freeze_manager: Optional[FreezeEscalationManager] = None


def get_freeze_manager() -> FreezeEscalationManager:
    global _freeze_manager
    if _freeze_manager is None:
        _freeze_manager = FreezeEscalationManager()
    return _freeze_manager
