"""
Aegion Contracts - Architecture Decision Records.

Phase 5: Advanced Epistemics
Models for architecture timeline and decision tracking.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class ADRStatus(str, Enum):
    """Status of an Architecture Decision Record."""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class DecisionDriver(BaseModel):
    """A factor driving an architecture decision."""
    id: str
    description: str
    priority: str = "medium"  # high, medium, low


class ArchitectureDecision(BaseModel):
    """
    Architecture Decision Record (ADR) for tracking system decisions.
    """
    adr_id: str
    title: str
    status: ADRStatus = ADRStatus.PROPOSED
    
    # Context
    context: str
    drivers: List[DecisionDriver] = Field(default_factory=list)
    
    # Decision
    decision: str
    rationale: str
    
    # Consequences
    positive_consequences: List[str] = Field(default_factory=list)
    negative_consequences: List[str] = Field(default_factory=list)
    
    # Links
    supersedes: Optional[str] = None  # ADR ID
    superseded_by: Optional[str] = None
    related_decisions: List[str] = Field(default_factory=list)
    related_proposals: List[str] = Field(default_factory=list)
    
    # Metadata
    created_at: str
    created_by: str
    accepted_at: Optional[str] = None
    accepted_by: Optional[str] = None
    
    # Concurrency Control
    version: int = 0


class TimelineEvent(BaseModel):
    """
    An event in the architecture timeline.
    """
    event_id: str
    event_type: str  # "adr_created", "adr_accepted", "decision_made", "proposal_approved"
    timestamp: str
    title: str
    description: str
    
    # Links
    adr_id: Optional[str] = None
    decision_id: Optional[str] = None
    proposal_id: Optional[str] = None
    
    # Actor
    actor: str
    
    # Impact
    affected_modules: List[str] = Field(default_factory=list)


class ArchitectureTimeline(BaseModel):
    """
    Complete architecture timeline for a workspace.
    """
    workspace_id: str
    events: List[TimelineEvent] = Field(default_factory=list)
    current_adrs: List[str] = Field(default_factory=list)  # Active ADR IDs
    deprecated_adrs: List[str] = Field(default_factory=list)
