"""
Aegion API v1 - Pipeline Endpoints.

Phase 3: The Cognitive Plane
API for managing decision pipelines.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from pydantic import BaseModel

from ...services.nexus.pipelines import get_pipeline_service
from ...contracts.pipeline import (
    DecisionPipeline,
    PipelineTemplate,
    EvaluationOutcome
)
from ...core.security import AuthorityContext, get_current_user


router = APIRouter(prefix="/pipelines", tags=["pipelines"])


# ========== Request Models ==========

class CreatePipelineRequest(BaseModel):
    title: str
    hypothesis_statement: str
    workspace_id: str
    proposal_id: Optional[str] = None
    session_id: Optional[str] = None
    template_id: Optional[str] = None


class ExecuteStepRequest(BaseModel):
    step_index: int
    outcome: EvaluationOutcome
    notes: Optional[str] = None


# ========== Endpoints ==========

@router.post("/", response_model=DecisionPipeline)
async def create_pipeline(
    request: CreatePipelineRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """Create a new decision pipeline."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    service = get_pipeline_service()
    
    return await service.create_pipeline(
        title=request.title,
        hypothesis_statement=request.hypothesis_statement,
        created_by=user.user_id,
        workspace_id=request.workspace_id,
        proposal_id=request.proposal_id,
        session_id=request.session_id,
        template_id=request.template_id
    )


@router.get("/{pipeline_id}", response_model=DecisionPipeline)
async def get_pipeline(
    pipeline_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get a specific pipeline by ID."""
    service = get_pipeline_service()
    pipeline = await service.get_pipeline(pipeline_id)
    
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    return pipeline


@router.post("/{pipeline_id}/step", response_model=DecisionPipeline)
async def execute_step(
    pipeline_id: str,
    request: ExecuteStepRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """Execute a step in the pipeline."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    service = get_pipeline_service()
    
    try:
        return await service.execute_step(
            pipeline_id=pipeline_id,
            step_index=request.step_index,
            outcome=request.outcome,
            notes=request.notes,
            executed_by=user.user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[DecisionPipeline])
async def list_pipelines(
    workspace_id: Optional[str] = None,
    limit: int = 50,
    user: AuthorityContext = Depends(get_current_user)
):
    """List pipelines with optional workspace filter."""
    service = get_pipeline_service()
    return await service.list_pipelines(workspace_id, limit)


@router.get("/templates/all", response_model=List[PipelineTemplate])
async def get_templates(
    user: AuthorityContext = Depends(get_current_user)
):
    """Get all available pipeline templates."""
    service = get_pipeline_service()
    return await service.get_templates()
