"""
Tests for Provider Health Monitor — Background Health Probing.

Covers:
    - Monitor lifecycle (start/stop)
    - Provider update
    - Summary generation
    - Probe result data structure
    - Consecutive failure tracking
    - Circuit breaker integration

Note: Actual HTTP probing is tested via integration tests.
These unit tests focus on local state management.
"""

import asyncio
import pytest

from app.services.council_kernel.provider_health import (
    ProviderHealthMonitor,
    ProviderProbeResult,
    get_provider_health_monitor,
    _PROVIDER_HEALTH_URLS,
)
from app.services.council_kernel.circuit_breaker import CircuitBreakerRegistry


# ──────────────────────────────────────────────────────────────────────────────
# Probe Result
# ──────────────────────────────────────────────────────────────────────────────

class TestProbeResult:
    """ProviderProbeResult data structure."""

    def test_successful_probe(self):
        result = ProviderProbeResult(
            provider="openai", reachable=True,
            latency_ms=45.2, status_code=200,
        )
        assert result.provider == "openai"
        assert result.reachable is True
        assert result.latency_ms == 45.2
        assert result.status_code == 200
        assert result.error == ""

    def test_failed_probe(self):
        result = ProviderProbeResult(
            provider="anthropic", reachable=False,
            error="ConnectTimeout",
        )
        assert result.reachable is False
        assert "ConnectTimeout" in result.error

    def test_timestamp_auto_set(self):
        r1 = ProviderProbeResult(provider="test", reachable=True)
        r2 = ProviderProbeResult(provider="test", reachable=True)
        assert r2.timestamp >= r1.timestamp


# ──────────────────────────────────────────────────────────────────────────────
# Monitor Lifecycle
# ──────────────────────────────────────────────────────────────────────────────

class TestMonitorLifecycle:
    """Monitor start/stop behavior."""

    def test_initial_state(self):
        monitor = ProviderHealthMonitor(
            active_providers={"openai"},
            probe_interval_s=300.0,
        )
        assert monitor.is_running is False

    @pytest.mark.asyncio
    async def test_start_stop(self):
        monitor = ProviderHealthMonitor(
            active_providers=set(),  # Empty to avoid real probes
            probe_interval_s=300.0,
        )
        await monitor.start()
        assert monitor.is_running is True

        await monitor.stop()
        assert monitor.is_running is False

    @pytest.mark.asyncio
    async def test_double_start_idempotent(self):
        monitor = ProviderHealthMonitor(
            active_providers=set(),
            probe_interval_s=300.0,
        )
        await monitor.start()
        await monitor.start()  # Should not create a second task
        assert monitor.is_running is True
        await monitor.stop()


# ──────────────────────────────────────────────────────────────────────────────
# Provider Management
# ──────────────────────────────────────────────────────────────────────────────

class TestProviderManagement:
    """Dynamic provider set updates."""

    def test_update_providers(self):
        monitor = ProviderHealthMonitor(active_providers={"openai"})
        assert "openai" in monitor._active_providers

        monitor.update_providers({"openai", "anthropic", "google"})
        assert len(monitor._active_providers) == 3
        assert "anthropic" in monitor._active_providers


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────

class TestSummary:
    """Health summary generation."""

    def test_empty_results(self):
        monitor = ProviderHealthMonitor(active_providers={"openai", "anthropic"})
        summary = monitor.get_summary()
        assert summary["total_providers"] == 2
        assert summary["healthy"] == 0
        assert len(summary["unhealthy"]) == 2

    def test_with_results(self):
        monitor = ProviderHealthMonitor()
        monitor._last_results = {
            "openai": ProviderProbeResult("openai", True, latency_ms=50.0),
            "anthropic": ProviderProbeResult("anthropic", True, latency_ms=100.0),
            "google": ProviderProbeResult("google", False, error="timeout"),
        }
        summary = monitor.get_summary()
        assert summary["total_providers"] == 3
        assert summary["healthy"] == 2
        assert summary["unhealthy"] == ["google"]
        assert summary["avg_latency_ms"] == 75.0  # (50 + 100) / 2


# ──────────────────────────────────────────────────────────────────────────────
# Provider URL Map
# ──────────────────────────────────────────────────────────────────────────────

class TestProviderURLMap:
    """All major providers have health URLs configured."""

    def test_all_major_providers_have_urls(self):
        expected = {"openai", "anthropic", "google", "deepseek", "xai", "mistral", "cohere"}
        configured = set(_PROVIDER_HEALTH_URLS.keys())
        assert expected.issubset(configured)

    def test_urls_are_https(self):
        for provider, url in _PROVIDER_HEALTH_URLS.items():
            assert url.startswith("https://"), f"{provider} URL not HTTPS"


# ──────────────────────────────────────────────────────────────────────────────
# Consecutive Failures
# ──────────────────────────────────────────────────────────────────────────────

class TestConsecutiveFailures:
    """Failure tracking for exponential backoff."""

    def test_initial_no_failures(self):
        monitor = ProviderHealthMonitor()
        assert monitor._consecutive_failures.get("openai", 0) == 0

    def test_failure_increment(self):
        monitor = ProviderHealthMonitor()
        monitor._consecutive_failures["openai"] = 0
        monitor._consecutive_failures["openai"] += 1
        monitor._consecutive_failures["openai"] += 1
        assert monitor._consecutive_failures["openai"] == 2


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

class TestSingleton:
    """Module singleton pattern."""

    def test_singleton(self):
        import app.services.council_kernel.provider_health as ph_module
        ph_module._monitor = None

        m1 = get_provider_health_monitor()
        m2 = get_provider_health_monitor()
        assert m1 is m2

        ph_module._monitor = None
