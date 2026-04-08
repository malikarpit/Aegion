"""
Aegion Governance Invariant Tests.

These tests verify that governance invariants are never violated.
They represent the "constitution" of the system.

Doctrine: "What cannot be broken, cannot be violated."
"""

import pytest
from datetime import timezone, datetime, timedelta
from unittest.mock import MagicMock, patch

# Import the modules under test
from app.services.archon.gates import ArchonGates, GovernanceError, get_archon
from app.services.archon.registry import PolicyRegistry, GovernancePolicy
from app.contracts.decision_intent import (
    DecisionTier, ImpactLevel, ReversibilityLevel, calculate_tier
)
from app.contracts.evidence import (
    Evidence, EvidenceClassification, EvidenceGate, EvidenceType, EvidenceSource
)
from app.core.security import AuthorityContext, Role


def _make_evidence(proposal_id: str, classification=EvidenceClassification.SUPPORTING) -> Evidence:
    """Helper to create a valid Evidence object for tests needing approval."""
    now = datetime.now(timezone.utc)
    return Evidence(
        evidence_id=f"evd-{proposal_id}",
        proposal_id=proposal_id,
        evidence_type=EvidenceType.TEST_RESULT,
        classification=classification,
        source=EvidenceSource.AUTOMATED,
        source_id="test-run",
        created_at=now,
        collected_at=now,
        content_hash="abc123",
        summary="Test evidence",
    )


class TestFreezeMode:
    """Tests for freeze mode - the emergency stop."""

    @pytest.mark.asyncio
    async def test_freeze_blocks_all_mutations(self):
        """INVARIANT: When frozen, NO mutations are allowed."""
        archon = ArchonGates()
        await archon.activate_freeze("test-actor", "security incident")
        
        with pytest.raises(GovernanceError) as exc_info:
            archon.guard_writable()
        
        assert "FREEZE mode" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_freeze_can_be_deactivated(self):
        """Freeze can be deactivated by authorized actor."""
        archon = ArchonGates()
        await archon.activate_freeze("test-actor", "security incident")
        await archon.deactivate_freeze("test-actor", "incident resolved")
        
        # Should not raise
        archon.guard_writable()

    def test_freeze_is_off_by_default(self):
        """System starts in writable mode."""
        archon = ArchonGates()
        
        # Should not raise
        archon.guard_writable()


class TestTierClassification:
    """Tests for decision tier classification using calculate_tier function."""

    def test_trivial_impact_easy_reversibility_is_t0(self):
        """INVARIANT: Trivial impact + easy reversibility = T0 (auto-approve)."""
        tier = calculate_tier(
            ImpactLevel.TRIVIAL,
            ReversibilityLevel.EASY
        )
        assert tier == DecisionTier.T0

    def test_local_impact_moderate_reversibility_is_t1(self):
        """INVARIANT: Local impact + moderate reversibility = T1."""
        tier = calculate_tier(
            ImpactLevel.LOCAL,
            ReversibilityLevel.MODERATE
        )
        assert tier == DecisionTier.T1

    def test_cross_module_difficult_reversibility_is_t2(self):
        """INVARIANT: Cross-module + difficult reversibility = T2."""
        tier = calculate_tier(
            ImpactLevel.CROSS_MODULE,
            ReversibilityLevel.DIFFICULT
        )
        assert tier == DecisionTier.T2

    def test_system_wide_irreversible_is_t3(self):
        """INVARIANT: System-wide + irreversible = T3 (highest tier)."""
        tier = calculate_tier(
            ImpactLevel.SYSTEM_WIDE,
            ReversibilityLevel.IRREVERSIBLE
        )
        assert tier == DecisionTier.T3


