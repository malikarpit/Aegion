"""
Aegion Data Models - Checkpoint.

Checkpoint and rollback models for session state snapshots.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class CheckpointStatus(str, Enum):
    """Status of a checkpoint."""
    ACTIVE = "active"
    ROLLED_BACK = "rolled_back"
    EXPIRED = "expired"


class Checkpoint(BaseModel):
    """A session state checkpoint."""

    # Identity
    checkpoint_id: str = Field(..., description="Unique checkpoint ID")
    session_id: str = Field(..., description="Session this checkpoint belongs to")

    # Creator
    created_by: str = Field(..., description="User who created the checkpoint")

    # Content
    label: str = Field("", description="Human-readable label")
    reason: str = Field("manual", description="Reason: manual, interval, pre_rollback")
    state_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Session state at checkpoint time")

    # Status
    status: CheckpointStatus = Field(default=CheckpointStatus.ACTIVE)

    # Git integration (#6)
    git_commit_sha: Optional[str] = Field(None, description="Shadow git commit SHA")
    trigger_action: Optional[str] = Field(None, description="Action that triggered auto-checkpoint")

    # Timing
    created_at: datetime
    expires_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Governance links
    evidence_ids: List[str] = Field(default_factory=list, description="Linked evidence IDs")
    decision_ids: List[str] = Field(default_factory=list, description="Linked decision IDs")


class RollbackResult(BaseModel):
    """Result of a rollback operation."""
    checkpoint_id: str
    session_id: str
    rolled_back_at: str
    previous_state_keys: int = Field(0, description="Number of state keys restored")
    restored_state: Optional[Dict[str, Any]] = Field(None, description="State snapshot that was restored")
    message: str = "Rollback completed successfully"
