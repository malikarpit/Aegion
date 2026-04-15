"""
Tests for Circuit Breaker — Per-Provider Resilience State Machine.

Covers:
    - State transitions: CLOSED → OPEN → HALF_OPEN → CLOSED
    - Sliding window failure tracking
    - Exponential backoff on recovery timeout
    - Error classification (transient vs auth vs validation)
    - Concurrent access safety
    - Registry: per-provider isolation
    - Health reporting

Reference: Implementation plan Section 1.1.7
"""

import asyncio
import time
from unittest.mock import patch

import pytest

from app.services.council_kernel.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    ErrorCategory,
    ProviderHealth,
    _BreakerState,
    classify_error,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fast_config() -> CircuitBreakerConfig:
    """Config with fast timeouts for testing."""
    return CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout_s=0.1,  # 100ms for fast tests
        half_open_max_calls=1,
        success_threshold=2,
        request_timeout_s=5.0,
        sliding_window_s=10.0,
        backoff_multiplier=2.0,
        max_recovery_timeout_s=1.0,
        jitter_range=0.0,  # No jitter for deterministic tests
    )


@pytest.fixture
def breaker(fast_config) -> _BreakerState:
    """A fresh breaker instance with fast config."""
    return _BreakerState("test_provider", fast_config)


@pytest.fixture
def registry(fast_config) -> CircuitBreakerRegistry:
    """A fresh registry with fast config."""
    return CircuitBreakerRegistry(default_config=fast_config)


# ──────────────────────────────────────────────────────────────────────────────
# State Machine Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestCircuitBreakerStateMachine:
    """Core state machine transitions."""

    @pytest.mark.asyncio
    async def test_starts_closed(self, breaker):
        """New breaker starts in CLOSED state."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.get_health() == ProviderHealth.HEALTHY
        can = await breaker.can_execute()
        assert can is True

    @pytest.mark.asyncio
    async def test_opens_after_failure_threshold(self, breaker):
        """CLOSED → OPEN after N consecutive failures."""
        for i in range(3):
            await breaker.record_failure(f"error_{i}")

        assert breaker.state == CircuitState.OPEN
        assert breaker.get_health() == ProviderHealth.UNAVAILABLE
        can = await breaker.can_execute()
        assert can is False

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_recovery_timeout(self, breaker):
        """OPEN → HALF_OPEN after recovery_timeout_s."""
        # Trip the breaker
        for i in range(3):
            await breaker.record_failure(f"error_{i}")
        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next can_execute should transition to HALF_OPEN
        can = await breaker.can_execute()
        assert can is True
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.get_health() == ProviderHealth.DEGRADED

    @pytest.mark.asyncio
    async def test_closes_after_successful_probes(self, breaker):
        """HALF_OPEN → CLOSED after success_threshold successes."""
        # Trip the breaker
        for i in range(3):
            await breaker.record_failure(f"error_{i}")

        # Wait for recovery, enter HALF_OPEN
        await asyncio.sleep(0.15)
        await breaker.can_execute()
        assert breaker.state == CircuitState.HALF_OPEN

        # Record successful probes
        await breaker.record_success()
        assert breaker.state == CircuitState.HALF_OPEN  # Need 2 successes

        await breaker.record_success()
        assert breaker.state == CircuitState.CLOSED  # Now closed
        assert breaker.get_health() == ProviderHealth.HEALTHY

    @pytest.mark.asyncio
    async def test_reopens_on_probe_failure(self, breaker):
        """HALF_OPEN → OPEN if probe fails."""
        # Trip the breaker
        for i in range(3):
            await breaker.record_failure(f"error_{i}")

        # Wait for recovery, enter HALF_OPEN
        await asyncio.sleep(0.15)
        await breaker.can_execute()
        assert breaker.state == CircuitState.HALF_OPEN

        # Probe fails
        await breaker.record_failure("probe_failed")
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_resets_failures_on_success_in_closed(self, breaker):
        """Success in CLOSED state prunes old failures."""
        # Add 2 failures (below threshold of 3)
        await breaker.record_failure("error_1")
        await breaker.record_failure("error_2")
        assert breaker.active_failure_count == 2

        # Success prunes old failures
        await breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_limits_concurrent_calls(self):
        """HALF_OPEN only allows half_open_max_calls probe requests after transition."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout_s=0.05,
            half_open_max_calls=1,  # Allow 1 probe call within HALF_OPEN
            success_threshold=2,
            sliding_window_s=10.0,
            jitter_range=0.0,
        )
        breaker = _BreakerState("test_limit", config)

        # Trip the breaker
        for i in range(3):
            await breaker.record_failure(f"error_{i}")

        # Wait for recovery
        await asyncio.sleep(0.1)

        # First call transitions OPEN → HALF_OPEN (doesn't count as probe)
        assert await breaker.can_execute() is True
        assert breaker.state == CircuitState.HALF_OPEN

        # Second call is the first HALF_OPEN probe (allowed, half_open_calls=1)
        assert await breaker.can_execute() is True

        # Third call exceeds half_open_max_calls=1
        assert await breaker.can_execute() is False


