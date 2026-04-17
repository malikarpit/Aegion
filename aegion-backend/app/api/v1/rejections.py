"""
Aegion API v1 - Rejection Endpoints.

Phase 3: The Cognitive Plane + W1.4: Rejection Learning Integration
API for managing and querying rejection artifacts.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Dict, Any
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


class PenaltyResponse(BaseModel):
    query: str
    workspace_id: str
    penalty: float
    similar_rejections: int


class TrendsResponse(BaseModel):
    workspace_id: str
    daily_counts: Dict[str, int]
    top_reasons: List[Dict[str, Any]]
    total_rejections: int


# ========== Rejection Learner Helper ==========

def _get_learner():
    """Lazy import to avoid circular dependencies."""
    try:
        from ...services.rejection_learner import get_rejection_learner
        return get_rejection_learner()
    except Exception:
        return None


# ========== Endpoints ==========

@router.post("/", response_model=RejectionArtifact)
async def record_rejection(
    request: RecordRejectionRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Record a new rejection artifact.
    
    Called when a proposal is rejected to capture the learning.
    Also feeds the RejectionLearner for confidence adjustment.
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
    
    # W1.4: Feed the rejection learner (Christiano et al., 2017)
    learner = _get_learner()
    if learner:
        try:
            learner.record_rejection(
                query=request.proposal_title,
                reason=request.reason_detail,
                workspace_id=request.workspace_id,
            )
        except Exception as exc:
            logger.warning(f"Rejection learner feed failed (non-fatal): {exc}")
    
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


@router.get("/trends/{workspace_id}", response_model=TrendsResponse)
async def get_rejection_trends(
    workspace_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Get rejection trend analytics for a workspace (W1.4).
    
    Returns daily rejection counts and top rejection reasons
    using the RejectionLearner (Christiano et al., 2017).
    """
    learner = _get_learner()
    if not learner:
        raise HTTPException(
            status_code=503,
            detail="Rejection learner not available"
        )
    trends = learner.get_trends(workspace_id)
    return TrendsResponse(
        workspace_id=workspace_id,
        daily_counts=trends.get("daily_counts", {}),
        top_reasons=trends.get("top_reasons", []),
        total_rejections=trends.get("total_rejections", 0),
    )


@router.get("/penalty", response_model=PenaltyResponse)
async def get_rejection_penalty(
    query_text: str = Query(..., alias="query"),
    workspace_id: str = Query(...),
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Check how much confidence penalty a query would receive
    based on historical rejection patterns (W1.4).
    """
    learner = _get_learner()
    if not learner:
        return PenaltyResponse(
            query=query_text,
            workspace_id=workspace_id,
            penalty=0.0,
            similar_rejections=0,
        )
    penalty = learner.get_penalty(query_text, workspace_id)
    count = len([
        r for r in learner._rejections
        if r.get("workspace_id") == workspace_id
    ])
    return PenaltyResponse(
        query=query_text,
        workspace_id=workspace_id,
        penalty=round(penalty, 4),
        similar_rejections=count,
    )