class TestApprovalAuthority:
    """Tests for approval authority enforcement."""

    def test_developer_cannot_approve_t1(self):
        """INVARIANT: Developers cannot approve T1 decisions."""
        archon = ArchonGates()
        dev_authority = AuthorityContext.from_role("dev-user", Role.DEVELOPER)
        
        can_approve, error = archon.can_approve(dev_authority, DecisionTier.T1)
        
        assert can_approve is False
        assert error is not None

    def test_architect_can_approve_t1(self):
        """Architects CAN approve T1 decisions."""
        archon = ArchonGates()
        arch_authority = AuthorityContext.from_role("arch-user", Role.ARCHITECT)
        
        can_approve, error = archon.can_approve(arch_authority, DecisionTier.T1)
        
        assert can_approve is True
        assert error is None

    def test_architect_cannot_approve_t2(self):
        """INVARIANT: Only Admins can approve T2 decisions."""
        archon = ArchonGates()
        arch_authority = AuthorityContext.from_role("arch-user", Role.ARCHITECT)
        
        can_approve, error = archon.can_approve(arch_authority, DecisionTier.T2)
        
        assert can_approve is False
        assert error is not None

    def test_admin_can_approve_all_tiers(self):
        """Admins can approve any tier."""
        archon = ArchonGates()
        admin_authority = AuthorityContext.from_role("admin-user", Role.ADMIN)
        
        for tier in [DecisionTier.T0, DecisionTier.T1, DecisionTier.T2, DecisionTier.T3]:
            can_approve, _ = archon.can_approve(admin_authority, tier)
            assert can_approve is True, f"Admin should approve {tier}"


class TestEvidenceGating:
    """Tests for evidence gating rules."""

    def create_evidence(
        self,
        evidence_id: str,
        proposal_id: str,
        classification: EvidenceClassification = EvidenceClassification.SUPPORTING,
        collected_at: datetime = None
    ) -> Evidence:
        """Helper to create properly formed Evidence objects."""
        return Evidence(
            evidence_id=evidence_id,
            proposal_id=proposal_id,
            evidence_type=EvidenceType.TEST_RESULT,
            classification=classification,
            source=EvidenceSource.AUTOMATED,
            source_id="test-run-001",
            created_at=collected_at or datetime.now(timezone.utc),
            collected_at=collected_at or datetime.now(timezone.utc),
            content_hash="abc123def456789",
            summary="Test passed successfully"
        )

    def test_t1_requires_evidence(self):
        """INVARIANT: T1 decisions require at least 1 evidence."""
        archon = ArchonGates()
        
        is_valid, errors = archon.validate_evidence(
            proposal_id="prop-123",
            proposal_created_at=datetime.now(timezone.utc),
            evidence_list=[],  # No evidence
            tier=DecisionTier.T1
        )
        
        assert is_valid is False
        assert any("at least" in e.lower() for e in errors)

    def test_t0_allows_no_evidence(self):
        """T0 decisions can proceed without evidence (auto-approve)."""
        archon = ArchonGates()
        
        is_valid, errors = archon.validate_evidence(
            proposal_id="prop-123",
            proposal_created_at=datetime.now(timezone.utc),
            evidence_list=[],
            tier=DecisionTier.T0
        )
        
        assert is_valid is True
        assert len(errors) == 0

    def test_evidence_must_be_linked_to_proposal(self):
        """INVARIANT: Evidence must be linked to the specific proposal."""
        archon = ArchonGates()
        
        # Evidence linked to different proposal
        unlinked_evidence = self.create_evidence(
            evidence_id="evd-1",
            proposal_id="prop-OTHER",  # Different proposal!
        )
        
        is_valid, errors = archon.validate_evidence(
            proposal_id="prop-123",
            proposal_created_at=datetime.now(timezone.utc),
            evidence_list=[unlinked_evidence],
            tier=DecisionTier.T1
        )
        
        assert is_valid is False
        assert any("not linked" in e.lower() for e in errors)

    def test_contradictory_evidence_blocks_approval(self):
        """INVARIANT: Contradictory evidence blocks T1+ approval."""
        archon = ArchonGates()
        proposal_time = datetime.now(timezone.utc)
        
        contradictory = self.create_evidence(
            evidence_id="evd-1",
            proposal_id="prop-123",
            classification=EvidenceClassification.CONTRADICTORY,
            collected_at=proposal_time
        )
        
        is_valid, errors = archon.validate_evidence(
            proposal_id="prop-123",
            proposal_created_at=proposal_time,
            evidence_list=[contradictory],
            tier=DecisionTier.T1
        )
        
        assert is_valid is False
        assert any("contradictory" in e.lower() for e in errors)