# ──────────────────────────────────────────────────────────────────────────────
# Sliding Window Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSlidingWindow:
    """Failure counting uses a sliding time window."""

    @pytest.mark.asyncio
    async def test_old_failures_expire(self):
        """Failures outside the sliding window don't count."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            sliding_window_s=0.1,  # 100ms window
            jitter_range=0.0,
        )
        breaker = _BreakerState("test", config)

        # Add 2 failures
        await breaker.record_failure("old_error_1")
        await breaker.record_failure("old_error_2")

        # Wait for failures to expire
        await asyncio.sleep(0.15)

        # These shouldn't be counted anymore
        assert breaker.active_failure_count == 0

        # Need 3 new failures to trip
        await breaker.record_failure("new_error_1")
        assert breaker.state == CircuitState.CLOSED

        await breaker.record_failure("new_error_2")
        assert breaker.state == CircuitState.CLOSED

        await breaker.record_failure("new_error_3")
        assert breaker.state == CircuitState.OPEN


# ──────────────────────────────────────────────────────────────────────────────
# Exponential Backoff Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestExponentialBackoff:
    """Recovery timeout increases on consecutive OPENs."""

    @pytest.mark.asyncio
    async def test_backoff_increases_on_consecutive_opens(self):
        """Each consecutive OPEN without full recovery increases backoff."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout_s=0.1,
            success_threshold=1,
            half_open_max_calls=1,
            backoff_multiplier=2.0,
            max_recovery_timeout_s=10.0,
            sliding_window_s=60.0,
            jitter_range=0.0,
        )
        breaker = _BreakerState("test", config)

        # First trip: consecutive_opens = 1
        await breaker.record_failure("e1")
        await breaker.record_failure("e2")
        assert breaker.consecutive_opens == 1
        assert breaker.state == CircuitState.OPEN

        # Recover, enter HALF_OPEN, but probe FAILS → back to OPEN
        await asyncio.sleep(0.15)
        await breaker.can_execute()  # HALF_OPEN
        assert breaker.state == CircuitState.HALF_OPEN
        await breaker.record_failure("probe_fail")  # Back to OPEN
        assert breaker.state == CircuitState.OPEN
        assert breaker.consecutive_opens == 2

        # Second recovery should take longer (0.1 * 2^1 = 0.2s)
        timeout = breaker._get_recovery_timeout()
        assert timeout == pytest.approx(0.2, abs=0.01)

    @pytest.mark.asyncio
    async def test_backoff_resets_on_close(self):
        """consecutive_opens resets to 0 when circuit closes successfully."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout_s=0.05,
            success_threshold=1,
            backoff_multiplier=2.0,
            jitter_range=0.0,
        )
        breaker = _BreakerState("test", config)

        # Trip
        await breaker.record_failure("e1")
        await breaker.record_failure("e2")
        assert breaker.consecutive_opens == 1

        # Recover fully
        await asyncio.sleep(0.1)
        await breaker.can_execute()
        await breaker.record_success()
        assert breaker.consecutive_opens == 0


# ──────────────────────────────────────────────────────────────────────────────
# Error Classification Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestErrorClassification:
    """Error classification determines if breaker should trip."""

    def test_timeout_is_transient(self):
        assert classify_error(asyncio.TimeoutError()) == ErrorCategory.TRANSIENT

    def test_server_error_is_transient(self):
        assert classify_error(Exception("HTTP 503 Service Unavailable")) == ErrorCategory.TRANSIENT

    def test_rate_limit_is_transient(self):
        assert classify_error(Exception("429 Too Many Requests")) == ErrorCategory.TRANSIENT

    def test_connection_refused_is_transient(self):
        assert classify_error(ConnectionRefusedError("Connection refused")) == ErrorCategory.TRANSIENT

    def test_auth_error_is_auth(self):
        assert classify_error(Exception("401 Unauthorized")) == ErrorCategory.AUTH

    def test_forbidden_is_auth(self):
        assert classify_error(Exception("403 Forbidden")) == ErrorCategory.AUTH

    def test_invalid_api_key_is_auth(self):
        assert classify_error(Exception("Invalid API key provided")) == ErrorCategory.AUTH

    def test_bad_request_is_validation(self):
        assert classify_error(Exception("400 Bad Request")) == ErrorCategory.VALIDATION

    def test_unknown_error_is_unknown(self):
        assert classify_error(Exception("Something weird happened")) == ErrorCategory.UNKNOWN

    @pytest.mark.asyncio
    async def test_auth_error_does_not_trip_breaker(self, breaker):
        """Auth errors are tracked but don't trip the breaker."""
        for i in range(10):
            await breaker.record_failure(
                "401 Unauthorized", ErrorCategory.AUTH
            )
        # Still CLOSED because auth errors don't count
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_validation_error_does_not_trip_breaker(self, breaker):
        """Validation errors don't trip the breaker."""
        for i in range(10):
            await breaker.record_failure(
                "400 Bad Request", ErrorCategory.VALIDATION
            )
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_transient_errors_trip_breaker(self, breaker):
        """Transient errors DO trip the breaker."""
        for i in range(3):
            await breaker.record_failure(
                "503 Service Unavailable", ErrorCategory.TRANSIENT
            )
        assert breaker.state == CircuitState.OPEN


