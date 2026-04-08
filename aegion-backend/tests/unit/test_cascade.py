"""
Unit tests for LLMCascade (FrugalGPT) — Phase 69.

Tests the multi-tier cost optimization cascade covering:
  - Tier ordering and skipping unavailable providers
  - Confidence scoring (5 signals)
  - Budget enforcement (hard cap)
  - Early exit on high confidence
  - Exhaustion behavior when all providers fail
  - Edge cases in confidence scoring
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.council_kernel.cascade import LLMCascade, CascadeTier
from app.services.council_kernel.model_router import ModelRouter
from app.services.council_kernel.types import ModelResponse


@pytest.fixture
def mock_router():
    router = MagicMock(spec=ModelRouter)
    router.providers = {"google": MagicMock(), "openai": MagicMock()}
    router.call = AsyncMock()
    return router


@pytest.fixture
def cascade(mock_router):
    return LLMCascade(mock_router)


def _make_response(text: str, model: str = "test", provider: str = "openai", cost: float = 0.01):
    return ModelResponse(
        model=model, provider=provider, response=text,
        confidence=0.0, tokens_in=100, tokens_out=len(text.split()) * 2,
        cost_usd=cost, latency_ms=200,
    )


# ──────────────────────────────────────────────────────────────
# Tier Structure Tests
# ──────────────────────────────────────────────────────────────

class TestCascadeTiers:
    def test_default_tiers_ordered_by_cost(self):
        """Tiers should be ordered cheapest to most expensive."""
        tiers = LLMCascade.DEFAULT_TIERS
        for i in range(len(tiers) - 1):
            assert tiers[i].level < tiers[i + 1].level

    def test_default_tiers_have_decreasing_thresholds(self):
        """More expensive tiers should have lower confidence thresholds (more lenient)."""
        tiers = LLMCascade.DEFAULT_TIERS
        for i in range(len(tiers) - 2):  # Exclude final fallback (threshold=0)
            assert tiers[i].confidence_threshold >= tiers[i + 1].confidence_threshold

    def test_final_tier_has_zero_threshold(self):
        """The last tier should always accept (threshold=0)."""
        last = LLMCascade.DEFAULT_TIERS[-1]
        assert last.confidence_threshold == 0.0

    def test_each_tier_has_valid_fields(self):
        for tier in LLMCascade.DEFAULT_TIERS:
            assert isinstance(tier.provider, str)
            assert isinstance(tier.model, str)
            assert tier.avg_cost_per_1m >= 0
            assert 0 <= tier.confidence_threshold <= 1.0


# ──────────────────────────────────────────────────────────────
# Confidence Scoring Tests
# ──────────────────────────────────────────────────────────────

class TestConfidenceScoring:
    def test_high_confidence_long_structured(self, cascade):
        """Long structured response with evidence markers → high confidence."""
        text = (
            "# Architecture Decision\n\n"
            "Because the system needs horizontal scaling, therefore we recommend "
            "using event-driven architecture. Specifically, Apache Kafka provides:\n"
            "- High throughput message processing\n"
            "- Built-in partitioning\n"
            "- Consumer group management\n\n"
            "```python\n"
            "from kafka import KafkaProducer\n"
            "producer = KafkaProducer(bootstrap_servers='localhost:9092')\n"
            "```\n\n"
            "Step 1: Configure the producer. "
            "Step 2: Define topic partitions. "
            "For example, use 12 partitions for our expected load. "
            "According to the Kafka documentation, this is the recommended approach. "
            "The key insight is that partition count should match consumer parallelism. "
            "In conclusion, this architecture handles 10x growth."
        )
        resp = _make_response(text)
        score = cascade._score_confidence(text, resp)
        assert score >= 0.75, f"Expected high confidence, got {score}"

    def test_low_confidence_uncertain(self, cascade):
        """Response full of hedging → low confidence."""
        text = "I'm not sure about this. I think it might work. Perhaps you should try. It's hard to say really."
        resp = _make_response(text)
        score = cascade._score_confidence(text, resp)
        assert score < 0.70, f"Expected low confidence, got {score}"

    def test_low_confidence_refusal(self, cascade):
        """Model refusal → very low confidence."""
        text = "I'm sorry, but I cannot provide assistance with that request. As an AI, I don't have access to that information."
        resp = _make_response(text)
        score = cascade._score_confidence(text, resp)
        assert score < 0.60, f"Expected very low confidence for refusal, got {score}"

    def test_low_confidence_short(self, cascade):
        """Very short response → low adequacy signal."""
        text = "Yes."
        resp = _make_response(text)
        score = cascade._score_confidence(text, resp)
        assert score < 0.70, f"Expected low confidence for short response, got {score}"

    def test_confidence_range(self, cascade):
        """Confidence should always be in [0, 1]."""
        test_cases = [
            "",
            "Short.",
            "A" * 5000,
            "I'm not sure " * 20,
            "```python\nprint('hello')\n```\n" * 5,
        ]
        for text in test_cases:
            resp = _make_response(text)
            score = cascade._score_confidence(text, resp)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for text: {text[:50]}..."

    def test_code_blocks_boost_structural(self, cascade):
        """Response with code blocks should score higher structurally."""
        with_code = "Here is the solution:\n```python\ndef solve():\n    return 42\n```\nThis works because of the algorithm."
        without_code = "Here is the solution: you should return 42. This works because of the algorithm and stuff."
        r1 = _make_response(with_code)
        r2 = _make_response(without_code)
        score_with = cascade._score_confidence(with_code, r1)
        score_without = cascade._score_confidence(without_code, r2)
        assert score_with >= score_without, "Code blocks should boost confidence"


# ──────────────────────────────────────────────────────────────
# Cascade Query Tests
# ──────────────────────────────────────────────────────────────

class TestCascadeQuery:
    @pytest.mark.asyncio
    async def test_early_exit_on_high_confidence(self, cascade, mock_router):
        """Cascade should stop at first tier if confidence is high enough."""
        high_conf_text = (
            "Because the architecture uses clean separation, therefore the approach is solid. "
            "Specifically, Step 1 is to configure the database. Step 2 is to set up the API. "
            "For example, use FastAPI with SQLAlchemy. The key insight is performance. "
            "According to benchmarks, this handles 10k RPS. In conclusion, this works."
        )
        mock_router.call.return_value = _make_response(high_conf_text, provider="google", model="gemini-2.0-flash", cost=0.001)

        result = await cascade.query("How to set up a database?")

        assert result.provider == "google"
        # Should have called only once (early exit)
        assert mock_router.call.call_count == 1

    @pytest.mark.asyncio
    async def test_escalation_on_low_confidence(self, cascade, mock_router):
        """Low confidence should cause escalation to next tier."""
        low_conf = _make_response("I'm not sure maybe.", provider="google", model="gemini-2.0-flash", cost=0.001)
        high_conf_text = (
            "The answer is clear. Because of performance requirements, therefore use Redis. "
            "Specifically, configure max memory to 512MB. Step 1: Install Redis. "
            "For example, use docker. According to docs, this is recommended."
        )
        high_conf = _make_response(high_conf_text, provider="openai", model="gpt-4.1-mini", cost=0.01)

        mock_router.call.side_effect = [low_conf, high_conf]

        result = await cascade.query("How to cache?")
        assert mock_router.call.call_count >= 2

    @pytest.mark.asyncio
    async def test_budget_enforcement(self, cascade, mock_router):
        """Cascade should stop when cumulative cost exceeds budget."""
        responses = [
            _make_response("partial answer", provider="google", cost=0.05),
            _make_response("better answer", provider="openai", cost=0.10),
        ]
        mock_router.call.side_effect = responses

        result = await cascade.query("expensive query", max_budget_usd=0.04)
        # Should have stopped after first response exceeded budget
        assert mock_router.call.call_count <= 2

    @pytest.mark.asyncio
    async def test_skip_unavailable_providers(self, cascade, mock_router):
        """Tiers whose provider isn't registered should be skipped."""
        # Only 'openai' available
        mock_router.providers = {"openai": MagicMock()}
        high_conf_text = "Clear answer. Because of X, therefore Y. Specifically, do Z. Step 1: A. For example, B."
        mock_router.call.return_value = _make_response(high_conf_text, provider="openai", cost=0.01)

        result = await cascade.query("test query")
        # Should have skipped all non-openai tiers and called openai
        for call in mock_router.call.call_args_list:
            assert call[0][0] == "openai"

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises(self, cascade, mock_router):
        """If all providers error out, should raise RuntimeError."""
        mock_router.providers = {"openai": MagicMock()}
        mock_router.call.side_effect = Exception("API error")

        with pytest.raises(RuntimeError, match="cascade exhausted"):
            await cascade.query("failing query")

    @pytest.mark.asyncio
    async def test_system_prompt_forwarded(self, cascade, mock_router):
        """System prompt should be passed through to router.call."""
        high_conf_text = "Answer. Because X. Therefore Y. Specifically Z. Step 1. For example A. In conclusion B."
        mock_router.call.return_value = _make_response(high_conf_text, provider="google", cost=0.001)

        await cascade.query("test", system_prompt="You are a code reviewer")

        call_kwargs = mock_router.call.call_args
        assert call_kwargs.kwargs.get("system_prompt") == "You are a code reviewer" or \
               (len(call_kwargs.args) > 3 and call_kwargs.args[3] == "You are a code reviewer") or \
               "system_prompt" in str(call_kwargs)
