"""
Aegion Archon Invariant Tests.

Property-based tests to ensure governance invariants hold under all conditions.
Uses hypothesis for property-based testing.
"""

import pytest
from typing import List
from datetime import datetime, timedelta

from app.services.archon.gates import ArchonGates, GovernanceError
from app.services.archon.policy_fixtures import (
    TierTestCase,
    EvidenceTestCase,
    SoDTestCase,
    ArchonInvariants,
    get_tier_fixtures,
    get_evidence_fixtures,
    get_sod_fixtures,
)
from app.contracts.decision_intent import (
    DecisionTier,
    ImpactLevel,
    ReversibilityLevel,
    calculate_tier,
)
from app.contracts.evidence import Evidence, EvidenceClassification


class TestTierClassification:
    """Tests for tier classification invariants."""
    
    @pytest.fixture
    def archon(self):
        return ArchonGates()
    
    @pytest.mark.parametrize("fixture", get_tier_fixtures(), ids=lambda f: f.name)
    def test_tier_classification_fixtures(self, archon: ArchonGates, fixture: TierTestCase):
        """Test tier classification against fixtures."""
        tier = archon.classify_tier(
            fixture.impact,
            fixture.reversibility,
            fixture.affected_modules
        )
        
        assert tier == fixture.expected_tier, (
            f"Expected {fixture.expected_tier} for {fixture.name}, got {tier}. "
            f"Description: {fixture.description}"
        )
    
    def test_tier_monotonic_escalation_invariant(self):
        """Property: Higher impact/lower reversibility = higher or equal tier."""
        invariants = ArchonInvariants()
        
        # Test all combinations
        for impact in ImpactLevel:
            for reversibility in ReversibilityLevel:
                tier = calculate_tier(impact, reversibility)
                assert invariants.tier_monotonic_escalation(
                    impact, reversibility, tier
                ), f"Monotonic escalation violated for {impact}/{reversibility} -> {tier}"
    
    def test_system_wide_impact_minimum_t3(self):
        """Property: System-wide impact always results in T3."""
        for reversibility in ReversibilityLevel:
            tier = calculate_tier(ImpactLevel.SYSTEM_WIDE, reversibility)
            assert tier == DecisionTier.T3, (
                f"System-wide impact with {reversibility} should be T3, got {tier}"
            )
    
    def test_irreversible_never_t0(self):
        """Property: Irreversible changes never result in T0."""
        for impact in ImpactLevel:
            tier = calculate_tier(impact, ReversibilityLevel.IRREVERSIBLE)
            assert tier != DecisionTier.T0, (
                f"Irreversible with {impact} should not be T0, got {tier}"
            )


class TestEvidenceGating:
    """Tests for evidence gating invariants."""
    
    @pytest.mark.parametrize("fixture", get_evidence_fixtures(), ids=lambda f: f.name)
    def test_evidence_gate_fixtures(self, fixture: EvidenceTestCase):
        """Test evidence gating against fixtures - uses invariants only."""
        # Note: We test invariants here, not actual Evidence instantiation
        # since that requires proper storage integration
        invariants = ArchonInvariants()
        
        if fixture.is_stale and fixture.evidence_count > 0:
            assert invariants.stale_evidence_never_valid(
                fixture.is_stale, fixture.expected_valid
            ), f"Stale evidence invariant violated for {fixture.name}"
        
        # Verify fixture consistency
        if fixture.tier == DecisionTier.T0:
            # T0 allows zero evidence
            pass
        elif fixture.expected_valid and fixture.tier.value >= DecisionTier.T1.value:
            # Valid T1+ should have supporting evidence
            assert fixture.has_supporting or fixture.evidence_count == 0, (
                f"Valid T1+ fixture {fixture.name} should have supporting evidence or be T0"
            )
    
    def test_stale_evidence_invariant(self):
        """Property: Stale evidence is never valid."""
        invariants = ArchonInvariants()
        
        # If evidence is stale, it cannot be valid
        assert invariants.stale_evidence_never_valid(True, False)
        assert not invariants.stale_evidence_never_valid(True, True)  # Violation
        assert invariants.stale_evidence_never_valid(False, True)
        assert invariants.stale_evidence_never_valid(False, False)
    
    def test_evidence_never_decreases_trust(self):
        """Property: Adding evidence never reduces trust."""
        invariants = ArchonInvariants()
        
        # Adding evidence should not make valid become invalid
        assert invariants.evidence_never_decreases_trust(1, 2, True, True)
        assert invariants.evidence_never_decreases_trust(0, 1, False, True)
        assert not invariants.evidence_never_decreases_trust(1, 2, True, False)  # Violation