# ──────────────────────────────────────────────────────────────────────────────
# Concurrency Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestConcurrency:
    """Verify thread-safety under concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_failures_no_race(self, breaker):
        """100 concurrent record_failure calls don't cause race conditions."""
        tasks = [
            breaker.record_failure(f"concurrent_error_{i}")
            for i in range(100)
        ]
        await asyncio.gather(*tasks)

        # Breaker should be OPEN (threshold is 3)
        assert breaker.state == CircuitState.OPEN
        assert breaker.total_failures == 100

    @pytest.mark.asyncio
    async def test_concurrent_can_execute_on_open(self, breaker):
        """Multiple concurrent can_execute on OPEN breaker all return False."""
        # Trip
        for i in range(3):
            await breaker.record_failure(f"error_{i}")

        results = await asyncio.gather(*[breaker.can_execute() for _ in range(50)])
        assert all(r is False for r in results)


# ──────────────────────────────────────────────────────────────────────────────
# Registry Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestCircuitBreakerRegistry:
    """Per-provider isolation and registry operations."""

    @pytest.mark.asyncio
    async def test_per_provider_isolation(self, registry):
        """Each provider has independent state."""
        # Trip openai
        for i in range(3):
            await registry.record_failure("openai", f"error_{i}")

        # Check states
        assert registry.get_health("openai") == ProviderHealth.UNAVAILABLE
        assert registry.get_health("anthropic") == ProviderHealth.HEALTHY

        # openai blocked, anthropic open
        assert await registry.can_execute("openai") is False
        assert await registry.can_execute("anthropic") is True

    @pytest.mark.asyncio
    async def test_get_all_health(self, registry):
        """get_all_health returns status for all known providers."""
        await registry.can_execute("openai")
        await registry.can_execute("anthropic")
        await registry.can_execute("google")

        health = registry.get_all_health()
        assert len(health) == 3
        assert "openai" in health
        assert "anthropic" in health
        assert "google" in health

    @pytest.mark.asyncio
    async def test_get_healthy_providers(self, registry):
        """get_healthy_providers excludes OPEN providers."""
        await registry.can_execute("openai")
        await registry.can_execute("anthropic")

        # Trip openai
        for i in range(3):
            await registry.record_failure("openai", f"error_{i}")

        healthy = registry.get_healthy_providers()
        assert "anthropic" in healthy
        assert "openai" not in healthy

    @pytest.mark.asyncio
    async def test_get_unavailable_providers(self, registry):
        """get_unavailable_providers returns only OPEN providers."""
        await registry.can_execute("openai")
        await registry.can_execute("anthropic")

        for i in range(3):
            await registry.record_failure("openai", f"error_{i}")

        unavailable = registry.get_unavailable_providers()
        assert unavailable == ["openai"]

    @pytest.mark.asyncio
    async def test_reset_single(self, registry):
        """Reset a single provider's breaker."""
        for i in range(3):
            await registry.record_failure("openai", f"error_{i}")
        assert registry.get_health("openai") == ProviderHealth.UNAVAILABLE

        await registry.reset("openai")
        assert registry.get_health("openai") == ProviderHealth.HEALTHY

    @pytest.mark.asyncio
    async def test_reset_all(self, registry):
        """Reset all breakers."""
        for provider in ["openai", "anthropic", "google"]:
            for i in range(3):
                await registry.record_failure(provider, f"error_{i}")

        await registry.reset_all()
        for provider in ["openai", "anthropic", "google"]:
            assert registry.get_health(provider) == ProviderHealth.HEALTHY

    @pytest.mark.asyncio
    async def test_record_success(self, registry):
        """Record success for a provider."""
        await registry.can_execute("openai")
        await registry.record_success("openai")

        health = registry.get_all_health()
        assert health["openai"]["total_successes"] == 1


