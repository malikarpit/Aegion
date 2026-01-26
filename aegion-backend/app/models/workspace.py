"""
Aegion Workspace Model.

Workspace represents a collaborative environment with team membership.

Doctrine: "Workspaces are governance boundaries."
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class WorkspaceRole(str, Enum):
    """Role within a workspace."""
    OWNER = "owner"          # Full control
    ADMIN = "admin"          # Can manage members, approve T2
    ARCHITECT = "architect"  # Can approve T1
    DEVELOPER = "developer"  # Can propose, execute
    VIEWER = "viewer"        # Read-only


class WorkspaceMember(BaseModel):
    """Member of a workspace with role."""
    user_id: str
    role: WorkspaceRole
    display_name: Optional[str] = None
    email: Optional[str] = None
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    invited_by: Optional[str] = None
    
    model_config = ConfigDict(frozen=True)


class WorkspaceInvite(BaseModel):
    """Pending invitation to workspace."""
    invite_id: str
    workspace_id: str
    email: str
    role: WorkspaceRole
    invited_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    accepted: bool = False
    accepted_at: Optional[datetime] = None


class Workspace(BaseModel):
    """
    Workspace with team collaboration.
    
    Workspaces define:
    - Team membership and roles
    - Governance policy (can override defaults)
    - Session and proposal scope
    """
    workspace_id: str = Field(..., description="Unique workspace ID")
    name: str = Field(..., description="Workspace display name")
    description: Optional[str] = None
    
    # Ownership
    owner_id: str = Field(..., description="User who owns the workspace")
    
    # Governance
    governance_policy_id: str = Field(
        default="genesis",
        description="Policy governing this workspace"
    )
    
    # Settings
    settings: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkspaceWithMembers(Workspace):
    """Workspace with loaded members."""
    members: List[WorkspaceMember] = Field(default_factory=list)
    
    @property
    def member_count(self) -> int:
        return len(self.members)
    
    def get_member(self, user_id: str) -> Optional[WorkspaceMember]:
        """Get member by user ID."""
        for member in self.members:
            if member.user_id == user_id:
                return member
        return None
    
    def has_role(self, user_id: str, role: WorkspaceRole) -> bool:
        """Check if user has specific role."""
        member = self.get_member(user_id)
        return member is not None and member.role == role
    
    def can_approve_tier(self, user_id: str, tier: str) -> bool:
        """Check if user can approve given tier."""
        member = self.get_member(user_id)
        if member is None:
            return False
        
        role = member.role
        
        if tier == "T0":
            return True  # Auto-approved
        if tier == "T1":
            return role in [WorkspaceRole.ARCHITECT, WorkspaceRole.ADMIN, WorkspaceRole.OWNER]
        if tier in ["T2", "T3"]:
            return role in [WorkspaceRole.ADMIN, WorkspaceRole.OWNER]
        
        return False


class WorkspaceActivity(BaseModel):
    """Activity event in workspace."""
    activity_id: str
    workspace_id: str
    event_type: str
    actor_id: str
    target_type: Optional[str] = None  # proposal, decision, member
    target_id: Optional[str] = None
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
