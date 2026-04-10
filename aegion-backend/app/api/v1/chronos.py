"""
Aegion API v1 - Chronos Endpoints.

Advanced Epistemics
Exposes Architecture Timeline Service resources.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field

from ...core.security import AuthorityContext, get_current_user
from ...core.errors import ConcurrencyError
from ...services.chronos.timeline import get_timeline_service, ArchitectureTimelineService
from ...contracts.adr import ArchitectureDecision, ADRStatus, DecisionDriver

router = APIRouter(prefix="/chronos", tags=["chronos"])

# ========== Request Models ==========

class CreateADRRequest(BaseModel):
    title: str
    context: str
    decision: str
    rationale: str
    drivers: List[DecisionDriver] = Field(default_factory=list)
    supersedes: Optional[str] = None
    workspace_id: str = "default"

class AcceptADRRequest(BaseModel):
    expected_version: int
    positive_consequences: List[str] = Field(default_factory=list)
    negative_consequences: List[str] = Field(default_factory=list)
    workspace_id: str = "default"

class DeprecateADRRequest(BaseModel):
    expected_version: int
    reason: str
    workspace_id: str = "default"

# ========== Dependency ==========

def get_service() -> ArchitectureTimelineService:
    return get_timeline_service()

# ========== Endpoints ==========

@router.get("/adrs", response_model=List[ArchitectureDecision])
async def list_adrs(
    workspace_id: str = Query("default"),
    status: Optional[ADRStatus] = Query(None),
    service: ArchitectureTimelineService = Depends(get_service),
    user: AuthorityContext = Depends(get_current_user),
):
    """List ADRs, optionally filtered by status."""
    return await service.list_adrs(workspace_id, status)

@router.post("/adrs", response_model=ArchitectureDecision, status_code=status.HTTP_201_CREATED)
async def create_adr(
    request: CreateADRRequest,
    service: ArchitectureTimelineService = Depends(get_service),
    user: AuthorityContext = Depends(get_current_user),
):
    """Create a new Architecture Decision Record."""
    return await service.create_adr(
        title=request.title,
        context=request.context,
        decision=request.decision,
        rationale=request.rationale,
        created_by=user.user_id,
        workspace_id=request.workspace_id,
        drivers=request.drivers,
        supersedes=request.supersedes
    )

@router.get("/adrs/{adr_id}", response_model=ArchitectureDecision)
async def get_adr(
    adr_id: str,
    service: ArchitectureTimelineService = Depends(get_service),
    user: AuthorityContext = Depends(get_current_user),
):
    """Get a specific ADR."""
    adr = await service.get_adr(adr_id)
    if not adr:
        raise HTTPException(status_code=404, detail="ADR not found")
    return adr

@router.post("/adrs/{adr_id}/accept", response_model=ArchitectureDecision)
async def accept_adr(
    adr_id: str,
    request: AcceptADRRequest,
    service: ArchitectureTimelineService = Depends(get_service),
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Accept an ADR.
    
    Requires optimistic concurrency control via `expected_version`.
    """
    try:
        return await service.accept_adr(
            adr_id=adr_id,
            accepted_by=user.user_id,
            workspace_id=request.workspace_id,
            expected_version=request.expected_version,
            positive_consequences=request.positive_consequences,
            negative_consequences=request.negative_consequences
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConcurrencyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Concurrency Conflict",
                "message": str(e),
                "current_version": e.current_version,
                "expected_version": e.expected_version
            }
        )

@router.post("/adrs/{adr_id}/deprecate", response_model=ArchitectureDecision)
async def deprecate_adr(
    adr_id: str,
    request: DeprecateADRRequest,
    service: ArchitectureTimelineService = Depends(get_service),
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Deprecate an ADR.
    
    Requires optimistic concurrency control via `expected_version`.
    """
    try:
        return await service.deprecate_adr(
            adr_id=adr_id,
            deprecated_by=user.user_id,
            workspace_id=request.workspace_id,
            reason=request.reason,
            expected_version=request.expected_version
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConcurrencyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Concurrency Conflict",
                "message": str(e),
                "current_version": e.current_version,
                "expected_version": e.expected_version
            }
        )

@router.get("/lineage/{adr_id}")
async def get_lineage(
    adr_id: str,
    service: ArchitectureTimelineService = Depends(get_service),
    user: AuthorityContext = Depends(get_current_user),
):
    """Get supersession lineage for an ADR."""
    return await service.get_supersession_chain(adr_id)
