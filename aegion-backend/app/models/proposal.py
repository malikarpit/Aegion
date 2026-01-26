"""Proposal model - core governance entity."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class Proposal(BaseModel):
    """A governance proposal requiring approval."""
    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    workspace_id: str
    title: str
    description: str
    status: str = "pending"  # pending, approved, rejected
    created_at: datetime = Field(default_factory=datetime.utcnow)
    author_id: str = ""
