"""
Aegion Praxis Service Layer.

Praxis is responsible for execution, evidence collection,
and causality tracking.

Phase 3 Components:
- ExecutionDependencyGraph: Tracks dependencies between sources and evidence
- StalenessDetector: Detects when evidence becomes stale
- SnapshotManager: Creates verifiable evidence snapshots
- ExecutionProfile: Defines how tests/builds execute
- ExecutionSandbox: Sandboxed execution with resource limits
"""

from .dependency_graph import ExecutionDependencyGraph
from .staleness_detector import StalenessDetector
from .snapshot_manager import SnapshotManager
from .execution_profile import (
    ExecutionProfile,
    ExecutionType,
    CaptureMode,
    get_preset_profiles,
    get_default_profile,
)
from .execution_sandbox import (
    ExecutionSandbox,
    ExecutionResult,
    ExecutionStatus,
    get_execution_sandbox,
)

__all__ = [
    "ExecutionDependencyGraph",
    "StalenessDetector", 
    "SnapshotManager",
    "ExecutionProfile",
    "ExecutionType",
    "CaptureMode",
    "get_preset_profiles",
    "get_default_profile",
    "ExecutionSandbox",
    "ExecutionResult",
    "ExecutionStatus",
    "get_execution_sandbox",
]