class TestPolicyRegistry:
    """Tests for policy registry behavior."""

    def test_genesis_policy_on_cold_start(self):
        """INVARIANT: System always has a policy, even on cold start."""
        # Clear any existing policies
        PolicyRegistry._policies = {}
        PolicyRegistry._active_policy_id = None
        
        policy = PolicyRegistry.get_active()
        
        assert policy is not None
        assert policy.id == "genesis"
        assert policy.version == "0.0.1"

    def test_policy_contains_required_invariants(self):
        """INVARIANT: Policy must define core invariants."""
        policy = PolicyRegistry.get_active()
        
        assert "AI_CANNOT_DIRECTLY_WRITE_DB" in policy.invariants
        assert "SESSION_MUST_HAVE_OWNER" in policy.invariants
        assert "DECISION_MUST_HAVE_RATIONALE" in policy.invariants

    def test_policy_has_critical_modules(self):
        """Policy must define critical modules for escalation."""
        policy = PolicyRegistry.get_active()
        
        assert hasattr(policy, 'critical_modules')
        assert "security" in policy.critical_modules
        assert "archon" in policy.critical_modules


class TestSegregationOfDuties:
    """Invariant: Author of T2+ proposal MUST NOT self-approve."""

    @pytest.mark.asyncio
    async def test_self_approval_blocked_t2(self):
        """INVARIANT: Self-approval MUST be blocked for T2 proposals."""
        archon = ArchonGates()
        approver = AuthorityContext.from_role("same-user", Role.ADMIN)

        with pytest.raises(GovernanceError):
            await archon.approve_proposal(
                proposal_id="prop-sod-t2",
                proposal_status="pending",
                approver=approver,
                tier=DecisionTier.T2,
                evidence_list=[],
                proposal_created_at=datetime.now(timezone.utc),
                proposal_creator_id="same-user",  # Same user = self-approval
            )

    @pytest.mark.asyncio
    async def test_self_approval_blocked_t3(self):
        """INVARIANT: Self-approval MUST be blocked for T3 proposals."""
        archon = ArchonGates()
        approver = AuthorityContext.from_role("same-user", Role.ADMIN)

        with pytest.raises(GovernanceError):
            await archon.approve_proposal(
                proposal_id="prop-sod-t3",
                proposal_status="pending",
                approver=approver,
                tier=DecisionTier.T3,
                evidence_list=[],
                proposal_created_at=datetime.now(timezone.utc),
                proposal_creator_id="same-user",
            )

    @pytest.mark.asyncio
    async def test_cross_user_approval_allowed(self):
        """Cross-user approval should succeed for authorized users."""
        archon = ArchonGates()
        approver = AuthorityContext.from_role("approver-user", Role.ADMIN)
        prop_id = "prop-cross"
        proposal_time = datetime.now(timezone.utc)
        evidence_time = proposal_time + timedelta(seconds=1)
        evidence = [
            Evidence(
                evidence_id="evd-cross-1", proposal_id=prop_id,
                evidence_type=EvidenceType.TEST_RESULT,
                classification=EvidenceClassification.SUPPORTING,
                source=EvidenceSource.AUTOMATED, source_id="test",
                created_at=evidence_time, collected_at=evidence_time,
                content_hash="abc1", summary="OK",
            ),
            Evidence(
                evidence_id="evd-cross-2", proposal_id=prop_id,
                evidence_type=EvidenceType.TEST_RESULT,
                classification=EvidenceClassification.INCONCLUSIVE, # Distinct classification
                source=EvidenceSource.AUTOMATED, source_id="test",
                created_at=evidence_time, collected_at=evidence_time,
                content_hash="abc2", summary="OK",
            ),
        ]

        # Should not raise — different creator
        with patch("app.services.archon.opa.get_opa_service") as mock_opa:
            mock_opa.return_value.evaluate_policy.return_value = {"allow": True}
            
            result = await archon.approve_proposal(
                proposal_id=prop_id,
                proposal_status="pending",
                approver=approver,
                tier=DecisionTier.T2,
                evidence_list=evidence,
                proposal_created_at=proposal_time,
                proposal_creator_id="author-user",
            )
        assert result is not None


