"""
Aegion Collaboration Models.

Models for real-time collaboration, session ownership, and handoffs.

Doctrine: "Collaboration is governance-aware."
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

# Import workspace primitives to ensure consistency
from .workspace import WorkspaceRole


class OwnershipStatus(str, Enum):
    """Status of session ownership."""
    CLAIMED = "claimed"      # Active owner
    RELEASED = "released"    # No active owner (free to claim)
    PENDING = "pending"      # Transfer pending acceptance


class TransferReason(str, Enum):
    """Reason for ownership transfer."""
    HANDOFF = "handoff"          # Scheduled handoff
    INTERRUPTION = "interruption" # Owner had to leave
    REQUESTED = "requested"      # Another user requested it
    FORCE = "force"             # Admin forced transfer


class OwnershipTransfer(BaseModel):
    """Record of an ownership transfer event."""
    transfer_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_user_id: Optional[str] = None
    to_user_id: str
    reason: TransferReason
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "completed"  # completed, rejected, cancelled


class SessionOwnership(BaseModel):
    """
    Tracks the 'con' (control) of a collaboration session.
    
    Only the owner can commit changes or finalize decisions.
    """
    session_id: str
    workspace_id: str
    
    # Current State
    owner_id: Optional[str] = None
    status: OwnershipStatus = Field(default=OwnershipStatus.RELEASED)
    
    # Valid until (heartbeat enforcement)
    expires_at: Optional[datetime] = None
    
    # Pending Transfer (if any)
    pending_transfer_to: Optional[str] = None
    
    # History
    history: List[OwnershipTransfer] = Field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

