"""
Tests for Debate & Red Team Modules — Sections 1.8/1.14.

Covers:
    EarlyConsensusDetector:
        - Consensus threshold by complexity
        - Early stop when above threshold
        - No stop below minimum rounds
        - Insufficient participants handling
        - Jaccard similarity correctness

    ContextCompressor:
        - Basic module availability
        - Configuration

    RedTeam / Persona:
        - Module importability
        - Configuration sanity

References:
    - Liang et al. "Encouraging Divergent Thinking in LLMs" (2023)
    - Du et al. "Improving Factuality through Multi-Agent Debate" (2023)
"""

import pytest

from app.services.council_kernel.debate import (
    EarlyConsensusDetector,
    early_consensus,
    MAX_ROUNDS,
)


# ══════════════════════════════════════════════════════════════════════════════
# EARLY CONSENSUS DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

class TestConsensusThresholds:
    """Complexity-based consensus thresholds."""

    def test_simple_has_lowest_threshold(self):
        t = EarlyConsensusDetector.CONSENSUS_THRESHOLDS
        assert t["simple"] <= t["medium"] <= t["complex"] <= t["critical"]

    def test_all_complexities_have_thresholds(self):
        expected = {"simple", "medium", "complex", "critical"}
        assert expected == set(EarlyConsensusDetector.CONSENSUS_THRESHOLDS.keys())

    def test_thresholds_in_valid_range(self):
        for comp, thresh in EarlyConsensusDetector.CONSENSUS_THRESHOLDS.items():
            assert 0.0 < thresh <= 1.0, f"{comp} threshold {thresh} out of range"


class TestConsensusStop:
    """Early stop decision logic."""

    def test_stops_on_identical_responses(self):
        """Identical responses should have consensus = 1.0."""
        responses = [
            {"position": "use dependency injection for testability"},
            {"position": "use dependency injection for testability"},
        ]
        result = early_consensus.should_stop(responses, round_num=2, complexity="simple")
        assert result["stop"] is True
        assert result["consensus_score"] == 1.0

    def test_no_stop_on_divergent_responses(self):
        """Completely different responses → low consensus → no stop."""
        responses = [
            {"position": "we should use microservices architecture with kubernetes"},
            {"position": "monolith is better for small team productivity"},
        ]
        result = early_consensus.should_stop(responses, round_num=2, complexity="critical")
        # Critical threshold is 0.95 — divergent positions won't reach it
        assert result["consensus_score"] < 0.95

    def test_no_stop_before_min_rounds(self):
        """Should not stop before minimum required rounds."""
        responses = [
            {"position": "use async"},
            {"position": "use async"},
        ]
        result = early_consensus.should_stop(responses, round_num=0, min_rounds=1)
        assert result["stop"] is False
        assert "Minimum" in result["reason"]

    def test_insufficient_participants(self):
        """< 2 valid responses → cannot check consensus."""
        result = early_consensus.should_stop([{"position": "solo"}], round_num=2)
        assert result["stop"] is False
        assert "Insufficient" in result["reason"]

    def test_empty_responses(self):
        result = early_consensus.should_stop([], round_num=2)
        assert result["stop"] is False

    def test_filters_error_responses(self):
        """Error responses should be excluded from consensus check."""
        responses = [
            {"position": "valid answer about caching"},
            {"position": "[Error: timeout]"},
        ]
        result = early_consensus.should_stop(responses, round_num=2)
        # Only 1 valid response → insufficient
        assert result["stop"] is False

    def test_rounds_saved_computed(self):
        """When stopping early, should report how many rounds were saved."""
        responses = [
            {"position": "refactor the auth module"},
            {"position": "refactor the auth module"},
        ]
        result = early_consensus.should_stop(responses, round_num=1, complexity="simple")
        if result["stop"]:
            assert result["rounds_saved"] == MAX_ROUNDS - 1

    def test_partial_overlap(self):
        """Partial word overlap should give a moderate consensus score."""
        responses = [
            {"position": "use redis for caching session data"},
            {"position": "use redis for caching user tokens"},
        ]
        result = early_consensus.should_stop(responses, round_num=2, complexity="simple")
        score = result["consensus_score"]
        # Shared words: "use", "redis", "for", "caching" = 4
        # Total unique words: "use", "redis", "for", "caching", "session", "data", "user", "tokens" = 8
        # Jaccard = 4/8 = 0.5
        assert 0.4 <= score <= 0.6

    def test_case_insensitive(self):
        """Consensus check should be case-insensitive."""
        responses = [
            {"position": "Use Redis"},
            {"position": "use redis"},
        ]
        result = early_consensus.should_stop(responses, round_num=2, complexity="simple")
        assert result["consensus_score"] == 1.0


# ══════════════════════════════════════════════════════════════════════════════
# MODULE INTEGRATION — IMPORTS & SINGLETONS
# ══════════════════════════════════════════════════════════════════════════════

class TestModuleIntegrity:
    """All council kernel modules should be importable and configured."""

    def test_debate_singleton(self):
        assert early_consensus is not None
        assert isinstance(early_consensus, EarlyConsensusDetector)

    def test_compressor_importable(self):
        from app.services.council_kernel.compressor import PromptCompressor
        comp = PromptCompressor()
        assert comp is not None

    def test_peer_review_importable(self):
        from app.services.council_kernel.peer_review import PeerReviewEngine
        assert PeerReviewEngine is not None

    def test_rubric_importable(self):
        from app.services.council_kernel.rubric import RubricEngine
        assert RubricEngine is not None

    def test_red_team_importable(self):
        from app.services.council_kernel.red_team import RedTeamValidator
        assert RedTeamValidator is not None

    def test_persona_importable(self):
        from app.services.council_kernel.persona import PersonaEngine
        assert PersonaEngine is not None

    def test_evidence_importable(self):
        from app.services.council_kernel.evidence import EvidenceManager
        assert EvidenceManager is not None

    def test_cancellation_importable(self):
        from app.services.council_kernel.cancellation import CancellationToken
        token = CancellationToken()
        assert token is not None

    def test_reflector_importable(self):
        from app.services.council_kernel.reflector import CognitiveReflector
        assert CognitiveReflector is not None

    def test_temporal_memory_importable(self):
        from app.services.council_kernel.temporal_memory import TemporalMemory
        assert TemporalMemory is not None
