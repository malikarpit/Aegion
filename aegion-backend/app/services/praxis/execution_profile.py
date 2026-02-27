"""
Aegion Execution Profiles.

Defines how to execute tests/builds in a controlled environment.

Phase 3 MVP: Local execution with snapshot capture.
Phase 4+: Container-based sandboxing (future).
"""

from typing import Literal, Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class ExecutionType(str, Enum):
    """Type of execution environment."""
    LOCAL = "local"           # Run on local machine
    CONTAINER = "container"   # Run in Docker/container
    REMOTE = "remote"         # Run on remote executor


class CaptureMode(str, Enum):
    """What to capture during execution."""
    NONE = "none"
    MINIMAL = "minimal"       # Output only
    STANDARD = "standard"     # Input + Output
    COMPREHENSIVE = "comprehensive"  # Input + Output + Environment


class ExecutionProfile(BaseModel):
    """
    Defines how to execute tests/builds in a controlled environment.
    
    Profile determines:
    - Where execution happens (local/container/remote)
    - What gets captured for reproducibility
    - Timeout and resource limits
    """
    
    # Identity
    profile_id: str = Field(..., description="Unique profile identifier")
    name: str = Field(..., description="Human-readable name")
    description: Optional[str] = Field(None, description="Profile description")
    
    # Execution settings
    execution_type: ExecutionType = Field(
        default=ExecutionType.LOCAL,
        description="Where to execute"
    )
    timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Maximum execution time"
    )
    working_directory: Optional[str] = Field(
        None, description="Working directory for execution"
    )
    
    # Capture settings
    capture_mode: CaptureMode = Field(
        default=CaptureMode.STANDARD,
        description="What to capture"
    )
    capture_inputs: bool = Field(
        default=True,
        description="Capture input files as snapshots"
    )
    capture_outputs: bool = Field(
        default=True,
        description="Capture execution outputs"
    )
    capture_environment: bool = Field(
        default=True,
        description="Capture environment (Python version, deps, etc.)"
    )
    
    # File patterns
    input_patterns: List[str] = Field(
        default_factory=lambda: ["*.py", "*.json", "*.yaml"],
        description="Glob patterns for input files to capture"
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: ["__pycache__/**", "*.pyc", ".git/**"],
        description="Glob patterns to exclude"
    )
    
    # Resource limits (for container/remote)
    memory_limit_mb: Optional[int] = Field(
        None, description="Memory limit in MB (container only)"
    )
    cpu_limit: Optional[float] = Field(
        None, description="CPU limit (container only)"
    )
    allow_network_egress: bool = Field(
        default=False,
        description="Allow network access (default-deny)"
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional profile metadata"
    )
    
    model_config = ConfigDict(frozen=True)


# ========== Preset Profiles ==========

PROFILE_FAST = ExecutionProfile(
    profile_id="preset-fast",
    name="Fast (No Capture)",
    description="Quick execution without snapshots",
    capture_mode=CaptureMode.NONE,
    capture_inputs=False,
    capture_outputs=False,
    capture_environment=False,
    timeout_seconds=60
)

PROFILE_STANDARD = ExecutionProfile(
    profile_id="preset-standard",
    name="Standard",
    description="Standard execution with input/output capture",
    capture_mode=CaptureMode.STANDARD,
    capture_inputs=True,
    capture_outputs=True,
    capture_environment=False,
    timeout_seconds=300
)

PROFILE_COMPREHENSIVE = ExecutionProfile(
    profile_id="preset-comprehensive",
    name="Comprehensive (Full Reproducibility)",
    description="Full capture for reproducible evidence",
    capture_mode=CaptureMode.COMPREHENSIVE,
    capture_inputs=True,
    capture_outputs=True,
    capture_environment=True,
    timeout_seconds=600
)


def get_preset_profiles() -> Dict[str, ExecutionProfile]:
    """Get all preset execution profiles."""
    return {
        "fast": PROFILE_FAST,
        "standard": PROFILE_STANDARD,
        "comprehensive": PROFILE_COMPREHENSIVE
    }


def get_default_profile() -> ExecutionProfile:
    """Get the default execution profile."""
    return PROFILE_STANDARD
