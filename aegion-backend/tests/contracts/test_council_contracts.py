import pytest
import struct
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

from app.domain.council import (
    ChildDebateResult, ParentVerdict, SentinelAssessment,
    UncertaintyLevel, CouncilVote, CouncilRole, CouncilStageResult
)
from app.services.council.llm_gateway import LLMGateway

# --- Domain Model Tests ---

def test_sentinel_blocking_policy():
    """Sentinel must block on high uncertainty."""
    # Valid high uncertainty (blocking=True)
    SentinelAssessment(
        claim="Potentially unsafe",
        reasoning_summary="...",
        confidence_score=0.9,
        uncertainty_level=UncertaintyLevel.HIGH,
        blocking=True,
        risk_category="security",
        stage_name="sentinel"
    )

    # Invalid high uncertainty (blocking=False) - Governance Violation
    with pytest.raises(ValidationError):
        SentinelAssessment(
            claim="Maybe unsafe",
            reasoning_summary="...",
            confidence_score=0.9,
            uncertainty_level=UncertaintyLevel.HIGH,
            blocking=False,
            risk_category="security",
            stage_name="sentinel"
        )
        
def test_sentinel_low_confidence_policy():
    """Sentinel must block on very low confidence."""
    with pytest.raises(ValidationError):
        SentinelAssessment(
            claim="I don't know",
            reasoning_summary="...",
            confidence_score=0.1, # Too low
            uncertainty_level=UncertaintyLevel.LOW,
            blocking=False,
            risk_category="security",
            stage_name="sentinel"
        )

def test_child_debate_result_valid():
    """Test valid child result."""
    res = ChildDebateResult(
        claim="Performance impact is negligible",
        reasoning_summary="Checked traces",
        confidence_score=0.8,
        uncertainty_level=UncertaintyLevel.LOW,
        blocking=False,
        agent_role=CouncilRole.CRITIC,
        vote=CouncilVote.SUPPORT,
        stage_name="child_debate"
    )
    assert res.vote == CouncilVote.SUPPORT

# --- LLM Gateway Tests ---

@pytest.mark.asyncio
async def test_gateway_success():
    """Test successful strict parsing."""
    mock_port = AsyncMock()
    mock_port.complete.return_value = {
        "claim": "Test claim",
        "reasoning_summary": "Logic",
        "confidence_score": 0.9,
        "uncertainty_level": "LOW",
        "blocking": False,
        "agent_role": "proposer",
        "vote": "support",
        "stage_name": "test"
    }
    
    gateway = LLMGateway(mock_port)
    result = await gateway.complete_with_schema(
        prompt="test", 
        model="gpt-4", 
        schema=ChildDebateResult
    )
    
    assert isinstance(result, ChildDebateResult)
    assert result.claim == "Test claim"

@pytest.mark.asyncio
async def test_gateway_retry_logic():
    """Test gateway retries on validation error."""
    mock_port = AsyncMock()
    # First attempt: Invalid JSON (missing field)
    # Second attempt: Valid JSON
    mock_port.complete.side_effect = [
        {"claim": "Bad"}, # Missing required fields
        {
            "claim": "Good",
            "reasoning_summary": "Logic",
            "confidence_score": 0.9,
            "uncertainty_level": "LOW",
            "blocking": False,
            "agent_role": "proposer",
            "vote": "support",
            "stage_name": "test"
        }
    ]
    
    gateway = LLMGateway(mock_port)
    gateway.base_delay = 0.01 # Fast test
    
    result = await gateway.complete_with_schema(
        prompt="test", 
        model="gpt-4", 
        schema=ChildDebateResult
    )
    
    assert result.claim == "Good"
    assert mock_port.complete.call_count == 2

@pytest.mark.asyncio
async def test_gateway_exhaust_retries():
    """Test gateway gives up after max retries."""
    mock_port = AsyncMock()
    mock_port.complete.return_value = {"claim": "Bad"} # Always invalid
    
    gateway = LLMGateway(mock_port)
    gateway.base_delay = 0.01
    
    
    with pytest.raises(ValidationError):
        await gateway.complete_with_schema(
            prompt="test", 
            model="gpt-4", 
            schema=ChildDebateResult
        )
    
    assert mock_port.complete.call_count == 3

@pytest.mark.asyncio
async def test_council_service_integration():
    """Test CouncilService mapping logic."""
    from datetime import datetime, timezone
    from app.services.council.council_service import CouncilService, CouncilMember
    from app.contracts.decision_intent import DecisionIntent, DecisionTier, ImpactLevel, ReversibilityLevel, ReasoningPhase as Reasoning
    
    # Mock Gateway
    mock_port = AsyncMock()
    mock_port.complete.return_value = {
        "claim": "Integration Work",
        "reasoning_summary": "Testing mapping",
        "confidence_score": 0.95,
        "uncertainty_level": "LOW",
        "blocking": False,
        "agent_role": "critic",
        "vote": "support",
        "stage_name": "child_debate",
        "citations": ["file.py"]
    }
    
    service = CouncilService(llm_port=mock_port)
    
    member = CouncilMember(member_id="m1", role=CouncilRole.CRITIC, model="gpt-4")
    proposal = DecisionIntent(
        intent_id="intent-1",
        session_id="session-1",
        title="Test", 
        description="Desc", 
        calculated_tier=DecisionTier.T1,
        impact_level=ImpactLevel.LOCAL,
        reversibility=ReversibilityLevel.MODERATE,
        affected_modules=[],
        reasoning=Reasoning(problem_framing="Prob", assumptions=[], constraints=[]),
        origin="human",
        proposed_by="user-1",
        proposed_at=datetime.now(timezone.utc)
    )
    
    opinion = await service._get_member_opinion(member, proposal, "ws-1")
    
    assert opinion.vote == CouncilVote.SUPPORT
    assert opinion.confidence == 0.95
    assert "Integration Work" in opinion.analysis
    assert opinion.metadata["stage"] == "child_debate"
    assert opinion.metadata["uncertainty"] == UncertaintyLevel.LOW

