"""
Aegion API - Session Drafts.

Endpoints for managing ephemeral session state (Partial Persistence).

AG-005: Uses InMemoryDraftStore (no Firestore dependency).
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

from ...models.draft import SessionDraft
from ...core.security import AuthorityContext, get_current_user
from .stores import get_draft_store

router = APIRouter(prefix="/sessions/drafts", tags=["Session Drafts"])


def _get_draft_store():
    """Get the draft store (testable seam)."""
    return get_draft_store()


@router.post("/", response_model=SessionDraft)
async def save_draft(
    draft: SessionDraft,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Save or update a session draft.
    Drafts are mutable and ephemeral.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if draft.user_id != user.user_id:
         raise HTTPException(status_code=403, detail="Cannot save draft for another user")
    
    store = _get_draft_store()
    saved_draft = await store.save(draft)
    return saved_draft

@router.get("/", response_model=List[SessionDraft])
async def list_drafts(
    user: AuthorityContext = Depends(get_current_user)
):
    """List all drafts owned by the current user."""
    store = _get_draft_store()
    return await store.list_for_user(user.user_id)

@router.get("/{draft_id}", response_model=SessionDraft)
async def get_draft(
    draft_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Retrieve a specific draft."""
    store = _get_draft_store()
    draft = await store.get(draft_id)
    
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    return draft

@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(
    draft_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Discard a draft."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    store = _get_draft_store()
    draft = await store.get(draft_id)
    
    if not draft:
        return # Idempotent
        
    if draft.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    await store.delete(draft_id)
    return

@router.post("/{draft_id}/restore", status_code=status.HTTP_201_CREATED)
async def restore_draft(
    draft_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Restore a draft into an Active Session.
    This effectively 'opens' the session and deletes the draft.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    store = _get_draft_store()
    draft = await store.get(draft_id)
    
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
        
    if draft.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Create session from draft context
    session_id = f"sess-{draft_id}"
    
    # Consume the draft
    await store.delete(draft_id)
    
    return {"message": "Draft restored to active session", "session_id": session_id}
