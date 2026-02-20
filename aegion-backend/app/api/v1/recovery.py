"""
Aegion API - Session Recovery.

Implements "Crash Recovery" by converting stuck sessions into Drafts.
DOCTRINE: "Day Zero is not Day One". Crashed sessions are not resumed, they are forked.

AG-005: Uses InMemorySessionStore + InMemoryDraftStore (no Firestore dependency).
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List
from datetime import timedelta

from ...models.session import Session, SessionStatus
from ...models.draft import SessionDraft
from ...core.security import AuthorityContext, get_current_user
from ...core.time import TimeAuthority
from ...core.logging import logger
from .stores import get_session_store, get_draft_store

router = APIRouter(prefix="/sessions", tags=["Session Recovery"])


def _get_session_store():
    """Get session store (testable seam)."""
    return get_session_store()


def _get_draft_store():
    """Get draft store (testable seam)."""
    return get_draft_store()


@router.get("/orphaned", response_model=List[Session])
async def list_orphaned_sessions(
    threshold_minutes: int = Query(60, description="Minutes of inactivity"),
    user: AuthorityContext = Depends(get_current_user)
):
    """
    List active sessions that have been inactive for > threshold.
    """
    threshold_time = TimeAuthority.now_dt() - timedelta(minutes=threshold_minutes)
    threshold_iso = threshold_time.isoformat()
    
    session_store = _get_session_store()
    stale_sessions = await session_store.list_active_stale(threshold_iso)
    
    # Filter by user (orphans must belong to the user requesting them)
    return [s for s in stale_sessions if s.owner_id == user.user_id]


@router.post("/{session_id}/recover", response_model=SessionDraft)
async def recover_session(
    session_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Recover a crashed/stale session.
    1. Mark old session as EXPIRED (dead).
    2. Create new Draft with old session's context.
    3. Return the Draft.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    session_store = _get_session_store()
    draft_store = _get_draft_store()
    
    # 1. Get Session
    session = await session_store.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if session.owner_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Cannot recover inactive session")
    
    # 2. Terminate Old Session
    await session_store.update(session_id, {
        "status": "expired",
        "closed_at": TimeAuthority.now()
    })
    
    # 3. Create Draft
    draft = SessionDraft(
        draft_id=f"draft-recv-{session_id}",
        user_id=user.user_id,
        workspace_id=session.workspace_id,
        title=f"Recovered: {session_id}",
        context_data={
            "source_session_id": session_id,
            "recovered_at": TimeAuthority.now(),
            "context_hash": session.context_hash
        },
        conversation_history=[], 
        tags=["recovered"]
    )
    
    # Save to Draft Store
    await draft_store.save(draft)
    
    logger.audit(
        action="SESSION_RECOVERED",
        actor=user.user_id,
        target=session_id,
        justification="Session recovered to draft"
    )
    
    return draft
