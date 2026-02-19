from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid
from ..core.time import TimeAuthority

class Session(BaseModel):
    """
    User Workflow Session.
    
    Represents a continuous period of work by a user in a workspace.
    """
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    owner_id: str
    workspace_id: str
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: TimeAuthority.now_dt())
    last_activity_at: datetime = Field(default_factory=lambda: TimeAuthority.now_dt())
    closed_at: Optional[datetime] = None
    distilled_at: Optional[datetime] = None
    context_hash: Optional[str] = None
    reasoning_phase: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Compatibility helper for existing adapters."""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Compatibility helper for existing adapters."""
        return cls.model_validate(data)
