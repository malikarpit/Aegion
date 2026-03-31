"""
Aegion Delegation Service.

Phase 35: Cloud Delegation (AG-017)
Orchestrates cloud deployments and resource management.
"""

from typing import List, Dict, Any, Optional
from ..ports.cloud_delegate import (
    CloudDelegate,
    CloudProvider,
    DeploymentResult,
    CloudResource,
    ResourceType
)
from ..adapters.cloud.aws_delegate import AWSDelegate

class DelegationService:
    def __init__(self, provider: CloudProvider = CloudProvider.AWS):
        self.provider = provider
        # In a real app, this would be dependency injected based on config
        self.delegate: CloudDelegate = AWSDelegate()

    async def deploy_run(
        self,
        artifact_id: str,
        target_env: str = "dev",
        config: Dict[str, Any] = None
    ) -> DeploymentResult:
        """Start a deployment for a specific run or artifact."""
        if config is None:
            config = {}
            
        return await self.delegate.deploy_artifact(
            artifact_id=artifact_id,
            target_env=target_env,
            config=config
        )

    async def get_status(self, deployment_id: str) -> DeploymentResult:
        """Get status of a delegation operation."""
        return await self.delegate.get_deployment_status(deployment_id)

    async def list_cloud_resources(
        self,
        env: str,
        resource_type: Optional[ResourceType] = None
    ) -> List[CloudResource]:
        """List active cloud resources."""
        return await self.delegate.list_resources(env, resource_type)

    async def get_logs(self, resource_id: str) -> List[str]:
        """Get logs from a cloud resource."""
        return await self.delegate.get_resource_logs(resource_id)

    async def check_health(self) -> Dict[str, Any]:
        """Check provider health."""
        return await self.delegate.health_check()

    # --- Remote Runs ---

    async def trigger_run(self, config_dict: Dict[str, Any]) -> Any:
        # Convert dict to model
        from ..ports.cloud_delegate import RunConfig
        config = RunConfig(**config_dict)
        return await self.delegate.trigger_run(config)

    async def get_run_status(self, run_id: str) -> Any:
        return await self.delegate.get_run_status(run_id)

    async def list_runs(self, status: Optional[str] = None) -> List[Any]:
        # Convert string to enum
        from ..ports.cloud_delegate import RunStatus
        status_enum = RunStatus(status) if status else None
        return await self.delegate.list_runs(status_enum)

# Singleton instance
_delegation_service = DelegationService()

def get_delegation_service() -> DelegationService:
    return _delegation_service
