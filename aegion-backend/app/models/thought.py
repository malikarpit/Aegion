"""
Aegion Thought-Commit Protocol Models.

Defines the schema for linking reasoning ("Why") to code ("What").
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from ..contracts.thought import ThoughtState, ThoughtLinkType
from ..contracts.adr import DecisionDriver


class ThoughtLink(BaseModel):
    """
    A specific link from a Thought Artifact to another entity.
    """
    link_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: ThoughtLinkType
    target_id: str = Field(..., description="ID of the linked entity (commit SHA, proposal ID, etc.)")
    target_type: str = Field(..., description="Type of target: 'commit', 'proposal', 'decision', 'evidence'")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ThoughtCommit(BaseModel):
    """
    The core artifact representing the reasoning behind a set of changes.
    Immutable once SEALED.
    """
    thought_id: str = Field(default_factory=lambda: f"tht-{uuid.uuid4().hex[:8]}")
    workspace_id: str
    session_id: str
    
    # Core Reasoning
    title: str = Field(..., description="Short summary of the 'Why'")
    rationale: str = Field(..., description="Detailed explanation of the change driver")
    alternatives: List[str] = Field(default_factory=list, description="Other approaches considered")
    
    # Relationships
    links: List[ThoughtLink] = Field(default_factory=list)
    
    # Metadata
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sealed_at: Optional[datetime] = None
    
    # State
    state: ThoughtState = ThoughtState.DRAFT
    content_hash: Optional[str] = Field(None, description="SHA-256 hash of sealed content")
    
    # Governance Context (Snapshotted from session)
    tier: Optional[str] = "T0"
    drivers: List[DecisionDriver] = Field(default_factory=list)


# --- API Request Models ---

class CreateThoughtRequest(BaseModel):
    workspace_id: str
    session_id: str
    title: str
    rationale: str
    proposal_id: Optional[str] = None  # Syntactic sugar to auto-create a DERIVES_FROM link
    decision_id: Optional[str] = None  # Syntactic sugar to auto-create a DERIVES_FROM link


class UpdateThoughtRequest(BaseModel):
    title: Optional[str] = None
    rationale: Optional[str] = None
    alternatives: Optional[List[str]] = None
    add_links: Optional[List[ThoughtLink]] = None
    remove_link_ids: Optional[List[str]] = None


class SealThoughtRequest(BaseModel):
    """
    Request to finalize a thought artifact.
    Must include a content hash for integrity verification if provided by client.
    """
    content_hash: Optional[str] = None


class LinkCommitRequest(BaseModel):
    """
    Link a specific Git commit to this thought artifact.
    """
    commit_sha: str
    repo_path: Optional[str] = None
    branch: Optional[str] = None
