from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, List

from ...services.praxis.sandbox import DockerSandboxRunner
from ...services.praxis.sandbox_hardening import get_quota_manager
from ...core.auth import get_current_user
from ...models.user import User

router = APIRouter(tags=["sandbox"])

class SandboxStats(BaseModel):
    active_executions: int
    docker_available: bool
    workspace_quotas: Dict[str, Any]

@router.get("/stats", response_model=SandboxStats)
async def get_sandbox_stats(
    user: User = Depends(get_current_user)
):
    """
    Get current sandbox usage statistics and health status.
    Requires authentication.
    """
    quota_manager = get_quota_manager()
    
    # Check docker availability
    # We create a temporary runner to check status
    # In a real app, this might be a singleton service check
    runner = DockerSandboxRunner()
    docker_available = runner.docker_available
    
    # Get all quotas (admin view) or filtered (user view?)
    # For now, we return a summary from the quota manager
    # We need to extend QuotaManager to provide this info
    
    # Calculate global active executions
    all_stats = quota_manager.get_stats()
    active_count = sum(s["concurrent_executions"] for s in all_stats.values())

    return SandboxStats(
        active_executions=active_count,
        docker_available=docker_available,
        workspace_quotas=all_stats
    )
