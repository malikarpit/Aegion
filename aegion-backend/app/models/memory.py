"""
Aegion Data Models - Memory.

Workspace-scoped memory entries for storing knowledge, decisions, and patterns.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class MemoryScope(str, Enum):
    """Scope level for a memory entry."""
    ORGANIZATION = "organization"
    REPOSITORY = "repository"
    SESSION = "session"


class MemoryEntry(BaseModel):
    """A knowledge memory entry."""

    # Identity
    memory_id: str = Field(..., description="Unique memory ID")

    # Content
    key: str = Field(..., description="Memory key (e.g., 'auth_pattern', 'naming_convention')")
    value: Any = Field(..., description="Memory value (string, dict, list, etc.)")

    # Scope
    scope: MemoryScope = Field(default=MemoryScope.REPOSITORY)
    scope_id: str = Field("", description="Org/repo/session ID for scoping")

    # Metadata
    tags: List[str] = Field(default_factory=list)
    created_by: str = Field(..., description="User who created the entry")
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Optional context
    source: Optional[str] = Field(None, description="Where this memory came from")
    confidence: float = Field(1.0, description="Confidence score 0.0-1.0")

    # Immutability / Supersession
    superseded: bool = Field(False, description="Whether this entry has been superseded")
    superseded_by: Optional[str] = Field(None, description="ID of the entry that superseded this one")
    superseded_at: Optional[datetime] = Field(None, description="When this entry was superseded")
    supersession_reason: Optional[str] = Field(None, description="Reason for supersession")
