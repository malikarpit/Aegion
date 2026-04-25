"""
Tests for Cost Optimization Stack — Sections 1.7.

Covers:
    - TokenBudgetManager: budget lookups, overrides, cost estimates, savings
    - AdaptiveCouncil: complexity mapping, model selection, profile conversion
    - SpeculativeDecoder: model selection, draft/verify fallback chain

These modules form the core cost optimization pipeline:
    Gateway → Adaptive Council → Token Budget → Speculative Decoder
"""

import pytest

from app.services.council_kernel.token_budget import (
    TokenBudgetManager,
    token_budget,
    BUDGETS,
    DEFAULT_BUDGET,
)
from app.services.council_kernel.adaptive_council import (
    AdaptiveCouncil,
    adaptive_council,
    SIZE_POLICIES,
    PROFILE_TO_COMPLEXITY,
)
from app.services.council_kernel.speculative import (
    SpeculativeDecoder,
    speculative_decoder,
    SPECULATIVE_INTENTS,
)
from app.services.council_kernel.types import CouncilProfile


# ══════════════════════════════════════════════════════════════════════════════
# TOKEN BUDGET MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class TestTokenBudget:
    """Token budget lookup and cost estimation."""

    def test_known_budget(self):
        """Known (intent, complexity) pair returns correct budget."""
        b = token_budget.get_budget("debug", "simple")
        assert b["max_tokens"] == 300
        assert b["temperature"] == 0.3

    def test_complex_architecture(self):
        b = token_budget.get_budget("architecture", "complex")
        assert b["max_tokens"] == 4000
        assert b["temperature"] == 0.5

    def test_unknown_falls_to_default(self):
        """Unknown intent/complexity falls back to DEFAULT_BUDGET."""
        b = token_budget.get_budget("alien_intent", "quantum_level")
        assert b["max_tokens"] == DEFAULT_BUDGET["max_tokens"]

    def test_user_override_max_tokens(self):
        """User override should replace max_tokens."""
        b = token_budget.get_budget("debug", "simple", user_override=999)
        assert b["max_tokens"] == 999
        # Temperature should stay unchanged
        assert b["temperature"] == 0.3

    def test_user_override_zero_ignored(self):
        """Zero/negative override should be ignored."""
        b = token_budget.get_budget("debug", "simple", user_override=0)
        assert b["max_tokens"] == 300

    def test_case_insensitive(self):
        """Intent and complexity should be case-insensitive."""
        b = token_budget.get_budget("DEBUG", "SIMPLE")
        assert b["max_tokens"] == 300

    def test_all_budgets_have_max_tokens(self):
        """Every budget entry must have max_tokens and temperature."""
        for key, budget in BUDGETS.items():
            assert "max_tokens" in budget, f"{key} missing max_tokens"
            assert "temperature" in budget, f"{key} missing temperature"
            assert budget["max_tokens"] > 0


class TestTokenBudgetCost:
    """Cost estimation from budgets."""

    def test_estimate_output_cost(self):
        """Cost estimate should be non-negative."""
        budget = {"max_tokens": 1000, "temperature": 0.5}
        cost = token_budget.estimate_output_cost(budget, "gemini-2.0-flash")
        assert cost >= 0.0

    def test_unknown_model_returns_zero(self):
        """Unknown model should return 0 cost."""
        budget = {"max_tokens": 1000}
        cost = token_budget.estimate_output_cost(budget, "unknown-model-xyz")
        assert cost == 0.0

    def test_savings_estimate(self):
        """Savings should be non-negative."""
        budget = {"max_tokens": 300}
        savings = token_budget.savings_estimate(budget, "gemini-2.0-flash")
        assert savings >= 0.0

    def test_savings_zero_when_uncapped(self):
        """No savings when budget >= uncapped default."""
        budget = {"max_tokens": 5000}
        savings = token_budget.savings_estimate(budget, "gemini-2.0-flash", uncapped_default=4096)
        assert savings == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# ADAPTIVE COUNCIL
# ══════════════════════════════════════════════════════════════════════════════

