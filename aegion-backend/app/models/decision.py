"""
Aegion Data Models - Decision.

The core Decision model that flows through governance.
Decisions are immutable once approved.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

from ..contracts.decision_intent import DecisionTier, DecisionIntent
from ..contracts.uncertainty_level import UncertaintyDeclaration, UncertaintyLevel


class DecisionStatus(str, Enum):
    """Status of a decision."""
    DRAFT = "draft"          # Being composed
    PENDING = "pending"      # Awaiting approval
    APPROVED = "approved"    # Approved, ready to apply
    APPLIED = "applied"      # Changes applied
    REJECTED = "rejected"    # Rejected by approver
    SUPERSEDED = "superseded"  # Replaced by newer decision


class VisibilityLabel(str, Enum):
    """
    Who created/approved this decision.
    From Explainability Doctrine.
    """
    AI_SUGGESTION = "ai_suggestion"    # 🤖 AI proposed
    HUMAN_AUTHORED = "human_authored"  # ✋ Human created
    GOVERNED = "governed"              # 🏛️ Approved through governance


class Decision(BaseModel):
    """
    A governed decision.
    Immutable once approved.
    """
    # Identity
    decision_id: str = Field(..., description="Unique decision ID")
    proposal_id: str = Field(..., description="Source proposal ID")
    session_id: str = Field(..., description="Session where decision was made")
    workspace_id: str = Field(..., description="Workspace")
    
    # Classification
    tier: DecisionTier
    status: DecisionStatus = Field(default=DecisionStatus.DRAFT)
    
    # Content
    title: str
    description: str
    
    # Scope
    affected_files: List[str] = Field(default_factory=list)
    affected_modules: List[str] = Field(default_factory=list)
    
    # Visibility
    visibility_label: VisibilityLabel = Field(default=VisibilityLabel.AI_SUGGESTION)
    
    # Provenance
    proposed_by: str = Field(..., description="User who proposed")
    proposed_at: datetime
    approved_by: Optional[str] = Field(None, description="User who approved")
    approved_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    
    # Evidence
    evidence_ids: List[str] = Field(default_factory=list)
    
    # Supersession
    supersedes_id: Optional[str] = None
    superseded_by_id: Optional[str] = None
    
    # Intent link
    intent: Optional[DecisionIntent] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "decision_id": "dec-123",
                "proposal_id": "prop-456",
                "session_id": "sess-789",
                "workspace_id": "ws-abc",
                "tier": "T1",
                "status": "approved",
                "title": "Add user authentication",
                "description": "Implement JWT validation middleware",
                "visibility_label": "human_authored",
                "proposed_by": "user-001",
                "proposed_at": "2026-02-09T10:00:00Z",
                "approved_by": "user-002",
                "approved_at": "2026-02-09T11:00:00Z"
            }
        }
    )


class Proposal(BaseModel):
    """
    A proposal awaiting governance.
    Can be promoted to Decision upon approval.
    """
    # Identity
    proposal_id: str
    session_id: str
    workspace_id: str
    
    # Source
    origin: str  # "human" | "ai_child" | "ai_parent"
    proposed_by: str
    proposed_at: datetime
    
    # Classification
    tier: DecisionTier
    status: str = "draft"  # draft | pending | approved | rejected
    
    # Content
    title: str
    description: str
    intent: DecisionIntent
    
    # Evidence
    evidence_ids: List[str] = Field(default_factory=list)

    # Uncertainty (H-3)
    uncertainty: Optional[UncertaintyDeclaration] = None

    # Exploration label
    exploration_stage: str = "exploration"  # exploration | proposed | governed
    
    def to_decision(
        self,
        approver_id: str,
        visibility_label: VisibilityLabel
    ) -> Decision:
        """Convert approved proposal to decision."""
        from datetime import datetime, timezone
        
        return Decision(
            decision_id=f"dec-{self.proposal_id}",
            proposal_id=self.proposal_id,
            session_id=self.session_id,
            workspace_id=self.workspace_id,
            tier=self.tier,
            status=DecisionStatus.APPROVED,
            title=self.title,
            description=self.description,
            affected_files=self.intent.affected_files,
            affected_modules=self.intent.affected_modules,
            visibility_label=visibility_label,
            proposed_by=self.proposed_by,
            proposed_at=self.proposed_at,
            approved_by=approver_id,
            approved_at=datetime.now(timezone.utc),
            evidence_ids=self.evidence_ids,
            intent=self.intent
        )
