"""
Aegion Council - Escalation Service.

Phase 3: The Cognitive Plane
Manages escalation flow from Child to Parent to War Room.
"""

from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

from ...adapters.langgraph.parent_agent import (
    get_parent_agent,
    ParentReview,
    ParentVerdict
)
from ...core.logging import logger
from ...core.time import TimeAuthority


class EscalationLevel(str, Enum):
    """Escalation levels in the council hierarchy."""
    CHILD = "child"
    PARENT = "parent"
    WAR_ROOM = "war_room"


class EscalationResult(BaseModel):
    """Result of an escalation request."""
    escalation_id: str
    proposal_id: str
    level: EscalationLevel
    verdict: str
    reasoning: str
    requires_human: bool
    timestamp: str
    parent_review: Optional[ParentReview] = None


class EscalationService:
    """
    Service for managing council escalations.
    
    Flow:
    1. Child proposes (T0/T1) → Auto-approve or simple review
    2. Child proposes (T2) → Escalate to Parent
    3. Parent reviews → Approve/Modify/Block/Escalate
    4. If Escalate (T3) → War Room (human intervention)
    """
    
    def __init__(self):
        self._escalations: dict = {}
    
    async def should_escalate(
        self,
        proposal_tier: str,
        child_confidence: float,
        affected_modules: list
    ) -> bool:
        """
        Determine if a proposal should be escalated to parent.
        
        Rules:
        - T2+ always escalates
        - Low confidence (<0.5) escalates
        - Critical modules escalate
        """
        if proposal_tier in ["T2", "T3"]:
            return True
        
        if child_confidence < 0.5:
            return True
        
        critical = ["security", "auth", "core", "archon", "chronos"]
        if any(m in critical for m in affected_modules):
            return True
        
        return False
    
    async def escalate_to_parent(
        self,
        proposal_id: str,
        proposal_title: str,
        proposal_tier: str,
        child_reasoning: str,
        child_confidence: float,
        affected_modules: list,
        context: dict = {}
    ) -> EscalationResult:
        """
        Escalate a proposal to the Parent AI Council.
        """
        import uuid
        
        escalation_id = f"esc-{uuid.uuid4().hex[:12]}"
        
        parent = get_parent_agent()
        review = await parent.review_proposal(
            proposal_id=proposal_id,
            proposal_title=proposal_title,
            proposal_tier=proposal_tier,
            child_reasoning=child_reasoning,
            child_confidence=child_confidence,
            affected_modules=affected_modules,
            context=context
        )
        
        result = EscalationResult(
            escalation_id=escalation_id,
            proposal_id=proposal_id,
            level=EscalationLevel.PARENT if not review.requires_human else EscalationLevel.WAR_ROOM,
            verdict=review.verdict.value,
            reasoning=review.reasoning,
            requires_human=review.requires_human,
            timestamp=TimeAuthority.now(),
            parent_review=review
        )
        
        self._escalations[escalation_id] = result
        
        logger.audit(
            action="PROPOSAL_ESCALATED",
            actor="system",
            target=proposal_id,
            justification=f"Escalated to {result.level.value}",
            metadata={
                "escalation_id": escalation_id,
                "verdict": review.verdict.value,
                "requires_human": review.requires_human
            }
        )
        
        return result
    
    async def get_escalation(self, escalation_id: str) -> Optional[EscalationResult]:
        """Get an escalation by ID."""
        return self._escalations.get(escalation_id)


# Singleton
_escalation_service: Optional[EscalationService] = None


def get_escalation_service() -> EscalationService:
    """Get singleton escalation service."""
    global _escalation_service
    if _escalation_service is None:
        _escalation_service = EscalationService()
    return _escalation_service
