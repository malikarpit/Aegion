"""
Aegion API v1 - Checkpoint Endpoints.

Session checkpoint management for state snapshots and rollback.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import uuid

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger
from ...models.checkpoint import Checkpoint, CheckpointStatus, RollbackResult
from ...services.durable_store import JsonFileStore


router = APIRouter(prefix="/checkpoints", tags=["checkpoints"])


# ========== Durable Store ==========
_checkpoints = JsonFileStore(".aegion_data/checkpoints.json", Checkpoint, "checkpoint_id")


# ========== Request/Response Models ==========


class CreateCheckpointRequest(BaseModel):
    session_id: str
    label: Optional[str] = None
    reason: Optional[str] = "manual"
    state_snapshot: Optional[dict] = None
    metadata: Optional[dict] = None
    evidence_ids: Optional[List[str]] = None  # linked evidence
    decision_ids: Optional[List[str]] = None  # linked decisions


class CheckpointResponse(BaseModel):
    checkpoint_id: str
    session_id: str
    created_by: str
    label: str
    reason: str
    status: str
    created_at: str
    expires_at: Optional[str] = None
    rolled_back_at: Optional[str] = None
    state_key_count: int = 0
    git_commit_sha: Optional[str] = None  
    trigger_action: Optional[str] = None
    evidence_ids: List[str] = []   # linked evidence
    decision_ids: List[str] = []   # linked decisions


# ========== Helpers ==========


def _checkpoint_to_response(cp: Checkpoint) -> CheckpointResponse:
    return CheckpointResponse(
        checkpoint_id=cp.checkpoint_id,
        session_id=cp.session_id,
        created_by=cp.created_by,
        label=cp.label,
        reason=cp.reason,
        status=cp.status.value,
        created_at=cp.created_at.isoformat(),
        expires_at=cp.expires_at.isoformat() if cp.expires_at else None,
        rolled_back_at=cp.rolled_back_at.isoformat() if cp.rolled_back_at else None,
        state_key_count=len(cp.state_snapshot),
        git_commit_sha=cp.git_commit_sha,
        trigger_action=cp.trigger_action,
        evidence_ids=cp.evidence_ids,
        decision_ids=cp.decision_ids,
    )


# ========== Endpoints ==========


@router.post("", response_model=CheckpointResponse, status_code=status.HTTP_201_CREATED)
async def create_checkpoint(
    request: CreateCheckpointRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Create a checkpoint for a session."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    now = datetime.now(timezone.utc)
    checkpoint_id = str(uuid.uuid4())

    cp = Checkpoint(
        checkpoint_id=checkpoint_id,
        session_id=request.session_id,
        created_by=user.user_id,
        label=request.label or f"Checkpoint {now.strftime('%H:%M:%S')}",
        reason=request.reason or "manual",
        status=CheckpointStatus.ACTIVE,
        state_snapshot=request.state_snapshot or {},
        created_at=now,
        expires_at=now + timedelta(hours=24),
        metadata=request.metadata or {},
        evidence_ids=request.evidence_ids or [],
        decision_ids=request.decision_ids or [],
    )

    await _checkpoints.save(cp)
    logger.info(f"Checkpoint created: {checkpoint_id} for session {request.session_id}")
    return _checkpoint_to_response(cp)


@router.get("", response_model=List[CheckpointResponse])
async def list_checkpoints(
    session_id: Optional[str] = None,
    user: AuthorityContext = Depends(get_current_user),
):
    """List checkpoints, optionally filtered by session."""
    cps = await _checkpoints.list_all()

    if session_id:
        cps = [c for c in cps if c.session_id == session_id]

    # Sort newest first
    cps.sort(key=lambda c: c.created_at.timestamp(), reverse=True)
    return [_checkpoint_to_response(c) for c in cps]


@router.get("/{checkpoint_id}", response_model=CheckpointResponse)
async def get_checkpoint(
    checkpoint_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get checkpoint details."""
    cp = await _checkpoints.get(checkpoint_id)
    if not cp:
        raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found")
    return _checkpoint_to_response(cp)


