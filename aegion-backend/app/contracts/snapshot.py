"""
Aegion Data Contracts - Evidence Snapshot.

Verifiable Evidence Snapshots for content-addressable storage of
execution inputs and outputs.

Doctrine: "Decision A is supported by (Snapshot Hash X + Test Result Y)."
All evidence must be reproducible from its snapshots.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import hashlib
import json


class SnapshotType(str, Enum):
    """Type of snapshot content."""
    INPUT = "input"         # Inputs to execution (source files, configs)
    OUTPUT = "output"       # Outputs from execution (test results, logs)
    ENVIRONMENT = "env"     # Execution environment (versions, deps)


class SnapshotStatus(str, Enum):
    """Status of a snapshot."""
    PENDING = "pending"     # Being captured
    COMPLETE = "complete"   # Successfully captured
    FAILED = "failed"       # Capture failed
    VERIFIED = "verified"   # Verified intact


class FileSnapshot(BaseModel):
    """
    Snapshot of a single file's content.
    Content-addressed by SHA-256 hash.
    """
    file_path: str = Field(..., description="Original file path")
    content_hash: str = Field(..., description="SHA-256 hash of file content")
    size_bytes: int = Field(..., description="File size in bytes")
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(frozen=True)


class EnvironmentSnapshot(BaseModel):
    """
    Snapshot of execution environment.
    Captures versions, dependencies, and settings.
    """
    # Runtime
    python_version: Optional[str] = None
    node_version: Optional[str] = None
    
    # Dependencies
    dependencies: Dict[str, str] = Field(
        default_factory=dict,
        description="Package name -> version mapping"
    )
    
    # Environment variables (filtered for security)
    environment_vars: Dict[str, str] = Field(
        default_factory=dict,
        description="Relevant environment variables"
    )
    
    # System
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    
    # Hash of all environment data
    content_hash: str = Field(..., description="SHA-256 hash of environment data")
    
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(frozen=True)


class EvidenceSnapshot(BaseModel):
    """
    Immutable snapshot of inputs/outputs for an execution.
    Content-addressed by SHA-256 hash.
    
    Doctrine: "Decision A is supported by (Snapshot Hash X + Test Result Y)."
    
    This enables:
    - Reproducibility: Re-run with exact same inputs
    - Verification: Confirm evidence hasn't been tampered with
    - Staleness detection: Know when inputs have changed
    """
    # Identity
    snapshot_id: str = Field(..., description="Content hash of snapshot manifest")
    evidence_id: str = Field(..., description="Parent evidence ID")
    
    # Type
    snapshot_type: SnapshotType
    status: SnapshotStatus = SnapshotStatus.COMPLETE
    
    # Content (depending on type)
    # For INPUT: list of file snapshots
    file_snapshots: List[FileSnapshot] = Field(
        default_factory=list,
        description="Snapshots of individual files"
    )
    
    # For OUTPUT: raw output content hash
    output_hash: Optional[str] = Field(
        None, description="SHA-256 hash of output content"
    )
    output_size_bytes: Optional[int] = Field(
        None, description="Size of output in bytes"
    )
    
    # For ENVIRONMENT: environment snapshot
    environment: Optional[EnvironmentSnapshot] = None
    
    # Storage
    storage_key: str = Field(..., description="Key in blob storage")
    
    # Timing
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Verification
    verified_at: Optional[datetime] = Field(
        None, description="Last verification time"
    )
    is_verified: bool = Field(
        default=False, description="Has integrity been verified?"
    )
    
    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional snapshot metadata"
    )
    
    model_config = ConfigDict(frozen=True)
    
    @property
    def total_files(self) -> int:
        """Number of files in this snapshot."""
        return len(self.file_snapshots)
    
    @property
    def total_size_bytes(self) -> int:
        """Total size of all content in this snapshot."""
        file_size = sum(f.size_bytes for f in self.file_snapshots)
        output_size = self.output_size_bytes or 0
        return file_size + output_size


class SnapshotManifest(BaseModel):
    """
    Manifest describing all snapshots for a piece of evidence.
    Used to verify evidence reproducibility.
    """
    evidence_id: str = Field(..., description="Evidence this manifest describes")
    
    # Snapshots by type
    input_snapshot_ids: List[str] = Field(
        default_factory=list,
        description="IDs of input snapshots"
    )
    output_snapshot_ids: List[str] = Field(
        default_factory=list,
        description="IDs of output snapshots"
    )
    environment_snapshot_id: Optional[str] = Field(
        None, description="ID of environment snapshot"
    )
    
    # Composite hash
    manifest_hash: str = Field(
        ..., description="SHA-256 hash of all snapshot IDs combined"
    )
    
    # Reproducibility
    is_reproducible: bool = Field(
        default=False,
        description="Can this evidence be reproduced from snapshots?"
    )
    reproducibility_notes: Optional[str] = Field(
        None, description="Notes on reproducibility"
    )
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(frozen=True)


def compute_snapshot_id(evidence_id: str, snapshot_type: SnapshotType, content_hash: str) -> str:
    """
    Compute a unique snapshot ID based on evidence, type, and content.
    """
    data = f"{evidence_id}:{snapshot_type.value}:{content_hash}"
    return hashlib.sha256(data.encode()).hexdigest()


def compute_manifest_hash(
    input_ids: List[str],
    output_ids: List[str],
    env_id: Optional[str]
) -> str:
    """
    Compute a manifest hash from all snapshot IDs.
    """
    all_ids = sorted(input_ids) + sorted(output_ids)
    if env_id:
        all_ids.append(env_id)
    data = json.dumps(all_ids, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


class SnapshotCaptureRequest(BaseModel):
    """
    Request to capture a snapshot for evidence.
    """
    evidence_id: str
    snapshot_type: SnapshotType
    
    # For INPUT type
    file_paths: List[str] = Field(
        default_factory=list,
        description="Paths to files to snapshot"
    )
    
    # For OUTPUT type
    output_data: Optional[bytes] = Field(
        None, description="Raw output data to snapshot"
    )
    
    # For ENVIRONMENT type
    capture_dependencies: bool = Field(
        default=True, description="Capture package dependencies"
    )
    capture_env_vars: List[str] = Field(
        default_factory=list,
        description="Environment variable names to capture"
    )
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