# ──────────────────────────────────────────────────────────────────────────────
# Status Snapshot Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestStatusSnapshot:
    """Health status reporting for dashboards."""

    @pytest.mark.asyncio
    async def test_status_snapshot_fields(self, breaker):
        """Status snapshot includes all expected fields."""
        await breaker.can_execute()
        await breaker.record_success()

        status = breaker.get_status()
        assert "provider_id" in status
        assert "state" in status
        assert "health" in status
        assert "active_failures" in status
        assert "total_requests" in status
        assert "total_failures" in status
        assert "total_successes" in status
        assert "time_in_state_s" in status
        assert "config" in status
        assert status["provider_id"] == "test_provider"
        assert status["state"] == "closed"
        assert status["health"] == "healthy"

    @pytest.mark.asyncio
    async def test_degraded_health_on_recent_failures(self, breaker):
        """CLOSED with recent failures reports DEGRADED."""
        await breaker.record_failure("transient_error")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.get_health() == ProviderHealth.DEGRADED


# ──────────────────────────────────────────────────────────────────────────────
# Reset Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestReset:
    """Manual reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_clears_everything(self, breaker):
        """Reset returns breaker to pristine CLOSED state."""
        for i in range(3):
            await breaker.record_failure(f"error_{i}")
        assert breaker.state == CircuitState.OPEN

        await breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.active_failure_count == 0
        assert breaker.consecutive_opens == 0
        assert breaker.success_count == 0
        assert breaker.half_open_calls == 0
