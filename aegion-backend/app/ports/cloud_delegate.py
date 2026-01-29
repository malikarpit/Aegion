"""
Aegion Cloud Delegate Port - Interface for Cloud Operations.

Phase 35: Cloud Delegation (AG-017)
Abstracts cloud provider operations for deployment, status checks, and resource management.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class CloudProvider(str, Enum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    LOCAL = "local"


class ResourceType(str, Enum):
    COMPUTE = "compute"
    STORAGE = "storage"
    DATABASE = "database"
    QUEUE = "queue"
    FUNCTION = "function"


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK_IN_PROGRESS = "rollback_in_progress"
    ROLLED_BACK = "rolled_back"


class CloudResource(BaseModel):
    resource_id: str
    name: str
    type: ResourceType
    provider: CloudProvider
    region: str
    status: str
    metadata: Dict[str, Any] = {}
    created_at: datetime


class DeploymentResult(BaseModel):
    deployment_id: str
    status: DeploymentStatus
    resources: List[CloudResource]
    logs: List[str]
    error: Optional[str] = None
    completed_at: Optional[datetime] = None





class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunConfig(BaseModel):
    command: str
    image: str = "aegion-runner:latest"
    env_vars: Dict[str, str] = {}
    timeout_seconds: int = 3600
    resource_size: str = "medium"


class RemoteRun(BaseModel):
    run_id: str
    config: RunConfig
    status: RunStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    resource_id: Optional[str] = None
    exit_code: Optional[int] = None
    logs_url: Optional[str] = None


class CloudDelegate(ABC):
    """
    Abstract interface for Cloud Delegation.
    
    Doctrine: "The system extends beyond the local capabilities."
    """

    @abstractmethod
    async def deploy_artifact(
        self,
        artifact_id: str,
        target_env: str,
        config: Dict[str, Any]
    ) -> DeploymentResult:
        """Deploy an artifact to the target environment."""
        pass

    @abstractmethod
    async def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        """Get status of a specific deployment."""
        pass

    @abstractmethod
    async def list_resources(
        self,
        env: str,
        resource_type: Optional[ResourceType] = None
    ) -> List[CloudResource]:
        """List managed cloud resources."""
        pass

    @abstractmethod
    async def get_resource_logs(
        self,
        resource_id: str,
        lines: int = 100
    ) -> List[str]:
        """Get logs from a specific resource."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check connection to cloud provider."""
        pass

    @abstractmethod
    async def trigger_run(self, config: RunConfig) -> RemoteRun:
        """Trigger a remote execution."""
        pass

    @abstractmethod
    async def get_run_status(self, run_id: str) -> RemoteRun:
        """Get status of a remote run."""
        pass

    @abstractmethod
    async def list_runs(self, status: Optional[RunStatus] = None) -> List[RemoteRun]:
        """List remote runs."""
        pass
