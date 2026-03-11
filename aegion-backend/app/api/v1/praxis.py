"""
Aegion API v1 - Praxis Execution Endpoints.

Phase 4: Execution & Resilience
API for execution descriptor registry and sandbox.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import uuid

from ...services.praxis.registry import get_descriptor_registry
from ...services.praxis.sandbox import get_sandbox_service
from ...contracts.execution import (
    ExecutionDescriptor,
    ExecutionRequest,
    ExecutionResult,
    ActionType,
    RiskLevel,
    SandboxConfig
)
from ...core.security import AuthorityContext, get_current_user
from ...core.time import TimeAuthority


router = APIRouter(prefix="/praxis", tags=["praxis"])


# ========== Request Models ==========

class RegisterDescriptorRequest(BaseModel):
    action_type: ActionType
    name: str
    description: str
    risk_level: RiskLevel = RiskLevel.MODERATE
    requires_sandbox: bool = False
    requires_approval: bool = False
    timeout_ms: int = 30000


class ExecuteRequest(BaseModel):
    descriptor_id: str
    parameters: dict = {}
    context: dict = {}
    session_id: Optional[str] = None


# ========== Endpoints ==========

@router.get("/descriptors", response_model=List[ExecutionDescriptor])
async def list_descriptors(
    risk_level: Optional[RiskLevel] = None,
    user: AuthorityContext = Depends(get_current_user)
):
    """List all registered execution descriptors."""
    registry = get_descriptor_registry()
    return await registry.list_all(risk_level)


@router.get("/descriptors/{descriptor_id}", response_model=ExecutionDescriptor)
async def get_descriptor(
    descriptor_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get a specific execution descriptor."""
    registry = get_descriptor_registry()
    descriptor = await registry.get(descriptor_id)
    
    if not descriptor:
        raise HTTPException(status_code=404, detail="Descriptor not found")
    
    return descriptor


@router.post("/descriptors", response_model=ExecutionDescriptor)
async def register_descriptor(
    request: RegisterDescriptorRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """Register a new execution descriptor."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    registry = get_descriptor_registry()
    
    return await registry.register(
        action_type=request.action_type,
        name=request.name,
        description=request.description,
        risk_level=request.risk_level,
        requires_sandbox=request.requires_sandbox,
        requires_approval=request.requires_approval,
        timeout_ms=request.timeout_ms,
        created_by=user.user_id
    )


@router.post("/execute", response_model=ExecutionResult)
async def execute_action(
    request: ExecuteRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """Execute an action using a registered descriptor."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    sandbox = get_sandbox_service()
    
    exec_request = ExecutionRequest(
        request_id=f"exec-{uuid.uuid4().hex[:12]}",
        descriptor_id=request.descriptor_id,
        parameters=request.parameters,
        context=request.context,
        session_id=request.session_id,
        requested_by=user.user_id,
        requested_at=TimeAuthority.now()
    )
    
    return await sandbox.execute(exec_request)


@router.get("/executions/{request_id}", response_model=ExecutionResult)
async def get_execution(
    request_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get the result of a previous execution."""
    sandbox = get_sandbox_service()
    result = await sandbox.get_result(request_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return result
