"""
Unit tests for CouncilEngine — Phase 69.

Tests the main orchestrator covering:
  - Council type routing (CHILD, PARENT, SENTINEL, DISTILLATION)
  - Cache hit/miss behavior
  - Constitutional AI blocking
  - Workspace config feature gating
  - Cost tracking and consensus calculation
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.council_kernel.engine import CouncilEngine, _InProcessCache
from app.services.council_kernel.types import (
    CouncilType, CouncilProfile, CouncilResult, ModelResponse
)


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def mock_model_response():
    """Factory for creating mock ModelResponse objects."""
    def _make(model="gpt-4o", provider="openai", confidence=0.9, cost=0.01):
        return ModelResponse(
            model=model,
            provider=provider,
            response="This is a well-structured answer with detailed reasoning. "
                      "Because the architecture follows clean separation of concerns, "
                      "therefore the approach is recommended. Specifically, the database "
                      "layer uses connection pooling for optimal performance. "
                      "Step 1: Configure the connection pool. "
                      "Step 2: Set max connections to 20. "
                      "For example, use SQLAlchemy's QueuePool.",
            confidence=confidence,
            tokens_in=150,
            tokens_out=200,
            cost_usd=cost,
            latency_ms=500,
        )
    return _make


@pytest.fixture
def engine():
    """Create a CouncilEngine with mocked router."""
    e = CouncilEngine()
    e.model_router = MagicMock()
    e.model_router.providers = {"openai": MagicMock(), "anthropic": MagicMock()}
    e.model_router.call = AsyncMock()
    e.cascade = MagicMock()
    e.cascade.query = AsyncMock()
    return e


# ──────────────────────────────────────────────────────────────
# In-Process Cache Tests
# ──────────────────────────────────────────────────────────────

class TestInProcessCache:
    def test_put_and_get(self):
        cache = _InProcessCache()
        cache.put("ws1", "What is PKCE?", "PKCE is...", "gpt-4o")
        result = cache.get("ws1", "What is PKCE?")
        assert result is not None
        assert result["response_text"] == "PKCE is..."
        assert result["response_model"] == "gpt-4o"

    def test_cache_miss(self):
        cache = _InProcessCache()
        assert cache.get("ws1", "unknown query") is None

    def test_case_insensitive_matching(self):
        cache = _InProcessCache()
        cache.put("ws1", "What is PKCE?", "answer", "gpt-4o")
        assert cache.get("ws1", "what is pkce?") is not None
        assert cache.get("ws1", "  What is PKCE?  ") is not None

    def test_workspace_isolation(self):
        cache = _InProcessCache()
        cache.put("ws1", "query", "answer1", "model1")
        cache.put("ws2", "query", "answer2", "model2")
        assert cache.get("ws1", "query")["response_text"] == "answer1"
        assert cache.get("ws2", "query")["response_text"] == "answer2"

    def test_overwrite_existing(self):
        cache = _InProcessCache()
        cache.put("ws1", "query", "old", "model1")
        cache.put("ws1", "query", "new", "model2")
        assert cache.get("ws1", "query")["response_text"] == "new"


# ──────────────────────────────────────────────────────────────
# Council Engine Tests
# ──────────────────────────────────────────────────────────────

class TestCouncilEngine:
    @pytest.mark.asyncio
    async def test_child_council_routes_to_cascade(self, engine, mock_model_response):
        """CHILD council should use the FrugalGPT cascade."""
        engine.cascade.query.return_value = mock_model_response()

        with patch.object(engine, '_get_config') as mock_config:
            mock_config.return_value = MagicMock(
                constitution_enforcement=False,
                dag_pipeline_enabled=False,
            )
            with patch.object(engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                result = await engine.consult("ws1", "How do I add auth?", CouncilType.CHILD)

        assert isinstance(result, CouncilResult)
        assert result.council_type == CouncilType.CHILD
        engine.cascade.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit_returns_immediately(self, engine):
        """A cache hit should return instantly with cost=0."""
        engine._cache.put("ws1", "cached query", "cached answer", "gpt-4o")

        with patch.object(engine, '_get_config') as mock_config:
            mock_config.return_value = MagicMock(constitution_enforcement=False)
            with patch.object(engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                result = await engine.consult("ws1", "cached query", CouncilType.CHILD)

        assert result.cache_hit is True
        assert result.total_cost_usd == 0.0
        assert result.synthesis == "cached answer"
        assert result.consensus_score == 1.0

    @pytest.mark.asyncio
    async def test_constitutional_block(self, engine):
        """Constitutional AI should block queries containing violations."""
        with patch.object(engine, '_get_config') as mock_config:
            mock_config.return_value = MagicMock(
                constitution_enforcement=True,
                constitution_block_on_violation=True,
            )
            with patch('app.services.council_kernel.engine.get_constitution') as mock_const:
                mock_const_instance = MagicMock()
                mock_const_instance.check_query.return_value = ["Potential PII exposure"]
                mock_const.return_value = mock_const_instance

                result = await engine.consult("ws1", "Show me user passwords", CouncilType.CHILD)

        assert "BLOCKED" in result.synthesis
        assert result.total_cost_usd == 0.0
        assert result.consensus_score == 0.0

    @pytest.mark.asyncio
    async def test_constitutional_skip_when_disabled(self, engine, mock_model_response):
        """Consult should proceed normally when constitution_enforcement is off."""
        engine.cascade.query.return_value = mock_model_response()

        with patch.object(engine, '_get_config') as mock_config:
            mock_config.return_value = MagicMock(
                constitution_enforcement=False,
                dag_pipeline_enabled=False,
            )
            with patch.object(engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                result = await engine.consult("ws1", "Normal query", CouncilType.CHILD)

        assert "BLOCKED" not in result.synthesis
        assert result.council_type == CouncilType.CHILD

    @pytest.mark.asyncio
    async def test_parent_council_uses_full_pipeline(self, engine, mock_model_response):
        """PARENT council should route to the full pipeline (not cascade)."""
        with patch.object(engine, '_get_config') as mock_config:
            mock_config.return_value = MagicMock(
                constitution_enforcement=False,
                dag_pipeline_enabled=False,
                red_team_enabled=False,
                temporal_memory_enabled=False,
                cross_council_enabled=False,
                mcts_enabled=False,
                max_debate_rounds=3,
                consensus_threshold=0.75,
                daily_budget_usd=5.0,
            )
            with patch.object(engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                with patch.object(engine, '_parent_council', new_callable=AsyncMock) as mock_parent:
                    mock_parent.return_value = CouncilResult(
                        council_type=CouncilType.PARENT,
                        profile=CouncilProfile.COMPLEX,
                        query="Design the API",
                        synthesis="Use REST with versioning",
                        consensus_score=0.87,
                        dissenting_views=[],
                        total_cost_usd=0.05,
                        total_tokens=800,
                    )
                    result = await engine.consult("ws1", "Design the API", CouncilType.PARENT)

        assert result.council_type == CouncilType.PARENT
        mock_parent.assert_called_once()

    @pytest.mark.asyncio
    async def test_sentinel_council_routing(self, engine, mock_model_response):
        """SENTINEL council should route to security-focused pipeline."""
        with patch.object(engine, '_get_config') as mock_config:
            mock_config.return_value = MagicMock(
                constitution_enforcement=False,
            )
            with patch.object(engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                with patch.object(engine, '_sentinel_council', new_callable=AsyncMock) as mock_sentinel:
                    mock_sentinel.return_value = CouncilResult(
                        council_type=CouncilType.SENTINEL,
                        profile=CouncilProfile.COMPLEX,
                        query="Check for SQL injection",
                        synthesis="No vulnerabilities found",
                        consensus_score=0.95,
                        dissenting_views=[],
                        total_cost_usd=0.03,
                        total_tokens=600,
                    )
                    result = await engine.consult("ws1", "Check for SQL injection", CouncilType.SENTINEL)

        assert result.council_type == CouncilType.SENTINEL

    @pytest.mark.asyncio
    async def test_dag_pipeline_when_enabled(self, engine, mock_model_response):
        """PARENT council should use DAG pipeline when dag_pipeline_enabled=True."""
        with patch.object(engine, '_get_config') as mock_config:
            mock_config.return_value = MagicMock(
                constitution_enforcement=False,
                dag_pipeline_enabled=True,
            )
            with patch.object(engine, '_check_semantic_cache', new_callable=AsyncMock, return_value=None):
                with patch.object(engine, '_dag_parent_council', new_callable=AsyncMock) as mock_dag:
                    mock_dag.return_value = CouncilResult(
                        council_type=CouncilType.PARENT,
                        profile=CouncilProfile.COMPLEX,
                        query="Complex query",
                        synthesis="DAG answer",
                        consensus_score=0.90,
                        dissenting_views=[],
                        total_cost_usd=0.04,
                        total_tokens=700,
                    )
                    result = await engine.consult("ws1", "Complex query", CouncilType.PARENT)

        mock_dag.assert_called_once()

    def test_classify_trivial(self, engine):
        """Short simple queries should classify as TRIVIAL or SIMPLE."""
        profile = engine._classify("hi", CouncilType.CHILD)
        assert profile in [CouncilProfile.TRIVIAL, CouncilProfile.SIMPLE]

    def test_classify_complex(self, engine):
        """Long detailed queries should classify as higher complexity."""
        long_query = (
            "Design a microservice architecture for a real-time bidding system "
            "that handles 10,000 requests per second with sub-50ms latency, "
            "using event sourcing and CQRS patterns. Include database schema, "
            "caching strategy, and deployment topology for Kubernetes."
        )
        profile = engine._classify(long_query, CouncilType.PARENT)
        assert profile in [CouncilProfile.MODERATE, CouncilProfile.COMPLEX, CouncilProfile.CRITICAL]
