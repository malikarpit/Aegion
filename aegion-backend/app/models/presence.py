"""
Aegion Data Models - Presence.

Real-time presence tracking for collaboration sessions.
"""

from typing import Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class PresenceStatus(str, Enum):
    """User presence status."""
    ONLINE = "online"
    AWAY = "away"
    BUSY = "busy"
    OFFLINE = "offline"


class UserPresence(BaseModel):
    """A user's presence in a workspace."""

    user_id: str = Field(...)
    workspace_id: str = Field(...)
    session_id: Optional[str] = None

    # Presence state
    status: PresenceStatus = Field(default=PresenceStatus.ONLINE)
    active_file: Optional[str] = Field(None, description="Currently open file")
    cursor_line: Optional[int] = Field(None, description="Current cursor line")

    # Timestamps
    connected_at: datetime
    last_heartbeat: datetime
