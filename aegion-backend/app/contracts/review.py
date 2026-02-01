"""
Aegion Review & Voting Contracts.

For multi-user proposal review workflow.

Doctrine: "Approval is consensus, not authority."
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class ReviewVerdict(str, Enum):
    """Verdict for a proposal review."""
    APPROVE = "approve"                # Approve the proposal
    REQUEST_CHANGES = "request_changes"  # Request modifications
    COMMENT = "comment"                # Comment only, no vote
    REJECT = "reject"                  # Reject the proposal


class ProposalReview(BaseModel):
    """
    Individual review on a proposal.
    
    Reviews are immutable once submitted.
    """
    review_id: str = Field(..., description="Unique review ID")
    proposal_id: str = Field(..., description="Proposal being reviewed")
    reviewer_id: str = Field(..., description="User submitting review")
    
    # Verdict
    verdict: ReviewVerdict
    
    # Content
    comments: str = Field(..., description="Review comments")
    inline_comments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Line-specific comments"
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(frozen=True)


class ApprovalVote(BaseModel):
    """
    Approval vote for a proposal.
    
    Separate from review - this is the actual vote.
    """
    vote_id: str
    proposal_id: str
    voter_id: str
    vote: bool  # True = approve, False = reject
    justification: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(frozen=True)


class QuorumRequirement(BaseModel):
    """
    Quorum requirements for proposal approval.
    
    Defined per tier.
    """
    tier: str
    minimum_approvers: int = 1
    require_owner_approval: bool = False
    require_architect_approval: bool = False
    timeout_hours: int = 24  # Auto-timeout if not met


class ProposalApprovalStatus(BaseModel):
    """
    Aggregated approval status for a proposal.
    """
    proposal_id: str
    tier: str
    
    # Requirements
    quorum: QuorumRequirement
    
    # Current state
    total_reviews: int = 0
    approve_count: int = 0
    reject_count: int = 0
    request_changes_count: int = 0
    
    # Status
    quorum_met: bool = False
    blocked: bool = False  # Has rejections or contradictory evidence
    
    # Calculated
    @property
    def approval_percentage(self) -> float:
        if self.total_reviews == 0:
            return 0.0
        return (self.approve_count / self.total_reviews) * 100
    
    @property
    def can_approve(self) -> bool:
        """Can this proposal be approved?"""
        return (
            self.quorum_met and
            not self.blocked and
            self.reject_count == 0 and
            self.request_changes_count == 0
        )


# Default quorum requirements per tier
DEFAULT_QUORUM = {
    "T0": QuorumRequirement(tier="T0", minimum_approvers=0),  # Auto
    "T1": QuorumRequirement(tier="T1", minimum_approvers=1),
    "T2": QuorumRequirement(
        tier="T2",
        minimum_approvers=2,
        require_architect_approval=True
    ),
    "T3": QuorumRequirement(
        tier="T3",
        minimum_approvers=3,
        require_owner_approval=True,
        require_architect_approval=True
    ),
}
