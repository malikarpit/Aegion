"""
Aegion Governance Control API.

Freeze mode toggle + governance status/policy endpoints.
Provides operator controls for system-wide governance state.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ...services.archon import get_archon, GovernanceError
from ...core.security import AuthorityContext, Role, get_current_user
from ...core.logging import logger
from ...services.governance_conflict import conflict_service
from ...models.conflict import Conflict
from typing import List


router = APIRouter(prefix="/governance", tags=["governance"])


# ========== Models ==========

class FreezeRequest(BaseModel):
    reason: str


class FreezeResponse(BaseModel):
    status: str
    actor: str
    reason: Optional[str] = None


# ========== Endpoints ==========

@router.post("/freeze", response_model=FreezeResponse)
async def activate_freeze(
    request: FreezeRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Activate freeze mode. Blocks all mutations system-wide.
    Only ADMIN users can activate freeze mode.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only admins can activate freeze mode"
        )

    await archon.activate_freeze(actor_id=user.user_id, reason=request.reason)

    return FreezeResponse(
        status="frozen",
        actor=user.user_id,
        reason=request.reason
    )


@router.post("/unfreeze", response_model=FreezeResponse)
async def deactivate_freeze(
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Deactivate freeze mode. Re-enables mutations.
    Only ADMIN users can deactivate freeze mode.

    NOTE: This endpoint intentionally does NOT call guard_writable().
    If it did, unfreeze would be blocked while frozen — a deadlock.
    Access control is enforced via ADMIN role check instead.
    """
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only admins can deactivate freeze mode"
        )

    from ...services.archon import get_archon
    archon = get_archon()
    await archon.deactivate_freeze(actor_id=user.user_id, reason="Admin unfreeze")

    return FreezeResponse(
        status="writable",
        actor=user.user_id
    )


@router.get("/status")
async def get_governance_status():
    """
    Get current governance status including freeze state.
    No authentication required — status is public.
    """
    archon = get_archon()

    return {
        "frozen": archon._freeze_mode,
        "version": "1.0.0",
    }


@router.get("/policy")
async def get_governance_policy():
    """
    Get current governance policy configuration.
    Returns tier definitions, evidence requirements, and quorum rules.
    """
    return {
        "version": "1.0.0",
        "tiers": {
            "T0": {"label": "Auto-approve", "quorum": 0, "evidence_required": 0},
            "T1": {"label": "Single approval", "quorum": 1, "evidence_required": 1},
            "T2": {"label": "Architect review", "quorum": 2, "evidence_required": 2},
            "T3": {"label": "Admin only", "quorum": 3, "evidence_required": 3},
        },
        "roles": {
            "admin": {"can_approve_all": True, "can_freeze": True},
            "architect": {"can_approve_t1": True, "can_approve_t2": False},
            "developer": {"can_propose": True, "can_approve": False},
            "viewer": {"can_propose": False, "can_approve": False},
        },
        "doctrine": "AI proposes, humans dispose.",
    }


# ========== Feature: Per-Workspace AI Toggle ==========

# Workspace AI enabled/disabled state
_workspace_ai_enabled: dict[str, bool] = {}


class AIToggleRequest(BaseModel):
    enabled: bool
    reason: Optional[str] = None


@router.post("/workspaces/{workspace_id}/ai-toggle")
async def toggle_workspace_ai(
    workspace_id: str,
    request: AIToggleRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Enable or disable AI for a specific workspace."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can toggle AI settings")

    _workspace_ai_enabled[workspace_id] = request.enabled

    action = "enabled" if request.enabled else "disabled"
    logger.audit(
        action=f"AI_{action.upper()}",
        actor=user.user_id,
        target=workspace_id,
        justification=request.reason or f"AI {action} by admin",
    )

    return {
        "workspace_id": workspace_id,
        "ai_enabled": request.enabled,
        "toggled_by": user.user_id,
        "reason": request.reason,
    }


@router.get("/workspaces/{workspace_id}/ai-status")
async def get_workspace_ai_status(workspace_id: str):
    """Check if AI is enabled for a workspace."""
    enabled = _workspace_ai_enabled.get(workspace_id, True)  # Default: enabled
    return {
        "workspace_id": workspace_id,
        "ai_enabled": enabled,
    }

# ========== Feature: Governance Conflicts ==========

class ScanRequest(BaseModel):
    workspace_id: str
    file_path: str
    content: str

@router.post("/scan", response_model=List[Conflict])
async def scan_file(
    request: ScanRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Scans a file for governance conflicts.
    Triggers 'conflict.detected' event via WebSocket if violations are found.
    """
    conflicts = await conflict_service.detect_conflicts(
        workspace_id=request.workspace_id,
        file_path=request.file_path,
        content=request.content
    )
    return conflicts

class BranchScanRequest(BaseModel):
    workspace_id: str
    base_branch: str = "main"
    head_branch: str = "HEAD"

@router.post("/scan/branch", response_model=List[Conflict])
async def scan_branch(
    request: BranchScanRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Scans for conflicts between two branches (drift detection).
    """
    conflicts = await conflict_service.detect_branch_conflicts(
        workspace_id=request.workspace_id,
        base_branch=request.base_branch,
        head_branch=request.head_branch
    )
    return conflicts

@router.get("/workspaces/{workspace_id}/conflicts", response_model=List[Conflict])
async def get_active_conflicts(
    workspace_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Returns all active conflicts for a workspace.
    """
    return conflict_service.get_active_conflicts(workspace_id)


@router.get("/proposals/{proposal_id}/export")
async def export_proposal_summary(
    proposal_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Generate a markdown summary of the proposal for PR descriptions.
    """
    from ...services.archon.compliance import get_compliance_exporter
    exporter = get_compliance_exporter()
    summary = await exporter.generate_pr_description(proposal_id)
    return {"proposal_id": proposal_id, "markdown": summary}

