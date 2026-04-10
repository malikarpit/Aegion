"""
Aegion Collaboration API.

Endpoints for session ownership and real-time collaboration control.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import Optional

from ...core.security import get_current_user, AuthorityContext, Role
from ...core.logging import logger
from ...models.collaboration import SessionOwnership, OwnershipStatus
from ...services.session_manager import get_session_manager, GovernanceError
from ...services.collaboration.handoff import get_handoff_service
from .websocket import manager

router = APIRouter(tags=["collaboration"])
session_manager = get_session_manager()


# ========== Requests ==========

class TransferOwnershipRequest(BaseModel):
    target_user_id: str


# ========== Endpoints ==========

@router.get("/session/{session_id}/ownership", response_model=SessionOwnership)
async def get_session_ownership(
    session_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get current ownership state of a session."""
    ownership = await session_manager.get_ownership(session_id)
    if not ownership:
        raise HTTPException(status_code=404, detail="Session not found")
    return ownership


@router.post("/session/{session_id}/claim", response_model=SessionOwnership)
async def claim_ownership(
    session_id: str,
    force: bool = False,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Claim ownership of a session.
    
    If force=True, admin/owner permissions are required.
    """
    try:
        if force:
            if user.role not in [Role.ADMIN, Role.ARCHITECT]:
                raise HTTPException(
                    status_code=403, 
                    detail="Force claim requires Admin or Architect role"
                )
            
        ownership = await session_manager.claim_ownership(session_id, user.user_id, force=force)
        
        # Broadcast update
        await manager.broadcast_to_workspace(
            ownership.workspace_id,
            {
                "type": "ownership.changed",
                "session_id": session_id,
                "ownership": jsonable_encoder(ownership)
            }
        )
        
        return ownership
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/session/{session_id}/transfer", response_model=SessionOwnership)
async def transfer_ownership(
    session_id: str,
    request: TransferOwnershipRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Initiate ownership transfer to another user.
    """
    try:
        ownership = await session_manager.transfer_ownership(
            session_id, 
            current_owner_id=user.user_id, 
            target_user_id=request.target_user_id
        )

        # Broadcast update
        await manager.broadcast_to_workspace(
            ownership.workspace_id,
            {
                "type": "ownership.changed",
                "session_id": session_id,
                "ownership": jsonable_encoder(ownership)
            }
        )

        return ownership
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/session/{session_id}/release", response_model=SessionOwnership)
async def release_ownership(
    session_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Release ownership of a session.
    """
    try:
        ownership = await session_manager.release_ownership(session_id, user.user_id)

        # Broadcast update
        await manager.broadcast_to_workspace(
            ownership.workspace_id,
            {
                "type": "ownership.changed",
                "session_id": session_id,
                "ownership": jsonable_encoder(ownership)
            }
        )

        return ownership
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/session/{session_id}/handoff")
async def get_handoff_summary(
    session_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Generate a handoff summary for the session.
    """
    handoff_service = get_handoff_service()
    try:
        summary = await handoff_service.generate_handoff_summary(session_id)
        return {"session_id": session_id, "summary": summary}
    except Exception as e:
        logger.error(f"Failed to generate handoff summary: {e}")
        return {"session_id": session_id, "summary": f"# Handoff Report\n\nError generating report: {str(e)}"}
