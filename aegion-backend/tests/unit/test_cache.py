"""
Tests for Semantic Cache — Statistics, Health, and LRU Eviction Logic.

Covers:
    - Health reporting
    - Stats and effectiveness tracking
    - Degraded mode behavior
    - Reset functionality
    - Cache configuration

Note: DB-dependent methods (check, store, invalidate, evict) are tested
via integration tests. These unit tests focus on the local state logic.
"""

import pytest

from app.services.council_kernel.cache import SemanticCache, get_semantic_cache


# ──────────────────────────────────────────────────────────────────────────────
# Health & Stats
# ──────────────────────────────────────────────────────────────────────────────

class TestCacheHealth:
    """Cache health reporting."""

    def test_initial_health(self):
        """Fresh cache should report degraded (no sentence-transformers in test env)."""
        cache = SemanticCache()
        health = cache.health()
        assert "status" in health
        assert "hit_count" in health
        assert "miss_count" in health
        assert "error_count" in health
        assert "eviction_count" in health
        assert "max_entries" in health
        assert health["hit_count"] == 0
        assert health["miss_count"] == 0

    def test_health_hit_rate(self):
        """Hit rate computation."""
        cache = SemanticCache()
        cache._hit_count = 7
        cache._miss_count = 3
        health = cache.health()
        assert health["hit_rate"] == 0.7  # 7 / 10

    def test_health_zero_queries(self):
        """No queries should return 0 hit rate (not divide by zero)."""
        cache = SemanticCache()
        health = cache.health()
        assert health["hit_rate"] == 0.0


class TestCacheStats:
    """Extended cache statistics."""

    def test_stats_includes_health(self):
        """Stats should be a superset of health."""
        cache = SemanticCache()
        stats = cache.stats()
        health = cache.health()
        for key in health:
            assert key in stats

    def test_stats_total_queries(self):
        """total_queries = hits + misses."""
        cache = SemanticCache()
        cache._hit_count = 5
        cache._miss_count = 15
        stats = cache.stats()
        assert stats["total_queries"] == 20

    def test_stats_effectiveness_high_hit_rate(self):
        """High hit rate with no errors → high effectiveness."""
        cache = SemanticCache()
        cache._hit_count = 90
        cache._miss_count = 10
        stats = cache.stats()
        assert stats["effectiveness"] >= 0.8

    def test_stats_effectiveness_penalized_by_errors(self):
        """Errors should reduce effectiveness."""
        cache = SemanticCache()
        cache._hit_count = 50
        cache._miss_count = 50
        cache._error_count = 20
        stats = cache.stats()
        # effectiveness = 0.5 (hit_rate) - 0.2 * 0.5 (error_rate penalty) = 0.4
        assert stats["effectiveness"] == 0.4

    def test_stats_effectiveness_never_negative(self):
        """Effectiveness should never go below 0."""
        cache = SemanticCache()
        cache._hit_count = 0
        cache._miss_count = 10
        cache._error_count = 100
        stats = cache.stats()
        assert stats["effectiveness"] >= 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Reset
# ──────────────────────────────────────────────────────────────────────────────

class TestCacheReset:
    """Stats reset functionality."""

    def test_reset_clears_all(self):
        """reset_stats should zero all counters."""
        cache = SemanticCache()
        cache._hit_count = 100
        cache._miss_count = 50
        cache._error_count = 10
        cache._eviction_count = 5

        cache.reset_stats()

        assert cache._hit_count == 0
        assert cache._miss_count == 0
        assert cache._error_count == 0
        assert cache._eviction_count == 0


# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

class TestCacheConfig:
    """Cache configuration."""

    def test_default_max_entries(self):
        """Default max entries should be 10000."""
        cache = SemanticCache()
        assert cache._max_entries == 10_000

    def test_custom_max_entries(self):
        """Max entries should be configurable."""
        cache = SemanticCache(max_entries=500)
        assert cache._max_entries == 500

    def test_singleton(self):
        """get_semantic_cache should return the same instance."""
        # Reset the singleton for testing
        import app.services.council_kernel.cache as cache_module
        cache_module._semantic_cache = None

        c1 = get_semantic_cache()
        c2 = get_semantic_cache()
        assert c1 is c2

        # Clean up
        cache_module._semantic_cache = None


# ──────────────────────────────────────────────────────────────────────────────
# Degraded Mode
# ──────────────────────────────────────────────────────────────────────────────

class TestDegradedMode:
    """Cache behavior when sentence-transformers is not available."""

    def test_degraded_after_warmup(self):
        """Cache should degrade gracefully without sentence-transformers."""
        cache = SemanticCache()
        cache.warmup()
        # In test environment, sentence-transformers may not be installed
        # Either way, health should be valid
        health = cache.health()
        assert health["status"] in ("ok", "degraded")

    def test_is_available_reflects_state(self):
        """is_available should return False when degraded."""
        cache = SemanticCache()
        cache._degraded = True
        assert cache.is_available() is False

    def test_is_available_when_ok(self):
        """is_available should return True when not degraded (with embedder)."""
        cache = SemanticCache()
        cache._degraded = False
        cache._embedder = "mock"  # Pretend we have an embedder
        assert cache.is_available() is True
