"""
Aegion Data Models - Session.

The core Session model for tracking user work sessions.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Status of a session."""
    ACTIVE = "active"        # Currently active
    CLOSED = "closed"        # Closed, awaiting distillation
    DISTILLED = "distilled"  # Artifacts extracted
    EXPIRED = "expired"      # Expired due to inactivity


class ExplorationLabel(str, Enum):
    """
    Exploration stage indicator.
    From Reasoning Phase Doctrine.
    """
    EXPLORATION = "exploration"  # 🧠 Still exploring
    PROPOSED = "proposed"        # 🏗️ Proposed for governance
    GOVERNED = "governed"        # 🏛️ Approved and governed


class Session(BaseModel):
    """A user work session."""
    
    # Identity
    session_id: str = Field(..., description="Unique session ID")
    owner_id: str = Field(..., description="User who owns the session")
    workspace_id: str = Field(..., description="Workspace")
    
    # Status
    status: SessionStatus = Field(default=SessionStatus.ACTIVE)
    
    # Timing
    created_at: datetime
    last_activity_at: datetime
    closed_at: Optional[datetime] = None
    distilled_at: Optional[datetime] = None
    
    # Context
    context_hash: Optional[str] = None
    context_token_count: int = 0
    
    # Reasoning phase tracking
    current_phase: ExplorationLabel = Field(default=ExplorationLabel.EXPLORATION)
    reasoning_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Metrics
    decision_count: int = 0
    evidence_count: int = 0
    ai_invocation_count: int = 0
    
    # Artifact reference (after distillation)
    artifact_id: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class User(BaseModel):
    """A user in the system."""
    
    # Identity
    user_id: str
    email: str
    display_name: Optional[str] = None
    
    # Status
    email_verified: bool = False
    
    # Workspaces
    workspace_ids: List[str] = Field(default_factory=list)
    default_workspace_id: Optional[str] = None
    
    # Preferences
    preferences: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime
    last_login_at: Optional[datetime] = None


class Workspace(BaseModel):
    """A workspace for team collaboration."""
    
    # Identity
    workspace_id: str
    name: str
    description: Optional[str] = None
    
    # Ownership
    owner_id: str
    
    # Members
    member_ids: List[str] = Field(default_factory=list)
    
    # Settings
    settings: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime
