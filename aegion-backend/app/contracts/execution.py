"""
Aegion Contracts - Execution Descriptors.

Phase 4: Execution & Resilience
Models for Praxis execution control and sandboxing.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ActionType(str, Enum):
    """Types of executable actions."""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    SHELL_COMMAND = "shell_command"
    API_CALL = "api_call"
    DB_READ = "db_read"
    DB_WRITE = "db_write"
    NETWORK_REQUEST = "network_request"
    CODE_EXECUTION = "code_execution"


class RiskLevel(str, Enum):
    """Risk classification for actions."""
    SAFE = "safe"           # No side effects, read-only
    MODERATE = "moderate"   # Reversible side effects
    DANGEROUS = "dangerous" # Irreversible or system-wide
    CRITICAL = "critical"   # Requires human approval


class ExecutionDescriptor(BaseModel):
    """
    Describes an executable action with metadata for governance.
    """
    descriptor_id: str
    action_type: ActionType
    name: str
    description: str
    
    # Risk classification
    risk_level: RiskLevel = RiskLevel.MODERATE
    requires_sandbox: bool = False
    requires_approval: bool = False
    
    # Constraints
    timeout_ms: int = Field(default=30000, ge=100, le=300000)
    allowed_contexts: List[str] = Field(default_factory=lambda: ["*"])
    denied_contexts: List[str] = Field(default_factory=list)
    
    # Resource limits
    max_memory_mb: Optional[int] = None
    max_file_size_bytes: Optional[int] = None
    
    # Metadata
    created_at: str
    created_by: str
    version: int = 1


class SandboxConfig(BaseModel):
    """
    Configuration for sandboxed execution.
    """
    isolate_filesystem: bool = True
    isolate_network: bool = True
    capture_stdout: bool = True
    capture_stderr: bool = True
    working_directory: Optional[str] = None
    environment_vars: Dict[str, str] = Field(default_factory=dict)


class ExecutionRequest(BaseModel):
    """
    Request to execute an action.
    """
    request_id: str
    descriptor_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    requested_by: str
    requested_at: str


class ExecutionResult(BaseModel):
    """
    Result of an execution.
    """
    request_id: str
    descriptor_id: str
    status: str  # "success", "failed", "timeout", "rejected"
    
    # Output
    output: Optional[str] = None
    error: Optional[str] = None
    return_code: Optional[int] = None
    
    # Timing
    started_at: str
    completed_at: str
    duration_ms: int
    
    # Sandbox info
    was_sandboxed: bool = False
    sandbox_violations: List[str] = Field(default_factory=list)
