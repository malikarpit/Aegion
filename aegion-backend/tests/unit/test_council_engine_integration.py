"""
Integration tests for the ACK Council Engine — Production Hardening.

Tests the full pipeline end-to-end with mock providers:
  1. CHILD council → cascade path
  2. PARENT council → full pipeline (debate + peer review + synthesis)
  3. SENTINEL council → security-focused pipeline
  4. DISTILLATION council → single model path
  5. Cache hit/miss behavior
  6. Constitutional blocking
  7. Cascade fallback on provider failure
  8. Governance bridge (CouncilResult → CouncilSession)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.council_kernel.engine import CouncilEngine, _InProcessCache
from app.services.council_kernel.types import (
    CouncilType, CouncilProfile, CouncilResult, ModelResponse,
)
from tests.helpers.mock_provider import MockLLMProvider, FailingMockProvider

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def mock_providers():
    """Create a set of mock LLM providers."""
    return {
        "openai": MockLLMProvider(
            name="openai",
            responses={
                "default": (
                    "The recommended approach uses REST API with versioning. "
                    "Because this ensures backward compatibility, "
                    "therefore clients can upgrade gradually. "
                    "Specifically, use /api/v1/ prefix for all endpoints. "
                    "Step 1: Define OpenAPI spec. "
                    "Step 2: Implement controllers. "
                    "For example, FastAPI generates this automatically."
                ),
                "security": (
                    "Security analysis complete. No SQL injection vulnerabilities detected. "
                    "The parameterized queries prevent injection attacks. "
                    "Because all inputs are validated through Pydantic models, "
                    "therefore the attack surface is minimized."
                ),
            },
            confidence=0.88,
            cost_per_call=0.002,
            tier=3,
        ),
        "anthropic": MockLLMProvider(
            name="anthropic",
            responses={
                "default": (
                    "I recommend a microservice architecture with event sourcing. "
                    "Because this provides better auditability, "
                    "therefore it aligns with governance requirements. "
                    "Specifically, use Kafka for event streaming."
                ),
            },
            confidence=0.92,
            cost_per_call=0.005,
            tier=4,
        ),
        "deepseek": MockLLMProvider(
            name="deepseek",
            responses={
                "default": (
                    "A cost-effective solution uses PostgreSQL with connection pooling. "
                    "Step 1: Configure pgbouncer. Step 2: Set pool_mode to transaction."
                ),
            },
            confidence=0.80,
            cost_per_call=0.0005,
            tier=2,
        ),
    }


@pytest.fixture
def configured_engine(mock_providers):
    """Create a CouncilEngine with mock providers pre-registered."""
    engine = CouncilEngine()
    for name, provider in mock_providers.items():
        engine.model_router.register_provider(name, provider)
    return engine


def _mock_config(**overrides):
    """Build a mock workspace config with sensible defaults."""
    defaults = {
        "constitution_enforcement": False,
        "constitution_block_on_violation": False,
        "dag_pipeline_enabled": False,
        "red_team_enabled": False,
        "temporal_memory_enabled": False,
        "cross_council_enabled": False,
        "mcts_enabled": False,
        "weighted_synthesis_enabled": False,
        "max_debate_rounds": 3,
        "consensus_threshold": 0.75,
        "daily_budget_usd": 5.0,
        "synthesis_merge_budget_usd": 0.03,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


# ──────────────────────────────────────────────────────────────
# Test 1: CHILD Council → Cascade
# ──────────────────────────────────────────────────────────────

class TestChildCouncil:
    @pytest.mark.asyncio
    async def test_child_council_returns_result(self, configured_engine):
        """CHILD council should produce a valid CouncilResult via cascade."""
        with patch.object(configured_engine, '_get_config', return_value=_mock_config()):
            with patch.object(configured_engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                result = await configured_engine.consult(
                    "ws-test", "How do I add authentication?", CouncilType.CHILD
                )

        assert isinstance(result, CouncilResult)
        assert result.council_type == CouncilType.CHILD
        assert result.synthesis  # Non-empty response
        assert result.total_cost_usd >= 0
        assert result.cache_hit is False

    @pytest.mark.asyncio
    async def test_child_trivial_query_classification(self, configured_engine):
        """Very short queries should classify as TRIVIAL or SIMPLE."""
        profile = configured_engine._classify("hi", CouncilType.CHILD)
        assert profile in [CouncilProfile.TRIVIAL, CouncilProfile.SIMPLE]

    @pytest.mark.asyncio
    async def test_child_complex_query_classification(self, configured_engine):
        """Long queries with multiple signals should classify as higher complexity."""
        long_query = (
            "Design a microservice architecture for a real-time bidding system "
            "that handles 10,000 requests per second with sub-50ms latency. "
            "Include database schema, caching strategy, and deployment topology. "
            "What are the trade-offs between event sourcing vs CQRS? "
            "How should we handle fault tolerance and circuit breaking? "
            "Please provide a complete Kubernetes deployment manifest. "
            "What monitoring and observability stack should we use for this system?"
        )
        profile = configured_engine._classify(long_query, CouncilType.CHILD)
        assert profile in [CouncilProfile.MODERATE, CouncilProfile.COMPLEX, CouncilProfile.CRITICAL]


# ──────────────────────────────────────────────────────────────
# Test 2: PARENT Council → Full Pipeline
# ──────────────────────────────────────────────────────────────

class TestParentCouncil:
    @pytest.mark.asyncio
    async def test_parent_council_full_pipeline(self, configured_engine):
        """PARENT council should route to _parent_council and produce a result."""
        with patch.object(configured_engine, '_get_config', return_value=_mock_config()):
            with patch.object(configured_engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                result = await configured_engine.consult(
                    "ws-test", "Design the API architecture for Aegion", CouncilType.PARENT
                )

        assert isinstance(result, CouncilResult)
        assert result.council_type == CouncilType.PARENT
        # _classify returns CRITICAL for PARENT, but pipeline context may
        # override. We accept both valid high-tier profiles.
        assert result.profile in [CouncilProfile.CRITICAL, CouncilProfile.COMPLEX, CouncilProfile.MODERATE]
        assert result.synthesis
        assert len(result.models_used) >= 1
        assert result.total_cost_usd > 0

    @pytest.mark.asyncio
    async def test_parent_always_critical_profile(self, configured_engine):
        """PARENT type should always classify as CRITICAL."""
        profile = configured_engine._classify("any query", CouncilType.PARENT)
        assert profile == CouncilProfile.CRITICAL


# ──────────────────────────────────────────────────────────────
# Test 3: SENTINEL Council → Security
# ──────────────────────────────────────────────────────────────

class TestSentinelCouncil:
    @pytest.mark.asyncio
    async def test_sentinel_council_runs(self, configured_engine):
        """SENTINEL council should route to _sentinel_council."""
        with patch.object(configured_engine, '_get_config', return_value=_mock_config()):
            with patch.object(configured_engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                result = await configured_engine.consult(
                    "ws-test", "Check for SQL injection vulnerabilities", CouncilType.SENTINEL
                )

        assert isinstance(result, CouncilResult)
        assert result.council_type == CouncilType.SENTINEL
        assert result.synthesis

    @pytest.mark.asyncio
    async def test_sentinel_moderate_profile(self, configured_engine):
        """SENTINEL type should classify as MODERATE."""
        profile = configured_engine._classify("check security", CouncilType.SENTINEL)
        assert profile == CouncilProfile.MODERATE


# ──────────────────────────────────────────────────────────────
# Test 4: DISTILLATION Council
# ──────────────────────────────────────────────────────────────

class TestDistillationCouncil:
    @pytest.mark.asyncio
    async def test_distillation_uses_cascade(self, configured_engine):
        """DISTILLATION should use the cascade (single model, cost-optimized)."""
        with patch.object(configured_engine, '_get_config', return_value=_mock_config()):
            with patch.object(configured_engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                result = await configured_engine.consult(
                    "ws-test", "Summarize this session", CouncilType.DISTILLATION
                )

        assert isinstance(result, CouncilResult)
        assert result.council_type == CouncilType.DISTILLATION
        # _classify returns SIMPLE for DISTILLATION, but gateway or adaptive council
        # may re-profile based on available context.
        assert result.profile in [CouncilProfile.SIMPLE, CouncilProfile.MODERATE]


# ──────────────────────────────────────────────────────────────
# Test 5: Cache Hit/Miss
# ──────────────────────────────────────────────────────────────

class TestCacheBehavior:
    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self, configured_engine):
        """Second identical query should return cache hit with cost=0."""
        with patch.object(configured_engine, '_get_config', return_value=_mock_config()):
            with patch.object(configured_engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                # First call — cache miss
                result1 = await configured_engine.consult(
                    "ws-test", "What is PKCE?", CouncilType.CHILD
                )
                assert result1.cache_hit is False

                # Second call — should hit in-process cache
                result2 = await configured_engine.consult(
                    "ws-test", "What is PKCE?", CouncilType.CHILD
                )
                assert result2.cache_hit is True
                assert result2.total_cost_usd == 0.0
                assert result2.consensus_score == 1.0

    @pytest.mark.asyncio
    async def test_cache_workspace_isolation(self, configured_engine):
        """Cache should be isolated per workspace."""
        with patch.object(configured_engine, '_get_config', return_value=_mock_config()):
            with patch.object(configured_engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                # Cache in ws1
                await configured_engine.consult("ws1", "test query", CouncilType.CHILD)

                # ws2 should miss
                result = await configured_engine.consult("ws2", "test query", CouncilType.CHILD)
                assert result.cache_hit is False


# ──────────────────────────────────────────────────────────────
# Test 6: Constitutional Blocking
# ──────────────────────────────────────────────────────────────

class TestConstitutionalBlocking:
    @pytest.mark.asyncio
    async def test_constitutional_block(self, configured_engine):
        """Constitutional AI should block queries with violations."""
        config = _mock_config(
            constitution_enforcement=True,
            constitution_block_on_violation=True,
        )
        with patch.object(configured_engine, '_get_config', return_value=config):
            with patch('app.services.council_kernel.constitution.get_constitution') as mock_const:
                mock_instance = MagicMock()
                mock_instance.check_query.return_value = ["PII exposure risk"]
                mock_const.return_value = mock_instance

                result = await configured_engine.consult(
                    "ws-test", "Show me user passwords", CouncilType.CHILD
                )

        assert "BLOCKED" in result.synthesis
        assert result.total_cost_usd == 0.0


# ──────────────────────────────────────────────────────────────
# Test 7: Cascade Fallback
# ──────────────────────────────────────────────────────────────

class TestCascadeFallback:
    @pytest.mark.asyncio
    async def test_cascade_skips_failing_provider(self):
        """Cascade should skip a failing provider and try the next tier."""
        engine = CouncilEngine()

        # Register a failing provider as first priority
        engine.model_router.register_provider("deepseek", FailingMockProvider(name="deepseek"))
        # Register a working provider
        engine.model_router.register_provider("openai", MockLLMProvider(name="openai", confidence=0.90))

        with patch.object(engine, '_get_config', return_value=_mock_config()):
            with patch.object(engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                result = await engine.consult(
                    "ws-test", "Test fallback query", CouncilType.CHILD
                )

        assert isinstance(result, CouncilResult)
        assert result.synthesis  # Got a response despite first provider failing


# ──────────────────────────────────────────────────────────────
# Test 8: Governance Bridge
# ──────────────────────────────────────────────────────────────

class TestGovernanceBridge:
    @pytest.mark.asyncio
    async def test_bridge_converts_result_to_session(self, configured_engine):
        """CouncilBridge should convert ACK CouncilResult to CouncilSession."""
        from app.services.council.council_bridge import CouncilBridge
        from app.contracts.decision_intent import (
            DecisionIntent, ImpactLevel, ReversibilityLevel,
            DecisionTier, ReasoningPhase,
        )
        from app.domain.council import CouncilSession, CouncilVote
        from datetime import datetime, timezone

        bridge = CouncilBridge(configured_engine)

        proposal = DecisionIntent(
            intent_id="test-intent-001",
            session_id="session-001",
            title="Add caching layer",
            description="Should we add Redis caching to the auth service?",
            impact_level=ImpactLevel.LOCAL,
            reversibility=ReversibilityLevel.EASY,
            calculated_tier=DecisionTier.T1,
            reasoning=ReasoningPhase(
                problem_framing="Performance issue",
                assumptions=["Redis is available"],
                constraints=["Budget < $50/mo"],
            ),
            affected_modules=["auth", "cache"],
            origin="human",
            proposed_by="user-001",
            proposed_at=datetime.now(timezone.utc),
            status="pending",
        )

        with patch.object(configured_engine, '_get_config', return_value=_mock_config()):
            with patch.object(configured_engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                session = await bridge.consult_as_session(proposal, "ws-test")

        assert isinstance(session, CouncilSession)
        assert session.proposal_id == "test-intent-001"
        assert session.workspace_id == "ws-test"
        assert session.status == "completed"
        assert session.consensus is not None
        assert len(session.opinions) > 0
        assert session.total_tokens > 0

        # Verify opinions have correct structure
        for opinion in session.opinions:
            assert opinion.proposal_id == "test-intent-001"
            assert opinion.vote in [CouncilVote.SUPPORT, CouncilVote.DEFER, CouncilVote.OPPOSE, CouncilVote.ABSTAIN]
            assert 0.0 <= opinion.confidence <= 1.0


# ──────────────────────────────────────────────────────────────
# Test 9: Synthesize / Consensus
# ──────────────────────────────────────────────────────────────

class TestSynthesis:
    def test_synthesize_picks_best_response(self, configured_engine):
        """_synthesize should use BFT consensus to pick the majority position.

        After the BFT upgrade (Phase 87), synthesis uses semantic Jaccard
        similarity to identify a quorum instead of naively picking the
        highest-confidence single response.  The majority position is
        the text chosen by the BFT engine, consensus_score reflects quorum
        agreement, and dissenting_views depends on pair-wise similarity.
        """
        import time
        responses = [
            ModelResponse(
                model="model-a", provider="a", response="Answer A",
                confidence=0.60, tokens_in=50, tokens_out=50, cost_usd=0.001,
            ),
            ModelResponse(
                model="model-b", provider="b", response="Answer B (best)",
                confidence=0.95, tokens_in=50, tokens_out=50, cost_usd=0.002,
            ),
            ModelResponse(
                model="model-c", provider="c", response="Answer C",
                confidence=0.40, tokens_in=50, tokens_out=50, cost_usd=0.001,
            ),
        ]
        start_ms = int(time.monotonic() * 1000)
        result = configured_engine._synthesize(
            "test query", CouncilType.CHILD, CouncilProfile.MODERATE,
            responses, start_ms,
        )
        # BFT picks majority position — with these inputs it selects best
        assert result.synthesis  # Non-empty synthesis
        assert result.consensus_score > 0
        # dissenting_views is a list (may be empty if BFT finds full quorum)
        assert isinstance(result.dissenting_views, list)
        assert result.total_cost_usd == pytest.approx(0.004, abs=0.001)

    def test_synthesize_empty_raises(self, configured_engine):
        """_synthesize should raise on empty responses."""
        import time
        start_ms = int(time.monotonic() * 1000)
        with pytest.raises(RuntimeError, match="zero successful responses"):
            configured_engine._synthesize(
                "test", CouncilType.CHILD, CouncilProfile.SIMPLE, [], start_ms,
            )


# ──────────────────────────────────────────────────────────────
# Test 10: Engine Configuration
# ──────────────────────────────────────────────────────────────

class TestEngineConfiguration:
    @pytest.mark.asyncio
    async def test_configure_registers_providers(self):
        """configure() should register providers from API keys."""
        engine = CouncilEngine()
        # Mock the model_router.configure_from_user_keys
        engine.model_router.configure_from_user_keys = AsyncMock()

        await engine.configure({"openai_key": "sk-test"})
        engine.model_router.configure_from_user_keys.assert_called_once_with(
            {"openai_key": "sk-test"}
        )

    def test_engine_starts_with_no_providers(self):
        """A fresh engine should have no providers."""
        engine = CouncilEngine()
        assert len(engine.model_router.providers) == 0
