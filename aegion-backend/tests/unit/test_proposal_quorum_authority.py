"""
Aegion AG-003: Governance Quorum & Authority Tests.

Tests policy-driven quorum enforcement, tier reasoning,
and authority gates for the proposal approval pipeline.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import get_current_user, AuthorityContext
from app.contracts.decision_intent import (
    DecisionTier, ImpactLevel, ReversibilityLevel
)
from app.services.archon.gates import ArchonGates, get_archon
from app.services.archon.registry import GovernancePolicy, PolicyRegistry


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides = {}


def mock_user(user_id="user-1", role="architect", t1=True, t2=True):
    return AuthorityContext(
        user_id=user_id,
        scopes=["read", "write"],
        role=role,
        can_approve_t1=t1,
        can_approve_t2=t2
    )


STANDARD_HEADERS = {
    "X-Aegion-Session": "sess-test",
    "X-Aegion-Intent": "proposal.create"
}


# ============================================================
# Test 1: T1 proposal auto-approves with 1 vote
# ============================================================

class TestQuorumT1:
    def test_t1_single_vote_auto_approves(self):
        """T1 proposals require only 1 vote to auto-approve."""
        archon = ArchonGates()
        required = archon.get_quorum(DecisionTier.T1)
        assert required == 1


# ============================================================
# Test 2: T2 proposal requires 2 votes
# ============================================================

class TestQuorumT2:
    def test_t2_requires_two_votes(self):
        """T2 proposals require 2 distinct approvers."""
        archon = ArchonGates()
        required = archon.get_quorum(DecisionTier.T2)
        assert required == 2


# ============================================================
# Test 3: T3 proposal requires 3 votes
# ============================================================

class TestQuorumT3:
    def test_t3_requires_three_votes(self):
        """T3 proposals require 3 distinct approvers."""
        archon = ArchonGates()
        required = archon.get_quorum(DecisionTier.T3)
        assert required == 3


# ============================================================
# Test 4: T0 auto-approves with 1 vote
# ============================================================

class TestQuorumT0:
    def test_t0_single_vote(self):
        """T0 (trivial) proposals need only 1 vote."""
        archon = ArchonGates()
        required = archon.get_quorum(DecisionTier.T0)
        assert required == 1


# ============================================================
# Test 5: get_quorum returns policy values
# ============================================================

class TestQuorumPolicyDriven:
    def test_quorum_reads_from_policy(self):
        """Quorum values should come from the active GovernancePolicy."""
        custom_policy = GovernancePolicy(
            id="custom",
            version="1.0.0",
            effective_from="2026-01-01T00:00:00Z",
            quorum_requirements={"T0": 1, "T1": 2, "T2": 4, "T3": 5}
        )
        PolicyRegistry.register(custom_policy)

        archon = ArchonGates()
        assert archon.get_quorum(DecisionTier.T1) == 2
        assert archon.get_quorum(DecisionTier.T2) == 4
        assert archon.get_quorum(DecisionTier.T3) == 5

        # Reset policy
        PolicyRegistry._active_policy_id = None


# ============================================================
# Test 6: explain_tier returns critical module reason
# ============================================================

class TestExplainTier:
    def test_explain_tier_basic(self):
        """explain_tier returns tier, quorum, and reasons."""
        archon = ArchonGates()
        result = archon.explain_tier(
            impact=ImpactLevel.LOCAL,
            reversibility=ReversibilityLevel.EASY,
            affected_modules=[]
        )
        assert "tier" in result
        assert "quorum" in result
        assert "reasons" in result
        assert isinstance(result["reasons"], list)
        assert len(result["reasons"]) >= 1

    def test_explain_tier_critical_module_escalation(self):
        """Touching a critical module escalates to T2+ with reason."""
        archon = ArchonGates()
        result = archon.explain_tier(
            impact=ImpactLevel.LOCAL,
            reversibility=ReversibilityLevel.EASY,
            affected_modules=["security"]
        )
        assert result["tier"] in ("T2", "T3")
        assert result["quorum"] >= 2
        assert any("critical module" in r for r in result["reasons"])

    def test_explain_tier_includes_self_approval_flag(self):
        """explain_tier includes whether self-approval is allowed."""
        archon = ArchonGates()
        
        t1_result = archon.explain_tier(
            impact=ImpactLevel.LOCAL,
            reversibility=ReversibilityLevel.EASY,
            affected_modules=[]
        )
        assert t1_result["self_approval_allowed"] is True

        t2_result = archon.explain_tier(
            impact=ImpactLevel.LOCAL,
            reversibility=ReversibilityLevel.EASY,
            affected_modules=["core"]
        )
        assert t2_result["self_approval_allowed"] is False


# ============================================================
# Test 7: Self-approval blocked for T2+
# ============================================================

class TestSelfApprovalBlocked:
    @pytest.mark.asyncio
    async def test_self_approval_blocked_t2(self):
        """Archon blocks self-approval for T2 decisions."""
        from datetime import datetime, timezone
        archon = ArchonGates()
        user = mock_user("user-creator")

        with pytest.raises(Exception) as exc_info:
            await archon.approve_proposal(
                proposal_id="prop-1",
                proposal_status="pending",
                approver=user,
                tier=DecisionTier.T2,
                evidence_list=[],
                proposal_created_at=datetime.now(timezone.utc),
                proposal_creator_id="user-creator"
            )
        error_msg = str(exc_info.value)
        assert "Self-approval blocked" in error_msg or "Separation" in error_msg


# ============================================================
# Test 8: ProposalResponse includes governance metadata
# ============================================================

class TestProposalResponseMetadata:
    def test_create_proposal_returns_governance_fields(self, client):
        """create_proposal response includes quorum, approvals_count, tier_reasons."""
        user = mock_user("user-test")
        app.dependency_overrides[get_current_user] = lambda: user

        explain_result = {
            "tier": "T2",
            "quorum": 2,
            "evidence_required": 2,
            "self_approval_allowed": False,
            "reasons": ["Impact: system_wide, Reversibility: difficult → base tier T2"]
        }

        with patch("app.services.archon.gates.ArchonGates.explain_tier", return_value=explain_result):
            payload = {
                "session_id": "sess-1",
                "title": "Test Governance Metadata",
                "description": "Verifying response fields",
                "impact_level": "system_wide",
                "reversibility": "difficult",
                "reasoning": {
                    "problem_framing": "Test",
                    "assumptions": [],
                    "constraints": [],
                    "alternatives_considered": []
                },
                "uncertainty": {
                    "level": "medium",
                    "confidence_score": 0.7,
                    "reasoning": "Standard risk assessment",
                    "sources": [],
                    "is_blocking": False
                }
            }

            response = client.post(
                "/api/v1/proposals/",
                json=payload,
                headers=STANDARD_HEADERS
            )
            assert response.status_code == 200
            data = response.json()
            assert data["tier"] == "T2"
            assert data["quorum_required"] == 2
            assert data["approvals_count"] == 0
            assert len(data["tier_reasons"]) >= 1
