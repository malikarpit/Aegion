
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.domain.council import (
    CouncilRole, HealthStatus, CouncilHealth, CouncilVote,
    UncertaintyLevel, SentinelAssessment
)
from app.contracts.decision_intent import (
    DecisionIntent, DecisionTier, ImpactLevel, ReversibilityLevel, ReasoningPhase
)
from datetime import datetime, timezone

@pytest.fixture
def mock_llm_port():
    port = AsyncMock()
    port.complete = AsyncMock()
    return port

@pytest.fixture
def basic_proposal():
    return DecisionIntent(
        intent_id="intent-1",
        session_id="session-1",
        title="Test Proposal",
        description="Testing health policies",
        impact_level=ImpactLevel.LOCAL,
        reversibility=ReversibilityLevel.MODERATE,
        calculated_tier=DecisionTier.T1,
        origin="human",
        proposed_by="tester",
        proposed_at=datetime.now(timezone.utc),
        reasoning=ReasoningPhase(problem_framing="Test", assumptions=[], constraints=[])
    )

@pytest.mark.asyncio
async def test_health_check_healthy(mock_llm_port):
    from app.services.council.council_service import CouncilService
    
    # Mock successful ping
    mock_llm_port.complete.return_value = "pong"
    
    service = CouncilService(llm_port=mock_llm_port)
    health = await service.check_health()
    
    assert health.status == HealthStatus.HEALTHY
    assert health.details.get("llm_connectivity") is True

@pytest.mark.asyncio
async def test_health_check_degraded(mock_llm_port):
    from app.services.council.council_service import CouncilService
    
    # Mock failure with side_effect
    mock_llm_port.ping = AsyncMock(side_effect=Exception("Timeout"))
    # Also fail fallback complete just in case
    mock_llm_port.complete.side_effect = Exception("Timeout")
    
    service = CouncilService(llm_port=mock_llm_port)
    health = await service.check_health()
    
    # Should degrade but not crash
    assert health.status == HealthStatus.DEGRADED
    assert health.details.get("llm_connectivity") is False

@pytest.mark.asyncio
async def test_degraded_mode_policy_blocking():
    """T2/T3 must be blocked in DEGRADED mode."""
    from app.services.council.council_service import CouncilService, GovernanceError
    
    # Service without LLM port => DEGRADED
    service = CouncilService(llm_port=None) 
    
    # T2 Proposal
    high_stakes_proposal = DecisionIntent(
        intent_id="i2", session_id="s2", title="High Stakes", description="...",
        impact_level=ImpactLevel.SYSTEM_WIDE, reversibility=ReversibilityLevel.DIFFICULT,
        calculated_tier=DecisionTier.T2, # Critical
        origin="human", proposed_by="u1", proposed_at=datetime.now(timezone.utc),
        reasoning=ReasoningPhase(problem_framing=".", assumptions=[], constraints=[])
    )
    
    # Should raise GovernanceError
    with pytest.raises(GovernanceError) as excinfo:
        await service.convene_session(high_stakes_proposal, "ws-1")
    
    assert "DEGRADED mode" in str(excinfo.value)

@pytest.mark.asyncio
async def test_sentinel_blocking_gate():
    """Sentinel blocking=True must raise GovernanceError."""
    from app.services.council.council_service import CouncilService, GovernanceError, CouncilOpinion, CouncilMember
    
    # Mock LLM port that returns HEALTHY so we can proceed to execution
    mock_port = AsyncMock()
    # Mock check_health to always return healthy so we don't get blocked by safe mode
    # But wait, we need to mock check_health or the port behavior
    mock_port.ping = AsyncMock() 
    
    service = CouncilService(llm_port=mock_port)
    
    # T1 Proposal (Allowed in Healthy)
    proposal = DecisionIntent(
        intent_id="i3", session_id="s3", title="Risky Proposal", description="...",
        impact_level=ImpactLevel.LOCAL, reversibility=ReversibilityLevel.MODERATE,
        calculated_tier=DecisionTier.T1,
        origin="human", proposed_by="u1", proposed_at=datetime.now(timezone.utc),
        reasoning=ReasoningPhase(problem_framing=".", assumptions=[], constraints=[])
    )

    # Register the sentinel member explicitly
    sentinel_member = CouncilMember(
        member_id="sentinel",
        role=CouncilRole.SENTINEL,
        model="gpt-4",
        specialization="security"
    )
    service.register_member(sentinel_member)

    # Mock _get_member_opinion to return a blocking sentinel opinion
    # We assert that conven_session raises GovernanceError
    
    blocking_opinion = CouncilOpinion(
        member_id="sentinel",
        proposal_id="i3",
        vote=CouncilVote.OPPOSE,
        confidence=0.9,
        analysis="Blocking Risk Found",
        metadata={
            "stage": "sentinel_assessment",
            "blocking": True
        }
    )
    
    service._get_member_opinion = AsyncMock(return_value=blocking_opinion)
    
    with pytest.raises(GovernanceError) as excinfo:
        await service.convene_session(proposal, "ws-1", member_ids=["sentinel"])
    
    assert "Sentinel blocked proposal" in str(excinfo.value)
