"""
Council Bridge — Adapts ACK CouncilEngine results to v1 CouncilSession domain.

The bridge pattern allows the governed CouncilService (v1) to delegate
LLM execution to the ACK CouncilEngine (multi-model, cost-optimized)
while preserving the full governance contract:

  CouncilService (governance layer)
       │
       ├── freeze mode check
       ├── health check
       ├── tier-based round count
       │
       ▼
  CouncilBridge (this module)
       │
       ├── maps DecisionIntent → ACK CouncilType + context
       ├── calls CouncilEngine.consult()
       ├── maps CouncilResult → List[CouncilOpinion]
       └── maps CouncilResult → CouncilSession
       │
       ▼
  CouncilEngine (ACK execution layer)
       │
       ├── FrugalGPT cascade
       ├── persona debate
       ├── peer review
       ├── rubric scoring
       └── cost tracking
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from ...core.logging import logger
from ...domain.council import (
    CouncilOpinion,
    CouncilSession,
    CouncilVote,
)
from ...contracts.decision_intent import DecisionIntent, DecisionTier
from ..council_kernel.types import CouncilResult, CouncilType, ModelResponse


# ───────────────────────────────────────────────────────
# Tier → CouncilType mapping
# ───────────────────────────────────────────────────────

_TIER_TO_COUNCIL_TYPE = {
    DecisionTier.T0: CouncilType.CHILD,
    DecisionTier.T1: CouncilType.CHILD,
    DecisionTier.T2: CouncilType.PARENT,
    DecisionTier.T3: CouncilType.PARENT,
}


class CouncilBridge:
    """
    Adapts ACK CouncilEngine operations to v1 governance domain types.

    Usage:
        bridge = CouncilBridge(council_engine)
        session = await bridge.consult_as_session(proposal, workspace_id)
    """

    def __init__(self, council_engine) -> None:
        self.engine = council_engine

    async def consult_as_session(
        self,
        proposal: DecisionIntent,
        workspace_id: str,
        member_ids: Optional[List[str]] = None,
    ) -> CouncilSession:
        """
        Run ACK consultation and return a governance-compatible CouncilSession.

        Maps:
          - DecisionTier → CouncilType (T0/T1 → CHILD, T2/T3 → PARENT)
          - CouncilResult.individual_responses → List[CouncilOpinion]
          - CouncilResult.consensus_score → consensus vote
        """
        start_time = datetime.now(timezone.utc)

        council_type = _TIER_TO_COUNCIL_TYPE.get(
            proposal.calculated_tier, CouncilType.CHILD
        )

        # Build context from proposal
        context: Dict = {
            "proposal_id": proposal.intent_id,
            "tier": proposal.calculated_tier.value,
            "impact": proposal.impact_level.value,
            "reversibility": proposal.reversibility.value,
            "affected_modules": proposal.affected_modules,
        }
        if proposal.reasoning:
            context["assumptions"] = proposal.reasoning.assumptions
            context["constraints"] = proposal.reasoning.constraints

        # Execute ACK consultation
        result = await self.engine.consult(
            workspace_id, proposal.description, council_type, context,
        )

        # Convert to governance types
        opinions = self._result_to_opinions(result, proposal.intent_id)
        consensus_vote, confidence = self._compute_consensus(result)

        # Check sentinel blocking
        sentinel_blocked = self._check_sentinel_block(result)

        session = CouncilSession(
            proposal_id=proposal.intent_id,
            workspace_id=workspace_id,
            member_ids=member_ids or [r.model for r in result.individual_responses],
            opinions=opinions,
            consensus=consensus_vote,
            consensus_confidence=confidence,
            synthesis=result.synthesis,
            status="rejected" if sentinel_blocked else "completed",
            started_at=start_time,
            completed_at=datetime.now(timezone.utc),
            total_tokens=result.total_tokens,
            dissent_count=len(result.dissenting_views),
            dissenting_member_ids=[
                r.model for r in result.individual_responses
                if r.confidence < 0.50
            ],
        )

        logger.audit(
            action="ACK_BRIDGE_CONSULT",
            actor="council_bridge",
            target=proposal.intent_id,
            justification=(
                f"ACK {council_type.value} council → "
                f"consensus={consensus_vote.value if consensus_vote else 'none'} "
                f"cost=${result.total_cost_usd:.4f}"
            ),
            metadata={
                "session_id": session.session_id,
                "council_type": council_type.value,
                "models_used": result.models_used,
                "cache_hit": result.cache_hit,
                "total_cost_usd": result.total_cost_usd,
            },
        )

        return session

    # ───────────────────────────────────────────────────────
    # Internal mapping helpers
    # ───────────────────────────────────────────────────────

    def _result_to_opinions(
        self, result: CouncilResult, proposal_id: str,
    ) -> List[CouncilOpinion]:
        """Map ACK ModelResponse list → CouncilOpinion list."""
        opinions: List[CouncilOpinion] = []

        for resp in result.individual_responses:
            vote = self._confidence_to_vote(resp.confidence)
            opinions.append(CouncilOpinion(
                member_id=f"ack-{resp.provider}-{resp.model}",
                proposal_id=proposal_id,
                vote=vote,
                confidence=resp.confidence,
                analysis=resp.response[:2000],  # Truncate for storage
                concerns=[],
                suggestions=[],
                tokens_consumed=resp.tokens_in + resp.tokens_out,
                metadata={
                    "stage": f"ack_{result.council_type.value}",
                    "provider": resp.provider,
                    "model": resp.model,
                    "cost_usd": resp.cost_usd,
                    "latency_ms": resp.latency_ms,
                    "blocking": False,
                },
            ))

        # Add dissenting views as additional opinions
        for i, dissent in enumerate(result.dissenting_views):
            opinions.append(CouncilOpinion(
                member_id=f"ack-dissent-{i}",
                proposal_id=proposal_id,
                vote=CouncilVote.OPPOSE,
                confidence=0.3,
                analysis=dissent[:2000],
                metadata={
                    "stage": "ack_dissent",
                    "blocking": False,
                },
            ))

        return opinions

    def _confidence_to_vote(self, confidence: float) -> CouncilVote:
        """Map confidence score → CouncilVote."""
        if confidence >= 0.70:
            return CouncilVote.SUPPORT
        if confidence >= 0.40:
            return CouncilVote.DEFER
        return CouncilVote.OPPOSE

    def _compute_consensus(self, result: CouncilResult):
        """Derive consensus vote and confidence from ACK result."""
        score = result.consensus_score

        if score >= 0.75:
            return CouncilVote.SUPPORT, score
        if score >= 0.50:
            return CouncilVote.DEFER, score
        if score >= 0.25:
            return CouncilVote.OPPOSE, score
        return CouncilVote.ABSTAIN, score

    def _check_sentinel_block(self, result: CouncilResult) -> bool:
        """Check if the ACK result indicates a sentinel block."""
        if result.council_type == CouncilType.SENTINEL:
            # If consensus is very low on a sentinel check, it's a block
            if result.consensus_score < 0.50:
                return True
        # Check for constitutional redaction markers
        if "[CONSTITUTIONAL REDACTION]" in result.synthesis:
            return True
        if "⚠️ RED TEAM WARNING" in result.synthesis:
            # Not a hard block, but flagged
            return False
        return False
