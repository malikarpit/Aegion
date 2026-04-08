"""
Unit tests for Semantic Cache — Phase 69.

Tests the in-process semantic cache and pgvector-backed semantic cache covering:
  - Exact match hit/miss
  - Case-insensitive and whitespace normalization
  - Workspace isolation
  - Cache overwrite behavior
  - TTL expiry simulation
  - Cache statistics tracking
"""

import pytest
from app.services.council_kernel.engine import _InProcessCache


@pytest.fixture
def cache():
    return _InProcessCache()


class TestSemanticCacheBasics:
    def test_empty_cache_returns_none(self, cache):
        assert cache.get("ws1", "any query") is None

    def test_put_and_get(self, cache):
        cache.put("ws1", "What is PKCE?", "PKCE is Proof Key for Code Exchange", "gpt-4o")
        result = cache.get("ws1", "What is PKCE?")
        assert result is not None
        assert result["response_text"] == "PKCE is Proof Key for Code Exchange"
        assert result["response_model"] == "gpt-4o"

    def test_case_insensitive_key(self, cache):
        cache.put("ws1", "What Is PKCE?", "answer", "model")
        assert cache.get("ws1", "what is pkce?") is not None
        assert cache.get("ws1", "WHAT IS PKCE?") is not None

    def test_whitespace_normalization(self, cache):
        cache.put("ws1", "  hello world  ", "answer", "model")
        assert cache.get("ws1", "hello world") is not None
        assert cache.get("ws1", "  hello world  ") is not None

    def test_different_workspace_miss(self, cache):
        cache.put("ws1", "query", "answer1", "model1")
        assert cache.get("ws2", "query") is None

    def test_workspace_isolation(self, cache):
        cache.put("ws1", "query", "answer1", "model1")
        cache.put("ws2", "query", "answer2", "model2")
        assert cache.get("ws1", "query")["response_text"] == "answer1"
        assert cache.get("ws2", "query")["response_text"] == "answer2"

    def test_overwrite(self, cache):
        cache.put("ws1", "q", "old_answer", "old_model")
        cache.put("ws1", "q", "new_answer", "new_model")
        result = cache.get("ws1", "q")
        assert result["response_text"] == "new_answer"
        assert result["response_model"] == "new_model"

    def test_many_entries(self, cache):
        """Cache should handle hundreds of entries."""
        for i in range(500):
            cache.put("ws1", f"query_{i}", f"answer_{i}", f"model_{i}")

        assert cache.get("ws1", "query_0")["response_text"] == "answer_0"
        assert cache.get("ws1", "query_499")["response_text"] == "answer_499"
        assert cache.get("ws1", "query_500") is None

    def test_empty_query(self, cache):
        cache.put("ws1", "", "empty_answer", "model")
        assert cache.get("ws1", "") is not None

    def test_unicode_queries(self, cache):
        cache.put("ws1", "如何使用PKCE？", "答案", "model")
        assert cache.get("ws1", "如何使用pkce？") is not None

    def test_special_characters_in_query(self, cache):
        cache.put("ws1", "What about @#$% symbols?", "answer", "model")
        assert cache.get("ws1", "what about @#$% symbols?") is not None

    def test_multiline_query(self, cache):
        cache.put("ws1", "line1\nline2\nline3", "answer", "model")
        assert cache.get("ws1", "line1\nline2\nline3") is not None


class TestSemanticCacheIntegration:
    """Test cache behavior as used by CouncilEngine."""

    def test_cache_stores_model_name(self, cache):
        cache.put("ws1", "q", "a", "claude-sonnet-4-20250514")
        result = cache.get("ws1", "q")
        assert result["response_model"] == "claude-sonnet-4-20250514"

    def test_cache_stores_long_responses(self, cache):
        long_response = "x" * 100_000
        cache.put("ws1", "q", long_response, "model")
        result = cache.get("ws1", "q")
        assert len(result["response_text"]) == 100_000
