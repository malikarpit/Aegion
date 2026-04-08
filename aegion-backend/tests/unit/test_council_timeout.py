
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.council.council_service import CouncilService, CouncilRole, CouncilVote
from datetime import datetime
from app.contracts.decision_intent import DecisionIntent, DecisionTier, ImpactLevel, ReversibilityLevel, ReasoningPhase
from app.domain.council import CouncilMember

@pytest.fixture
def mock_gateway():
    gateway = AsyncMock()
    # Mock complete_with_schema to hang indefinitely
    async def side_effect(*args, **kwargs):
        await asyncio.sleep(60) # Longer than any timeout
        return None
    gateway.complete_with_schema.side_effect = side_effect
    return gateway

@pytest.fixture
def council_service(mock_gateway):
    service = CouncilService(llm_port=MagicMock())
    service.gateway = mock_gateway
    return service

@pytest.mark.asyncio
async def test_council_member_timeout(council_service):
    # Setup proposal
    proposal = DecisionIntent(
        intent_id="test-prop-1",
        session_id="session-123",
        title="Test Proposal",
        description="Testing timeouts",
        impact_level=ImpactLevel.LOCAL,
        reversibility=ReversibilityLevel.EASY,
        calculated_tier=DecisionTier.T1,
        origin="human",
        proposed_by="user-1",
        proposed_at=datetime.utcnow(),
        reasoning=ReasoningPhase(problem_framing="Test", assumptions=[], constraints=[])
    )
    
    # Register purely a Sentinel (short timeout: 20s) to test quicker
    sentinel = CouncilMember(
        member_id="test-sentinel",
        role=CouncilRole.SENTINEL,
        model="gpt-4",
        specialization="safety"
    )
    council_service._members = {"test-sentinel": sentinel}
    
    # We expect this to finish in slightly > 20s, not 60s
    # Using a shorter wait_for in test to ensure we don't actually wait 20s if logic fails
    # But since we patched side_effect to sleep, the service should kill it at 20s.
    # To make test fast, we can mock asyncio.wait_for or just rely on the logic.
    # NOTE: To avoid slow tests, we should check if wait_for was called with correct timeout
    # OR we can mock asyncio.wait_for to raise TimeoutError immediately.
    
    from app.services.council.council_service import GovernanceError
    
    with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError) as mock_wait:
        # Sentinel timeout MUST raise GovernanceError (Safety Gate)
        with pytest.raises(GovernanceError) as excinfo:
            await council_service.convene_session(proposal, "ws-1")
        
        assert "Sentinel blocked proposal" in str(excinfo.value)
