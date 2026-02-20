"""
Aegion API v1 - Audit Access Control Endpoints.

Phase 4: Execution & Resilience
API for managing audit log permissions.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from ...services.archon.audit_acl import get_audit_acl
from ...contracts.audit_permission import (
    AuditPermission,
    AuditGrant,
    AuditQuery
)
from ...core.security import AuthorityContext, get_current_user


router = APIRouter(prefix="/audit", tags=["audit"])


# ========== Request Models ==========

class GrantRequest(BaseModel):
    user_id: str
    permissions: List[AuditPermission]
    scope: str = "*"
    reason: str
    expires_at: Optional[str] = None


class RevokeRequest(BaseModel):
    grant_id: str


# ========== Endpoints ==========

@router.post("/grants", response_model=AuditGrant)
async def create_grant(
    request: GrantRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """Grant audit permissions to a user."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    acl = get_audit_acl()
    
    # Check if granting user has admin access
    has_admin = await acl.check_permission(user.user_id, AuditPermission.READ_ALL)
    if not has_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can grant audit permissions"
        )
    
    return await acl.grant(
        user_id=request.user_id,
        permissions=request.permissions,
        scope=request.scope,
        granted_by=user.user_id,
        reason=request.reason,
        expires_at=request.expires_at
    )


@router.delete("/grants/{grant_id}")
async def revoke_grant(
    grant_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Revoke an audit permission grant."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    acl = get_audit_acl()
    
    has_admin = await acl.check_permission(user.user_id, AuditPermission.READ_ALL)
    if not has_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can revoke grants"
        )
    
    success = await acl.revoke(grant_id, user.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Grant not found")
    
    return {"status": "revoked"}


@router.get("/grants/me", response_model=List[AuditGrant])
async def my_grants(
    user: AuthorityContext = Depends(get_current_user)
):
    """Get my audit permission grants."""
    acl = get_audit_acl()
    return await acl.get_user_grants(user.user_id)


@router.post("/check")
async def check_query_access(
    query: AuditQuery,
    user: AuthorityContext = Depends(get_current_user)
):
    """Check if current user can execute an audit query."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    acl = get_audit_acl()
    allowed, reason = await acl.can_query(user.user_id, query)
    
    return {
        "allowed": allowed,
        "reason": reason
    }


# ========== Feature: Structured Audit Events ==========


class AuditEventQuery(BaseModel):
    action: Optional[str] = None
    actor: Optional[str] = None
    target: Optional[str] = None
    target_type: Optional[str] = None
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None
    limit: int = 100


class RecordEventRequest(BaseModel):
    action: str
    target: Optional[str] = None
    target_type: Optional[str] = None
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None
    task_id: Optional[str] = None
    metadata: Optional[dict] = None
    justification: Optional[str] = None


@router.post("/events", status_code=201)
async def record_audit_event(
    request: RecordEventRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Record a structured audit event."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    from ...services.audit_store import get_audit_store
    store = get_audit_store()

    entry = store.record(
        action=request.action,
        actor=user.user_id,
        target=request.target,
        target_type=request.target_type,
        session_id=request.session_id,
        workspace_id=request.workspace_id,
        task_id=request.task_id,
        metadata=request.metadata,
        justification=request.justification,
    )

    return {
        "entry_id": entry.entry_id,
        "action": entry.action,
        "sequence_number": entry.sequence_number,
        "timestamp": entry.timestamp.isoformat(),
    }


@router.get("/events")
async def query_audit_events(
    action: Optional[str] = None,
    actor: Optional[str] = None,
    target: Optional[str] = None,
    target_type: Optional[str] = None,
    task_id: Optional[str] = None,
    limit: int = 100,
    user: AuthorityContext = Depends(get_current_user),
):
    """Query structured audit events with filters."""
    from ...services.audit_store import get_audit_store
    store = get_audit_store()

    entries = store.query(
        action=action,
        actor=actor,
        target=target,
        target_type=target_type,
        task_id=task_id,
        limit=limit,
    )

    return [
        {
            "entry_id": e.entry_id,
            "action": e.action,
            "actor": e.actor,
            "target": e.target,
            "target_type": e.target_type,
            "task_id": e.task_id,
            "metadata": e.metadata,
            "justification": e.justification,
            "timestamp": e.timestamp.isoformat(),
            "sequence_number": e.sequence_number,
        }
        for e in entries
    ]


@router.get("/replay/{task_id}")
async def replay_task_audit(
    task_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Replay all audit events for a task in chronological order."""
    from ...services.audit_store import get_audit_store
    store = get_audit_store()

    entries = store.get_replay_log(task_id)

    return {
        "task_id": task_id,
        "event_count": len(entries),
        "events": [
            {
                "sequence": e.sequence_number,
                "action": e.action,
                "actor": e.actor,
                "target": e.target,
                "metadata": e.metadata,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in entries
        ],
    }


@router.get("/stats")
async def audit_stats(
    user: AuthorityContext = Depends(get_current_user),
):
    """Get aggregate audit statistics."""
    from ...services.audit_store import get_audit_store
    store = get_audit_store()
    return store.stats()

