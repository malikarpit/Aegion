"""
Aegion Contracts - Rejection Artifact.

Phase 3: The Cognitive Plane
Learns from rejected proposals to improve future decision-making.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class RejectionReason(str, Enum):
    """Standard rejection reason categories."""
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    VIOLATES_INVARIANT = "violates_invariant"
    EXCEEDS_AUTHORITY = "exceeds_authority"
    DUPLICATE_PROPOSAL = "duplicate_proposal"
    POOR_REASONING = "poor_reasoning"
    SECURITY_CONCERN = "security_concern"
    PERFORMANCE_CONCERN = "performance_concern"
    SCOPE_CREEP = "scope_creep"
    OTHER = "other"


class LessonLearned(BaseModel):
    """Structured lesson extracted from rejection."""
    category: str  # e.g., "reasoning", "evidence", "scope"
    insight: str   # The actual lesson
    applies_to: List[str] = Field(default_factory=list)  # Module/context tags
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class RejectionArtifact(BaseModel):
    """
    Immutable record of a rejected proposal.
    
    Doctrine: "Every rejection is a learning opportunity."
    """
    rejection_id: str
    proposal_id: str
    proposal_title: str
    
    # Rejection context
    rejected_by: str  # User ID
    rejected_at: str  # ISO timestamp
    reason_category: RejectionReason
    reason_detail: str
    
    # Learning extraction
    lessons_learned: List[LessonLearned] = Field(default_factory=list)
    
    # Graph connections (for similarity/pattern detection)
    similar_proposals: List[str] = Field(default_factory=list)
    related_decisions: List[str] = Field(default_factory=list)
    
    # Metadata
    proposal_tier: str  # T0, T1, T2, T3
    workspace_id: str
    session_id: Optional[str] = None


class RejectionQuery(BaseModel):
    """Query parameters for rejection search."""
    reason_category: Optional[RejectionReason] = None
    workspace_id: Optional[str] = None
    rejected_by: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    limit: int = Field(default=50, le=200)


class RejectionStats(BaseModel):
    """Aggregate statistics for rejections."""
    total_rejections: int
    by_reason: dict  # {reason: count}
    by_tier: dict    # {tier: count}
    top_lessons: List[LessonLearned]
    rejection_rate: float  # rejections / total proposals
