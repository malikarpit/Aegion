import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from app.services.archon.gates import ArchonGates, GovernanceError
from app.contracts.decision_intent import DecisionTier
from app.contracts.uncertainty_level import UncertaintyDeclaration, UncertaintyLevel, UncertaintySource
from app.core.security import AuthorityContext

@pytest.fixture
def archon():
    return ArchonGates()

@pytest.fixture
def mock_approver():
    return AuthorityContext(
        user_id="user-1",
        scopes=["read", "write"],
        role="developer",
        can_approve_t1=True,
        can_approve_t2=False  # Key: Not high enough to override uncertainty block
    )

@pytest.mark.asyncio
async def test_approve_proposal_with_high_uncertainty_blocks(archon, mock_approver):
    """Test that high uncertainty blocks approval."""
    proposal_id = "prop-high-uncertainty"
    
    # Mock proposal with blocking uncertainty
    mock_proposal = MagicMock()
    mock_proposal.status = "pending"
    mock_proposal.uncertainty = UncertaintyDeclaration(
        level=UncertaintyLevel.HIGH,
        confidence_score=0.1,
        reasoning="Too vague",
        is_blocking=True,
        blocking_reason="High uncertainty",
        sources=[UncertaintySource.AMBIGUOUS_CONTEXT]
    )

    # Mock evidence list
    evidence_list = []

    # Mock OPA to allow
    with patch("app.services.archon.opa.get_opa_service") as mock_opa:
        mock_opa.return_value.evaluate_policy.return_value = {"allow": True}
        
        # Attempt approval
        with pytest.raises(GovernanceError) as excinfo:
            await archon.approve_proposal(
                proposal_id=proposal_id,
                proposal_status="pending",
                approver=mock_approver,
                tier=DecisionTier.T1,
                evidence_list=evidence_list,
                proposal_created_at=datetime.now(timezone.utc),
                uncertainty=mock_proposal.uncertainty 
            )
    
    assert "Uncertainty blocking approval" in str(excinfo.value)
    assert "High uncertainty" in str(excinfo.value)

@pytest.mark.asyncio
async def test_approve_proposal_with_low_uncertainty_allows(archon, mock_approver):
    """Test that low uncertainty allows approval."""
    proposal_id = "prop-low-uncertainty"
    
    uncertainty = UncertaintyDeclaration(
        level=UncertaintyLevel.LOW,
        confidence_score=0.9,
        reasoning="Clear path",
        is_blocking=False
    )

    # Mock validate_evidence to pass
    archon.validate_evidence = MagicMock(return_value=(True, []))

    # Mock OPA to allow
    with patch("app.services.archon.opa.get_opa_service") as mock_opa:
        mock_opa.return_value.evaluate_policy.return_value = {"allow": True}

        # Attempt approval - should not raise
        await archon.approve_proposal(
            proposal_id=proposal_id,
            proposal_status="pending",
            approver=mock_approver,
            tier=DecisionTier.T1,
            evidence_list=[],
            proposal_created_at=datetime.now(timezone.utc),
            uncertainty=uncertainty
        )