class TestAdaptiveCouncilConfig:
    """Council configuration from complexity."""

    def test_simple_config(self):
        config = adaptive_council.get_council_config("simple")
        assert config["model_count"] == 1
        assert config["strategy"] == "cascade"
        assert config["prefer_cheap"] is True

    def test_critical_config(self):
        config = adaptive_council.get_council_config("critical")
        assert config["model_count"] == 4
        assert config["strategy"] == "full_debate_with_red_team"
        assert config["prefer_cheap"] is False

    def test_unknown_falls_to_medium(self):
        config = adaptive_council.get_council_config("unknown_complexity")
        assert config == SIZE_POLICIES["medium"]

    def test_user_override(self):
        config = adaptive_council.get_council_config("simple", user_override={"model_count": 3})
        assert config["model_count"] == 3  # Overridden
        assert config["strategy"] == "cascade"  # Not overridden

    def test_profile_string_accepted(self):
        """CouncilProfile value strings like 'moderate' should map to medium."""
        config = adaptive_council.get_council_config("moderate")
        assert config["model_count"] == SIZE_POLICIES["medium"]["model_count"]

    def test_case_insensitive(self):
        config = adaptive_council.get_council_config("COMPLEX")
        assert config["model_count"] == 3

    def test_all_policies_have_required_fields(self):
        required = {"model_count", "council_type", "strategy", "max_rounds", "prefer_cheap"}
        for complexity, policy in SIZE_POLICIES.items():
            for field in required:
                assert field in policy, f"{complexity} missing {field}"


class TestAdaptiveCouncilProfile:
    """Profile to complexity mapping."""

    def test_trivial_maps_to_simple(self):
        result = adaptive_council.profile_to_complexity(CouncilProfile.TRIVIAL)
        assert result == "simple"

    def test_critical_maps_to_critical(self):
        result = adaptive_council.profile_to_complexity(CouncilProfile.CRITICAL)
        assert result == "critical"

    def test_all_profiles_mapped(self):
        """Every CouncilProfile value should have a mapping."""
        for profile in CouncilProfile:
            result = adaptive_council.profile_to_complexity(profile)
            assert result in SIZE_POLICIES or result == "medium"


# ══════════════════════════════════════════════════════════════════════════════
# SPECULATIVE DECODER
# ══════════════════════════════════════════════════════════════════════════════

class TestSpeculativeDecoder:
    """Speculative draft-verify pattern."""

    def test_intents_configured(self):
        """Speculative decoding should be configured for generation-heavy intents."""
        assert "generate" in SPECULATIVE_INTENTS
        assert "code_review" in SPECULATIVE_INTENTS
        assert "architecture" in SPECULATIVE_INTENTS

    def test_non_generation_intents_excluded(self):
        """Simple intents should not trigger speculative decoding."""
        assert "debug" not in SPECULATIVE_INTENTS
        assert "general" not in SPECULATIVE_INTENTS

    def test_singleton_exists(self):
        assert speculative_decoder is not None
        assert isinstance(speculative_decoder, SpeculativeDecoder)


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT GATEWAY (basic)
# ══════════════════════════════════════════════════════════════════════════════

class TestPromptGateway:
    """Prompt gateway module integrity."""

    def test_gateway_importable(self):
        from app.services.council_kernel.prompt_gateway import PromptGateway, prompt_gateway
        assert prompt_gateway is not None
        assert isinstance(prompt_gateway, PromptGateway)

    def test_session_memory(self):
        from app.services.council_kernel.prompt_gateway import PromptGateway
        gw = PromptGateway()
        mem = gw._get_memory("test-ws")
        assert len(mem) == 0
        mem.append({"role": "user", "content": "hello"})
        assert len(gw._get_memory("test-ws")) == 1

    def test_memory_max_size(self):
        from app.services.council_kernel.prompt_gateway import PromptGateway
        gw = PromptGateway()
        mem = gw._get_memory("test-ws")
        for i in range(10):
            mem.append({"role": "user", "content": f"msg {i}"})
        assert len(mem) == gw.MAX_SESSION_MEMORY  # Capped at 5
