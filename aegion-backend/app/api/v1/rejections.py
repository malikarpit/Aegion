"""
Aegion API v1 - Rejection Endpoints.

Phase 3: The Cognitive Plane
API for managing and querying rejection artifacts.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from pydantic import BaseModel

from ...services.chronos.rejections import get_rejection_service
from ...contracts.rejection import (
    RejectionArtifact,
    RejectionReason,
    RejectionQuery,
    RejectionStats
)
from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger


router = APIRouter(prefix="/rejections", tags=["rejections"])


# ========== Request/Response Models ==========

class RecordRejectionRequest(BaseModel):
    proposal_id: str
    proposal_title: str
    proposal_tier: str
    reason_category: RejectionReason
    reason_detail: str
    workspace_id: str
    session_id: Optional[str] = None


# ========== Endpoints ==========

@router.post("/", response_model=RejectionArtifact)
async def record_rejection(
    request: RecordRejectionRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Record a new rejection artifact.
    
    Called when a proposal is rejected to capture the learning.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    service = get_rejection_service()
    
    artifact = await service.record_rejection(
        proposal_id=request.proposal_id,
        proposal_title=request.proposal_title,
        proposal_tier=request.proposal_tier,
        rejected_by=user.user_id,
        reason_category=request.reason_category,
        reason_detail=request.reason_detail,
        workspace_id=request.workspace_id,
        session_id=request.session_id
    )
    
    return artifact


@router.get("/{rejection_id}", response_model=RejectionArtifact)
async def get_rejection(
    rejection_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get a specific rejection by ID."""
    service = get_rejection_service()
    artifact = await service.get_rejection(rejection_id)
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Rejection not found")
    
    return artifact


@router.post("/query", response_model=List[RejectionArtifact])
async def query_rejections(
    query: RejectionQuery,
    user: AuthorityContext = Depends(get_current_user)
):
    """Query rejections with filters."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    service = get_rejection_service()
    return await service.query_rejections(query)


@router.get("/stats/{workspace_id}", response_model=RejectionStats)
async def get_rejection_stats(
    workspace_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get rejection statistics for a workspace."""
    service = get_rejection_service()
    return await service.get_stats(workspace_id)


@router.get("/stats", response_model=RejectionStats)
async def get_global_stats(
    user: AuthorityContext = Depends(get_current_user)
):
    """Get global rejection statistics."""
    service = get_rejection_service()
    return await service.get_stats()