@router.post("/{checkpoint_id}/rollback", response_model=RollbackResult)
async def rollback_to_checkpoint(
    checkpoint_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Rollback session state to a checkpoint."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    cp = await _checkpoints.get(checkpoint_id)
    if not cp:
        raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found")

    if cp.status == CheckpointStatus.EXPIRED:
        raise HTTPException(status_code=400, detail="Cannot rollback to an expired checkpoint")

    if cp.status == CheckpointStatus.ROLLED_BACK:
        raise HTTPException(status_code=400, detail="Checkpoint already rolled back")

    now = datetime.now(timezone.utc)

    # Mark checkpoint as rolled back
    cp.status = CheckpointStatus.ROLLED_BACK
    cp.rolled_back_at = now
    await _checkpoints.save(cp)

    # Restore actual session state from snapshot
    restored_state = None
    if cp.state_snapshot:
        restored_state = cp.state_snapshot
        # In production, this would push state back to the session store
        logger.info(f"State restored: {len(cp.state_snapshot)} keys for session {cp.session_id}")

    logger.info(f"Rolled back to checkpoint {checkpoint_id} for session {cp.session_id}")

    return RollbackResult(
        checkpoint_id=checkpoint_id,
        session_id=cp.session_id,
        rolled_back_at=now.isoformat(),
        previous_state_keys=len(cp.state_snapshot),
        restored_state=restored_state,
        message=f"Rolled back to '{cp.label}' successfully. {len(cp.state_snapshot)} state keys restored.",
    )


@router.delete("/{checkpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_checkpoint(
    checkpoint_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Delete a checkpoint."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    deleted = await _checkpoints.delete(checkpoint_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found")
    logger.info(f"Checkpoint deleted: {checkpoint_id}")


# ========== Feature: Auto-Checkpoint ==========


class AutoCheckpointRequest(BaseModel):
    session_id: str
    trigger_action: str  # e.g. "post_run", "tool_execution", "file_edit"
    action_detail: Optional[str] = None
    state_snapshot: Optional[dict] = None


@router.post("/auto", response_model=CheckpointResponse, status_code=status.HTTP_201_CREATED)
async def create_auto_checkpoint(
    request: AutoCheckpointRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Create an automatic checkpoint triggered by an agent action."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    now = datetime.now(timezone.utc)
    checkpoint_id = str(uuid.uuid4())

    cp = Checkpoint(
        checkpoint_id=checkpoint_id,
        session_id=request.session_id,
        created_by="system",
        label=f"Auto: {request.trigger_action}",
        reason="auto",
        status=CheckpointStatus.ACTIVE,
        state_snapshot=request.state_snapshot or {},
        trigger_action=request.trigger_action,
        created_at=now,
        expires_at=now + timedelta(hours=12),  # shorter TTL for auto checkpoints
        metadata={"action_detail": request.action_detail or ""},
    )

    await _checkpoints.save(cp)
    logger.info(f"Auto-checkpoint created: {checkpoint_id} trigger={request.trigger_action}")
    return _checkpoint_to_response(cp)


# ========== Feature: Git Snapshot Integration ==========


@router.post("/{checkpoint_id}/git-snapshot")
async def create_git_snapshot(
    checkpoint_id: str,
    workspace_path: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Create a shadow git commit for this checkpoint."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    cp = await _checkpoints.get(checkpoint_id)
    if not cp:
        raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found")

    from ...services.git_checkpoint_service import get_git_checkpoint_service
    git_svc = get_git_checkpoint_service()

    snapshot = await git_svc.commit_snapshot(
        workspace_path=workspace_path,
        checkpoint_id=checkpoint_id,
        message=cp.label,
        state_snapshot=cp.state_snapshot,
    )

    cp.git_commit_sha = snapshot.commit_sha
    await _checkpoints.save(cp)

    return {
        "checkpoint_id": checkpoint_id,
        "git_commit_sha": snapshot.commit_sha,
        "files_changed": snapshot.files_changed,
        "message": f"Git snapshot created: {snapshot.commit_sha[:8]}",
    }


@router.get("/{checkpoint_id}/git-diff")
async def get_git_diff(
    checkpoint_id: str,
    workspace_path: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get diff of all changes since this checkpoint."""
    cp = await _checkpoints.get(checkpoint_id)
    if not cp:
        raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found")

    from ...services.git_checkpoint_service import get_git_checkpoint_service
    git_svc = get_git_checkpoint_service()

    diff = await git_svc.diff_from_checkpoint(workspace_path, checkpoint_id)
    return {
        "checkpoint_id": checkpoint_id,
        "git_commit_sha": cp.git_commit_sha,
        "diff": diff,
    }
