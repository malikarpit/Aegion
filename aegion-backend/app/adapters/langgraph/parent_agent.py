"""
Aegion LangGraph - Parent AI Agent.

Phase 3: The Cognitive Plane
Higher-authority AI council member for T2+ escalations.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ParentVerdict(str, Enum):
    """Parent council decision outcomes."""
    APPROVE = "approve"
    MODIFY = "modify"  # Approve with modifications
    BLOCK = "block"    # Reject entirely
    ESCALATE = "escalate"  # Need even higher authority (T3 -> War Room)


class ParentReview(BaseModel):
    """Parent AI review of a child proposal."""
    verdict: ParentVerdict
    reasoning: str
    modifications: Optional[List[str]] = None
    risk_assessment: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_human: bool = False


class ParentAgent:
    """
    Parent AI Council Agent.
    
    Reviews T2+ proposals from child council.
    Applies stricter reasoning and risk assessment.
    """
    
    def __init__(self):
        self.policy_context: Dict[str, Any] = {}
        self.rejection_history: List[Dict] = []
    
    async def review_proposal(
        self,
        proposal_id: str,
        proposal_title: str,
        proposal_tier: str,
        child_reasoning: str,
        child_confidence: float,
        affected_modules: List[str],
        context: Dict[str, Any] = {}
    ) -> ParentReview:
        """
        Perform parent-level review of a child proposal.
        
        Rules:
        - T2 proposals require clear cross-module justification
        - T3 proposals trigger human escalation
        - Low child confidence increases scrutiny
        """
        
        # T3 always escalates to human
        if proposal_tier == "T3":
            return ParentReview(
                verdict=ParentVerdict.ESCALATE,
                reasoning="T3 proposals require human War Room review",
                risk_assessment="High - System-wide impact",
                confidence=0.95,
                requires_human=True
            )
        
        # Low child confidence triggers scrutiny
        if child_confidence < 0.5:
            return ParentReview(
                verdict=ParentVerdict.BLOCK,
                reasoning=f"Child confidence too low ({child_confidence:.2f}). Proposal needs stronger evidence.",
                risk_assessment="Medium - Uncertain outcomes",
                confidence=0.8,
                requires_human=False
            )
        
        # Check for critical module involvement
        critical_modules = ["security", "auth", "core", "archon", "chronos"]
        critical_impact = any(m in critical_modules for m in affected_modules)
        
        if critical_impact and child_confidence < 0.8:
            return ParentReview(
                verdict=ParentVerdict.MODIFY,
                reasoning="Critical modules affected. Recommend additional review.",
                modifications=[
                    "Add explicit rollback plan",
                    "Include performance impact analysis",
                    "Document security implications"
                ],
                risk_assessment="Medium-High - Critical modules involved",
                confidence=0.7,
                requires_human=False
            )
        
        # Standard approval for well-reasoned T2
        return ParentReview(
            verdict=ParentVerdict.APPROVE,
            reasoning=f"Proposal meets T2 requirements. Child reasoning: {child_reasoning[:200]}",
            risk_assessment="Acceptable - Cross-module changes with adequate justification",
            confidence=min(child_confidence + 0.1, 1.0),
            requires_human=False
        )
    
    async def learn_from_rejection(
        self,
        proposal_id: str,
        rejection_reason: str,
        lesson: str
    ) -> None:
        """
        Update parent knowledge from rejection.
        """
        self.rejection_history.append({
            "proposal_id": proposal_id,
            "reason": rejection_reason,
            "lesson": lesson
        })
    
    def set_policy_context(self, policy: Dict[str, Any]) -> None:
        """Update the policy context for decision-making."""
        self.policy_context = policy


# Singleton
_parent_agent: Optional[ParentAgent] = None


def get_parent_agent() -> ParentAgent:
    """Get singleton parent agent instance."""
    global _parent_agent
    if _parent_agent is None:
        _parent_agent = ParentAgent()
    return _parent_agent
