"""
Aegion API v1 - Architecture Timeline Endpoints.

Phase 5: Advanced Epistemics
API for ADRs and architecture timeline.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from ...services.chronos.timeline import get_timeline_service
from ...services.chronos.time_travel import get_time_travel
from ...contracts.adr import (
    ArchitectureDecision,
    ADRStatus,
    DecisionDriver,
    TimelineEvent,
    ArchitectureTimeline
)
from ...core.security import AuthorityContext, get_current_user


router = APIRouter(prefix="/architecture", tags=["architecture"])


# ========== Request Models ==========

class CreateADRRequest(BaseModel):
    title: str
    context: str
    decision: str
    rationale: str
    workspace_id: str
    supersedes: Optional[str] = None
    git_commit_shas: List[str] = []  # GAP-6: Link ADR to specific commits


class AcceptADRRequest(BaseModel):
    workspace_id: str
    positive_consequences: List[str] = []
    negative_consequences: List[str] = []


class DeprecateADRRequest(BaseModel):
    workspace_id: str
    reason: str


class CaptureSnapshotRequest(BaseModel):
    state: dict


class DiffRequest(BaseModel):
    timestamp_a: str
    timestamp_b: str


# ========== ADR Endpoints ==========

@router.post("/adrs", response_model=ArchitectureDecision)
async def create_adr(
    request: CreateADRRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """Create a new Architecture Decision Record."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    service = get_timeline_service()
    
    return await service.create_adr(
        title=request.title,
        context=request.context,
        decision=request.decision,
        rationale=request.rationale,
        created_by=user.user_id,
        workspace_id=request.workspace_id,
        supersedes=request.supersedes,
        metadata={"git_commit_shas": request.git_commit_shas}  # GAP-6
    )


@router.get("/adrs/{adr_id}", response_model=ArchitectureDecision)
async def get_adr(
    adr_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get an ADR by ID."""
    service = get_timeline_service()
    adr = await service.get_adr(adr_id)
    
    if not adr:
        raise HTTPException(status_code=404, detail="ADR not found")
    
    return adr


@router.post("/adrs/{adr_id}/accept", response_model=ArchitectureDecision)
async def accept_adr(
    adr_id: str,
    request: AcceptADRRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """Accept an ADR."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    service = get_timeline_service()
    
    try:
        return await service.accept_adr(
            adr_id=adr_id,
            accepted_by=user.user_id,
            workspace_id=request.workspace_id,
            positive_consequences=request.positive_consequences,
            negative_consequences=request.negative_consequences
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/adrs/{adr_id}/deprecate", response_model=ArchitectureDecision)
async def deprecate_adr(
    adr_id: str,
    request: DeprecateADRRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """Deprecate an ADR."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    service = get_timeline_service()
    
    try:
        return await service.deprecate_adr(
            adr_id=adr_id,
            deprecated_by=user.user_id,
            workspace_id=request.workspace_id,
            reason=request.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/adrs", response_model=List[ArchitectureDecision])
async def list_adrs(
    status: Optional[ADRStatus] = None,
    user: AuthorityContext = Depends(get_current_user)
):
    """List all ADRs."""
    service = get_timeline_service()
    return await service.list_adrs(status=status)


@router.get("/adrs/{adr_id}/chain", response_model=List[ArchitectureDecision])
async def get_supersession_chain(
    adr_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get the supersession chain for an ADR."""
    service = get_timeline_service()
    return await service.get_supersession_chain(adr_id)


# ========== Timeline Endpoints ==========

@router.get("/timeline/{workspace_id}", response_model=ArchitectureTimeline)
async def get_timeline(
    workspace_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get the architecture timeline for a workspace."""
    service = get_timeline_service()
    return await service.get_timeline(workspace_id)


# ========== Time Travel Endpoints ==========

@router.post("/snapshots")
async def capture_snapshot(
    request: CaptureSnapshotRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """Capture current state snapshot."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    service = get_time_travel()
    snapshot = await service.capture_snapshot(request.state, user.user_id)
    
    return {
        "snapshot_id": snapshot.snapshot_id,
        "timestamp": snapshot.timestamp
    }


@router.get("/snapshots")
async def list_snapshots(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 20,
    user: AuthorityContext = Depends(get_current_user)
):
    """List available snapshots."""
    service = get_time_travel()
    return await service.list_snapshots(start_time, end_time, limit)


@router.get("/state-at/{timestamp}")
async def get_state_at(
    timestamp: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get system state at a specific timestamp."""
    service = get_time_travel()
    state = await service.get_state_at(timestamp)
    
    if not state:
        raise HTTPException(status_code=404, detail="No state found for timestamp")
    
    return state


@router.post("/diff")
async def diff_states(
    request: DiffRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """Compare states at two points in time."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    service = get_time_travel()
    return await service.diff_states(request.timestamp_a, request.timestamp_b)


@router.post("/adrs/extract")
async def extract_adrs_from_decisions(
    workspace_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    GAP-13: Auto-extract ADR drafts from behavior.

    Scans approved T2+ decisions that lack an ADR link and
    generates candidate ADR drafts for human review.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    from .analytics import _graph_service
    from ...ports.knowledge_graph import GraphEdgeType

    # Fetch approved decisions
    all_decisions = await _graph_service.list_decisions(
        workspace_id=workspace_id, limit=100
    )

    tier_rank = {"T3": 3, "T2": 2, "T1": 1, "T0": 0}
    candidates = []
    
    for d in all_decisions:
        props = d.properties
        tier = props.get("tier", "T0")
        status = props.get("status", "")
        
        # Only T2+ approved decisions
        if tier_rank.get(tier, 0) < 2 or status != "approved":
            continue

        # Check if already linked to an ADR
        edges = await _graph_service.get_edges(
            source_id=d.node_id,
            edge_type=GraphEdgeType.DERIVES_FROM
        )
        if edges:
            continue  # Already has ADR lineage

        # Generate ADR draft
        candidates.append({
            "source_decision_id": d.node_id,
            "suggested_title": f"ADR: {props.get('title', 'Untitled')}",
            "context": props.get("description", ""),
            "decision": props.get("title", ""),
            "rationale": props.get("reasoning", props.get("description", "")),
            "tier": tier,
            "decided_at": props.get("decided_at", ""),
        })

    return {
        "workspace_id": workspace_id,
        "candidates_count": len(candidates),
        "adr_candidates": candidates,
    }
