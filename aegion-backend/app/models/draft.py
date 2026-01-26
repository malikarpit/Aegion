"""
Aegion Data Models - Session Drafts.

DOCTRINE:
- Drafts are MUTABLE and EPHEMERAL.
- They allow "pausing" work without committing to immutable history.
- They are DESTROYED upon session distillation (commit).
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class SessionDraft(BaseModel):
    """
    Mutable state of an active but paused session.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "draft_id": "draft-123",
                "user_id": "user-456",
                "workspace_id": "ws-789",
                "title": "Refactoring Auth - Draft",
                "context_data": {"active_file": "auth.py", "scratchpad": "Need to check JWT expiry"},
                "conversation_history": [{"role": "user", "content": "Let's refill the coffee"}],
                "created_at": "2026-02-10T10:00:00Z",
                "updated_at": "2026-02-10T10:30:00Z"
            }
        }
    )
    
    draft_id: str = Field(..., description="Unique draft ID")
    user_id: str = Field(..., description="Owner of the draft")
    workspace_id: str = Field(..., description="Workspace context")
    
    # Content (Mutable)
    title: str = "Untitled Session"
    context_data: Dict[str, Any] = Field(default_factory=dict, description="Raw context/memory dump")
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list, description="Recent messages")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)