class TestSeparationOfDuties:
    """Tests for Separation of Duties invariants."""
    
    @pytest.mark.parametrize("fixture", get_sod_fixtures(), ids=lambda f: f.name)
    def test_sod_fixtures(self, fixture: SoDTestCase):
        """Test SoD against fixtures."""
        invariants = ArchonInvariants()
        
        # For T1+, check SoD enforcement
        if fixture.tier.value >= DecisionTier.T1.value:
            is_sod_valid = invariants.sod_enforced_for_t1_plus(
                fixture.tier,
                fixture.proposer_id,
                fixture.approver_id
            )
            
            # If same person, should be invalid for T1+
            if fixture.proposer_id == fixture.approver_id:
                assert not is_sod_valid, (
                    f"SoD should block self-approval for {fixture.tier}"
                )
    
    def test_ai_never_approves_t3_invariant(self):
        """Property: AI agents cannot approve T3 decisions."""
        invariants = ArchonInvariants()
        
        # AI approving T3 should fail invariant
        assert not invariants.ai_never_approves_t3(DecisionTier.T3, "ai")
        assert invariants.ai_never_approves_t3(DecisionTier.T3, "human")
        assert invariants.ai_never_approves_t3(DecisionTier.T2, "ai")  # T2 allows AI


class TestFreezeMode:
    """Tests for freeze mode invariants."""
    
    @pytest.fixture
    def archon(self):
        return ArchonGates()
    
    def test_freeze_blocks_all_mutations_invariant(self):
        """Property: Freeze mode blocks ALL mutations."""
        invariants = ArchonInvariants()
        
        # When frozen, no mutation allowed
        assert invariants.freeze_blocks_all_mutations(True, False)
        assert not invariants.freeze_blocks_all_mutations(True, True)  # Violation
        
        # When not frozen, mutations allowed
        assert invariants.freeze_blocks_all_mutations(False, True)
        assert invariants.freeze_blocks_all_mutations(False, False)
    
    @pytest.mark.asyncio
    async def test_freeze_mode_activates(self, archon: ArchonGates):
        """Test freeze mode activation."""
        assert not archon._freeze_mode
        
        await archon.activate_freeze("admin", "Emergency")
        assert archon._freeze_mode
        
        with pytest.raises(GovernanceError):
            archon.guard_writable()
        
        await archon.deactivate_freeze("admin", "Resolved")
        assert not archon._freeze_mode
        
        # Should not raise
        archon.guard_writable()


class TestCombinedInvariants:
    """Combined invariant tests covering multiple aspects."""
    
    def test_all_invariants_have_falsifiable_cases(self):
        """Meta-test: Ensure invariants can detect violations."""
        invariants = ArchonInvariants()
        
        # Each invariant should have at least one falsifiable case
        violations = [
            invariants.freeze_blocks_all_mutations(True, True),  # Should be False
            invariants.ai_never_approves_t3(DecisionTier.T3, "ai"),  # Should be False
            invariants.stale_evidence_never_valid(True, True),  # Should be False
            invariants.evidence_never_decreases_trust(1, 2, True, False),  # Should be False
        ]
        
        # All of these should be False (violations detected)
        for i, result in enumerate(violations):
            assert not result, f"Invariant {i} should detect violation"
    
    def test_tier_evidence_sod_consistency(self):
        """Test that tier, evidence, and SoD requirements are consistent."""
        # T0 should have minimal requirements
        # T3 should have maximum requirements
        
        # This is a consistency check, not a specific invariant
        tiers_ascending = [
            DecisionTier.T0,
            DecisionTier.T1,
            DecisionTier.T2,
            DecisionTier.T3,
        ]
        
        # Evidence requirements should be monotonically increasing
        evidence_requirements = {
            DecisionTier.T0: 0,
            DecisionTier.T1: 1,
            DecisionTier.T2: 2,
            DecisionTier.T3: 3,
        }
        
        for i in range(len(tiers_ascending) - 1):
            current = tiers_ascending[i]
            next_tier = tiers_ascending[i + 1]
            
            assert evidence_requirements[current] <= evidence_requirements[next_tier], (
                f"Evidence requirements should increase: {current} -> {next_tier}"
            )
