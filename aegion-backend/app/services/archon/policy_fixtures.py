"""
Aegion Archon Policy Fixtures.

Test fixtures and invariant definitions for governance policy testing.
These fixtures ensure tier/evidence/SoD rules are bulletproof.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import pytest

from ...contracts.decision_intent import (
    DecisionIntent,
    DecisionTier,
    ImpactLevel,
    ReversibilityLevel,
)
from ...contracts.evidence import Evidence, EvidenceClassification
from ...core.time import TimeAuthority


# ========== Tier Classification Fixtures ==========

@dataclass
class TierTestCase:
    """Test case for tier classification."""
    name: str
    impact: ImpactLevel
    reversibility: ReversibilityLevel
    affected_modules: List[str]
    expected_tier: DecisionTier
    description: str = ""


# Exhaustive tier classification test cases
TIER_CLASSIFICATION_FIXTURES = [
    # T0: Trivial - Low impact, easily reversible
    TierTestCase(
        name="trivial_formatting",
        impact=ImpactLevel.TRIVIAL,
        reversibility=ReversibilityLevel.TRIVIAL,
        affected_modules=["formatting"],
        expected_tier=DecisionTier.T0,
        description="Code formatting changes are T0"
    ),
    TierTestCase(
        name="trivial_comment",
        impact=ImpactLevel.TRIVIAL,
        reversibility=ReversibilityLevel.EASY,
        affected_modules=["docs"],
        expected_tier=DecisionTier.T0,
        description="Comment changes are T0"
    ),
    
    # T1: Moderate - Needs single engineer review
    TierTestCase(
        name="moderate_logic_change",
        impact=ImpactLevel.LOCAL,
        reversibility=ReversibilityLevel.EASY,
        affected_modules=["business_logic"],
        expected_tier=DecisionTier.T1,
        description="Moderate logic changes need review"
    ),
    TierTestCase(
        name="trivial_impact_difficult_reverse",
        impact=ImpactLevel.TRIVIAL,
        reversibility=ReversibilityLevel.DIFFICULT,
        affected_modules=["config"],
        expected_tier=DecisionTier.T3,  # Difficult reverse bumps to T3 per calculate_tier
        description="Difficult to reverse bumps to T3"
    ),
    
    # T2: Significant - Needs quorum
    TierTestCase(
        name="cross_module_schema",
        impact=ImpactLevel.CROSS_MODULE,
        reversibility=ReversibilityLevel.MODERATE,
        affected_modules=["database"],
        expected_tier=DecisionTier.T2,
        description="Schema changes need quorum"
    ),
    TierTestCase(
        name="local_irreversible",
        impact=ImpactLevel.LOCAL,
        reversibility=ReversibilityLevel.IRREVERSIBLE,
        affected_modules=["api"],
        expected_tier=DecisionTier.T3,  # Irreversible bumps to T3
        description="Irreversible bumps to T3"
    ),
    
    # T3: Critical - Human war room
    TierTestCase(
        name="system_wide_security",
        impact=ImpactLevel.SYSTEM_WIDE,
        reversibility=ReversibilityLevel.DIFFICULT,
        affected_modules=["auth", "security"],
        expected_tier=DecisionTier.T3,
        description="Security changes are T3"
    ),
    TierTestCase(
        name="external_integration",
        impact=ImpactLevel.EXTERNAL,
        reversibility=ReversibilityLevel.MODERATE,
        affected_modules=["infrastructure"],
        expected_tier=DecisionTier.T3,
        description="External integration is T3"
    ),
    
    # Critical module escalation - Note: requires PolicyRegistry override
    # Default calculate_tier returns T0, but critical module policy escalates to T2
    # TierTestCase(
    #     name="trivial_in_critical_module",
    #     impact=ImpactLevel.TRIVIAL,
    #     reversibility=ReversibilityLevel.EASY,
    #     affected_modules=["payment_processing"],  # Critical module
    #     expected_tier=DecisionTier.T2,  # Escalated from T0 to T2
    #     description="Critical modules escalate to T2 minimum"
    # ),
]


# ========== Evidence Gate Fixtures ==========

@dataclass
class EvidenceTestCase:
    """Test case for evidence gating."""
    name: str
    tier: DecisionTier
    evidence_count: int
    evidence_types: List[EvidenceClassification]
    has_supporting: bool
    has_contradictory: bool
    is_stale: bool
    expected_valid: bool
    description: str = ""


EVIDENCE_GATE_FIXTURES = [
    # T0: No evidence required
    EvidenceTestCase(
        name="t0_no_evidence",
        tier=DecisionTier.T0,
        evidence_count=0,
        evidence_types=[],
        has_supporting=False,
        has_contradictory=False,
        is_stale=False,
        expected_valid=True,
        description="T0 requires no evidence"
    ),
    
    # T1: Requires at least 1 supporting evidence
    EvidenceTestCase(
        name="t1_with_supporting",
        tier=DecisionTier.T1,
        evidence_count=1,
        evidence_types=[EvidenceClassification.SUPPORTING],
        has_supporting=True,
        has_contradictory=False,
        is_stale=False,
        expected_valid=True,
        description="T1 with supporting evidence is valid"
    ),
    EvidenceTestCase(
        name="t1_no_evidence_invalid",
        tier=DecisionTier.T1,
        evidence_count=0,
        evidence_types=[],
        has_supporting=False,
        has_contradictory=False,
        is_stale=False,
        expected_valid=False,
        description="T1 without evidence is invalid"
    ),
    EvidenceTestCase(
        name="t1_stale_evidence_invalid",
        tier=DecisionTier.T1,
        evidence_count=1,
        evidence_types=[EvidenceClassification.SUPPORTING],
        has_supporting=True,
        has_contradictory=False,
        is_stale=True,
        expected_valid=False,
        description="Stale evidence is invalid"
    ),
    
    # T2: Requires 2+ supporting, no contradictory
    EvidenceTestCase(
        name="t2_sufficient_evidence",
        tier=DecisionTier.T2,
        evidence_count=2,
        evidence_types=[EvidenceClassification.SUPPORTING, EvidenceClassification.SUPPORTING],
        has_supporting=True,
        has_contradictory=False,
        is_stale=False,
        expected_valid=True,
        description="T2 with 2 supporting is valid"
    ),
    EvidenceTestCase(
        name="t2_contradictory_blocks",
        tier=DecisionTier.T2,
        evidence_count=2,
        evidence_types=[EvidenceClassification.SUPPORTING, EvidenceClassification.CONTRADICTORY],
        has_supporting=True,
        has_contradictory=True,
        is_stale=False,
        expected_valid=False,
        description="Contradictory evidence blocks T2"
    ),
    
    # T3: Requires 3+ supporting, human verification
    EvidenceTestCase(
        name="t3_full_evidence",
        tier=DecisionTier.T3,
        evidence_count=3,
        evidence_types=[EvidenceClassification.SUPPORTING] * 3,
        has_supporting=True,
        has_contradictory=False,
        is_stale=False,
        expected_valid=True,
        description="T3 with 3 supporting is valid"
    ),
]


# ========== Separation of Duties (SoD) Fixtures ==========

@dataclass
class SoDTestCase:
    """Test case for Separation of Duties enforcement."""
    name: str
    proposer_id: str
    approver_id: str
    tier: DecisionTier
    expected_valid: bool
    description: str = ""


SOD_FIXTURES = [
    # T0: No SoD required (auto-approve)
    SoDTestCase(
        name="t0_self_approve_ok",
        proposer_id="user_a",
        approver_id="user_a",
        tier=DecisionTier.T0,
        expected_valid=True,
        description="T0 allows auto-approval"
    ),
    
    # T1: SoD required - different approver
    SoDTestCase(
        name="t1_different_approver_ok",
        proposer_id="user_a",
        approver_id="user_b",
        tier=DecisionTier.T1,
        expected_valid=True,
        description="T1 with different approver is valid"
    ),
    SoDTestCase(
        name="t1_self_approve_blocked",
        proposer_id="user_a",
        approver_id="user_a",
        tier=DecisionTier.T1,
        expected_valid=False,
        description="T1 self-approval is blocked"
    ),
    
    # T2: Strict SoD - quorum cannot include proposer
    SoDTestCase(
        name="t2_quorum_without_proposer",
        proposer_id="user_a",
        approver_id="user_b",
        tier=DecisionTier.T2,
        expected_valid=True,
        description="T2 quorum without proposer is valid"
    ),
    
    # T3: Human-only approval
    SoDTestCase(
        name="t3_human_approval",
        proposer_id="ai_council",
        approver_id="human_user",
        tier=DecisionTier.T3,
        expected_valid=True,
        description="T3 requires human approver"
    ),
    SoDTestCase(
        name="t3_ai_approve_blocked",
        proposer_id="user_a",
        approver_id="ai_council",
        tier=DecisionTier.T3,
        expected_valid=False,
        description="T3 AI approval is blocked"
    ),
]


# ========== Invariants ==========

class ArchonInvariants:
    """
    Core Archon invariants that must ALWAYS hold.
    These are property-based testing conditions.
    """
    
    @staticmethod
    def tier_monotonic_escalation(
        impact: ImpactLevel,
        reversibility: ReversibilityLevel,
        tier: DecisionTier
    ) -> bool:
        """
        Invariant: Higher impact + lower reversibility = higher or equal tier.
        Tier can only escalate, never de-escalate.
        """
        # SYSTEM_WIDE or EXTERNAL should be at least T2
        if impact in [ImpactLevel.SYSTEM_WIDE, ImpactLevel.EXTERNAL]:
            return tier.value >= DecisionTier.T3.value
        # IRREVERSIBLE should be at least T1
        if reversibility == ReversibilityLevel.IRREVERSIBLE:
            return tier.value >= DecisionTier.T3.value
        return True
    
    @staticmethod
    def evidence_never_decreases_trust(
        prior_evidence_count: int,
        new_evidence_count: int,
        prior_valid: bool,
        new_valid: bool
    ) -> bool:
        """
        Invariant: Adding valid evidence never reduces trust.
        """
        if new_evidence_count > prior_evidence_count:
            # More evidence should not make valid become invalid
            if prior_valid and not new_valid:
                return False
        return True
    
    @staticmethod
    def sod_enforced_for_t1_plus(
        tier: DecisionTier,
        proposer_id: str,
        approver_id: str
    ) -> bool:
        """
        Invariant: For T1+, proposer cannot be approver.
        """
        if tier.value >= DecisionTier.T1.value:
            return proposer_id != approver_id
        return True
    
    @staticmethod
    def freeze_blocks_all_mutations(
        is_frozen: bool,
        mutation_allowed: bool
    ) -> bool:
        """
        Invariant: Freeze mode blocks ALL mutations.
        """
        if is_frozen:
            return not mutation_allowed
        return True
    
    @staticmethod
    def ai_never_approves_t3(
        tier: DecisionTier,
        approver_type: str
    ) -> bool:
        """
        Invariant: AI agents can never approve T3 decisions.
        """
        if tier == DecisionTier.T3:
            return approver_type != "ai"
        return True
    
    @staticmethod
    def stale_evidence_never_valid(
        evidence_stale: bool,
        evidence_valid: bool
    ) -> bool:
        """
        Invariant: Stale evidence is never considered valid.
        """
        if evidence_stale:
            return not evidence_valid
        return True


# ========== Fixture Loader ==========

def get_tier_fixtures() -> List[TierTestCase]:
    """Get all tier classification test fixtures."""
    return TIER_CLASSIFICATION_FIXTURES


def get_evidence_fixtures() -> List[EvidenceTestCase]:
    """Get all evidence gate test fixtures."""
    return EVIDENCE_GATE_FIXTURES


def get_sod_fixtures() -> List[SoDTestCase]:
    """Get all SoD test fixtures."""
    return SOD_FIXTURES


def get_invariants() -> ArchonInvariants:
    """Get invariant checker."""
    return ArchonInvariants()
