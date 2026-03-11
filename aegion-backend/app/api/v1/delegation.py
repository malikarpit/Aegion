"""
Aegion API v1 - Cloud Delegation Endpoints.

Phase 35: Cloud Delegation (AG-017)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from ...core.security import get_current_user, AuthorityContext

from ...services.delegation_service import get_delegation_service, DelegationService
from ...ports.cloud_delegate import (
    DeploymentResult,
    CloudResource,
    ResourceType,
    DeploymentStatus
)

router = APIRouter()

class DeployRequest(BaseModel):
    artifact_id: str
    target_env: str = "dev"
    config: Dict[str, Any] = {}

@router.post("/deploy", response_model=DeploymentResult)
async def deploy_artifact(
    req: DeployRequest,
    service: DelegationService = Depends(get_delegation_service)
):
    """Trigger a cloud deployment."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return await service.deploy_run(req.artifact_id, req.target_env, req.config)

@router.get("/deployments/{deployment_id}", response_model=DeploymentResult)
async def get_deployment_status(
    deployment_id: str,
    service: DelegationService = Depends(get_delegation_service)
):
    """Get status of a specific deployment."""
    try:
        return await service.get_status(deployment_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/resources", response_model=List[CloudResource])
async def list_resources(
    env: str = "dev",
    type: Optional[ResourceType] = None,
    service: DelegationService = Depends(get_delegation_service)
):
    """List managed cloud resources."""
    return await service.list_cloud_resources(env, type)
@router.get("/resources/{resource_id}/logs")
async def get_resource_logs(
    resource_id: str,
    service: DelegationService = Depends(get_delegation_service)
):
    """Get logs for a specific resource."""
    return await service.get_logs(resource_id)

@router.get("/health")
async def provider_health(
    service: DelegationService = Depends(get_delegation_service)
):
    """Check connectivity to cloud provider."""
    return await service.check_health()


# --- Remote Runs ---

class TriggerRunRequest(BaseModel):
    command: str
    image: str = "aegion-runner:latest"
    env_vars: Dict[str, str] = {}
    timeout_seconds: int = 3600
    resource_size: str = "medium"

@router.post("/runs")
async def trigger_run(
    req: TriggerRunRequest,
    service: DelegationService = Depends(get_delegation_service),
    user: AuthorityContext = Depends(get_current_user),
    session_id: Optional[str] = Header(None, alias="X-Aegion-Session")
):
    """Trigger a remote run."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    run = await service.trigger_run(req.model_dump())

    # Audit
    from ...core.logging import logger
    from ...contracts.audit_event import AuditAction

    logger.audit(
        action=AuditAction.REMOTE_RUN_TRIGGERED.value,
        actor=user.user_id,
        target=run.run_id,
        justification=f"Triggered run: {req.command}",
        session_id=session_id,
        metadata={"config": req.model_dump()}
    )
    return run

@router.get("/runs/{run_id}")
async def get_run_status(
    run_id: str,
    service: DelegationService = Depends(get_delegation_service)
):
    """Get status of a remote run."""
    try:
        return await service.get_run_status(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/runs")
async def list_runs(
    status: Optional[str] = None,
    service: DelegationService = Depends(get_delegation_service)
):
    """List remote runs."""
    return await service.list_runs(status)