class TestProposalStatusInvariants:
    """Invariant: Only 'pending' proposals can be approved/rejected."""

    @pytest.mark.asyncio
    async def test_approved_cannot_be_approved_again(self):
        """INVARIANT: Already-approved proposals MUST NOT be re-approved."""
        archon = ArchonGates()
        approver = AuthorityContext.from_role("admin-user", Role.ADMIN)

        with pytest.raises(GovernanceError, match="pending"):
            await archon.approve_proposal(
                proposal_id="prop-done",
                proposal_status="approved",
                approver=approver,
                tier=DecisionTier.T1,
                evidence_list=[],
                proposal_created_at=datetime.now(timezone.utc),
                proposal_creator_id="other-user",
            )

    @pytest.mark.asyncio
    async def test_rejected_cannot_be_approved(self):
        """INVARIANT: Rejected proposals MUST NOT be approved."""
        archon = ArchonGates()
        approver = AuthorityContext.from_role("admin-user", Role.ADMIN)

        with pytest.raises(GovernanceError, match="pending"):
            await archon.approve_proposal(
                proposal_id="prop-rej",
                proposal_status="rejected",
                approver=approver,
                tier=DecisionTier.T1,
                evidence_list=[],
                proposal_created_at=datetime.now(timezone.utc),
                proposal_creator_id="other-user",
            )

    @pytest.mark.asyncio
    async def test_superseded_cannot_be_approved(self):
        """INVARIANT: Superseded proposals MUST NOT be approved."""
        archon = ArchonGates()
        approver = AuthorityContext.from_role("admin-user", Role.ADMIN)

        with pytest.raises(GovernanceError, match="pending"):
            await archon.approve_proposal(
                proposal_id="prop-sup",
                proposal_status="superseded",
                approver=approver,
                tier=DecisionTier.T1,
                evidence_list=[],
                proposal_created_at=datetime.now(timezone.utc),
                proposal_creator_id="other-user",
            )

    @pytest.mark.asyncio
    async def test_pending_can_be_approved(self):
        """Pending proposals with correct authority should be approvable."""
        archon = ArchonGates()
        approver = AuthorityContext.from_role("admin-user", Role.ADMIN)
        prop_id = "prop-pending"
        proposal_time = datetime.now(timezone.utc)
        evidence_time = proposal_time + timedelta(seconds=1)
        evidence = [
            Evidence(
                evidence_id="evd-pending-1", proposal_id=prop_id,
                evidence_type=EvidenceType.TEST_RESULT,
                classification=EvidenceClassification.SUPPORTING,
                source=EvidenceSource.AUTOMATED, source_id="test",
                created_at=evidence_time, collected_at=evidence_time,
                content_hash="abc3", summary="OK",
            ),
        ]

        # Should not raise
        result = await archon.approve_proposal(
            proposal_id=prop_id,
            proposal_status="pending",
            approver=approver,
            tier=DecisionTier.T1,
            evidence_list=evidence,
            proposal_created_at=proposal_time,
            proposal_creator_id="other-user",
        )
        assert result is not None


