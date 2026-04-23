"""
Circuit Breaker — Per-Provider Resilience State Machine.

Implements the Circuit Breaker pattern from Michael Nygard's "Release It!" (2007, Ch. 5).
Each LLM provider (openai, anthropic, google, etc.) gets its own independent breaker.

State Machine:
    CLOSED ──(failures ≥ threshold)──→ OPEN
    OPEN   ──(recovery_timeout elapsed)──→ HALF_OPEN
    HALF_OPEN ──(success_count ≥ success_threshold)──→ CLOSED
    HALF_OPEN ──(any failure)──→ OPEN

Production considerations (from circuit breaker research):
    - Each breaker is async-lock protected (no race conditions under concurrency)
    - Exponential backoff with jitter on recovery timeout (avoids thundering herd)
    - Sliding window failure tracking (only recent failures count)
    - Health aggregation for engine-level status reporting
    - Distinct error classification: transient errors trip breaker, auth errors don't

References:
    - Nygard, M. (2007). "Release It!" — Chapter 5: Stability Patterns
    - Fowler, M. (2014). "Circuit Breaker" — martinfowler.com/bliki/CircuitBreaker.html
    - Netflix Hystrix (archived) — github.com/Netflix/Hystrix/wiki
"""

from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

from pydantic import BaseModel, Field

from ...core.logging import logger


# ──────────────────────────────────────────────────────────────────────────────
# State & Configuration
# ──────────────────────────────────────────────────────────────────────────────

class CircuitState(str, Enum):
    """Three-state circuit breaker as per Nygard's pattern."""
    CLOSED = "closed"        # Normal operation — requests pass through
    OPEN = "open"            # Tripped — requests fail fast
    HALF_OPEN = "half_open"  # Probing — limited requests to test recovery


class ProviderHealth(str, Enum):
    """Human-readable health status derived from circuit state."""
    HEALTHY = "healthy"          # CLOSED, no recent failures
    DEGRADED = "degraded"        # CLOSED but recent failures, or HALF_OPEN
    UNAVAILABLE = "unavailable"  # OPEN — not accepting requests


class CircuitBreakerConfig(BaseModel):
    """
    Configuration for a single circuit breaker instance.

    Defaults are tuned for LLM provider APIs:
    - 3 failures to trip (providers have occasional blips)
    - 60s recovery timeout (most provider outages resolve within minutes)
    - 2 successful probes to close (avoid flapping on single lucky request)
    - 30s request timeout (LLM responses can be slow)
    - 300s sliding window (only count recent failures)
    """
    failure_threshold: int = Field(default=3, ge=1, le=50)
    recovery_timeout_s: float = Field(default=60.0, ge=0.01, le=600.0)
    half_open_max_calls: int = Field(default=1, ge=1, le=5)
    success_threshold: int = Field(default=2, ge=1, le=10)
    request_timeout_s: float = Field(default=30.0, ge=0.1, le=120.0)
    sliding_window_s: float = Field(default=300.0, ge=0.01, le=3600.0)
    backoff_multiplier: float = Field(default=1.5, ge=1.0, le=4.0)
    max_recovery_timeout_s: float = Field(default=300.0, ge=0.1, le=1800.0)
    jitter_range: float = Field(default=0.1, ge=0.0, le=0.5)


# ──────────────────────────────────────────────────────────────────────────────
# Error Classification
# ──────────────────────────────────────────────────────────────────────────────

class ErrorCategory(str, Enum):
    """Classify errors to decide whether they should trip the breaker."""
    TRANSIENT = "transient"      # Timeouts, 5xx, rate limits → trip breaker
    AUTH = "auth"                # 401/403 → don't trip (configuration issue)
    VALIDATION = "validation"   # 400, bad request → don't trip (caller error)
    UNKNOWN = "unknown"         # Unclassified → trip breaker (conservative)


def classify_error(error: Exception) -> ErrorCategory:
    """
    Classify an exception to determine if it should trip the circuit breaker.

    Only transient errors (timeouts, server errors, rate limits) should trip.
    Auth and validation errors are configuration/caller issues, not provider health.
    """
    error_str = str(error).lower()

    # Auth errors — provider is fine, credentials are wrong
    if any(kw in error_str for kw in ("401", "403", "unauthorized", "forbidden", "invalid api key", "authentication")):
        return ErrorCategory.AUTH

    # Validation errors — caller's fault
    if any(kw in error_str for kw in ("400", "bad request", "invalid", "validation")):
        return ErrorCategory.VALIDATION

    # Timeouts — classic transient failure
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return ErrorCategory.TRANSIENT

    # Rate limits — transient, provider is healthy but overloaded
    if any(kw in error_str for kw in ("429", "rate limit", "too many requests", "quota")):
        return ErrorCategory.TRANSIENT

    # Server errors — provider is unhealthy
    if any(kw in error_str for kw in ("500", "502", "503", "504", "server error", "internal error", "service unavailable")):
        return ErrorCategory.TRANSIENT

    # Connection errors — network issue
    if any(kw in error_str for kw in ("connect", "connection", "refused", "reset", "timeout", "eof", "broken pipe")):
        return ErrorCategory.TRANSIENT

    return ErrorCategory.UNKNOWN


# ──────────────────────────────────────────────────────────────────────────────
# Failure Record (sliding window tracking)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class _FailureRecord:
    """A single failure event with timestamp and error category."""
    timestamp: float
    error_message: str
    category: ErrorCategory


# ──────────────────────────────────────────────────────────────────────────────
# Per-Provider Breaker State
# ──────────────────────────────────────────────────────────────────────────────

class _BreakerState:
    """
    Internal state for a single circuit breaker instance.

    Thread-safe via asyncio.Lock. Uses a sliding window deque for failure
    tracking — only failures within the last `sliding_window_s` seconds count.
    """

    __slots__ = (
        "provider_id", "config", "state", "_failures", "success_count",
        "last_failure_time", "last_success_time", "last_state_change",
        "total_requests", "total_failures", "total_successes",
        "half_open_calls", "consecutive_opens", "_lock",
    )

    def __init__(self, provider_id: str, config: Optional[CircuitBreakerConfig] = None) -> None:
        self.provider_id = provider_id
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self._failures: Deque[_FailureRecord] = deque()
        self.success_count: int = 0
        self.last_failure_time: float = 0.0
        self.last_success_time: float = 0.0
        self.last_state_change: float = time.monotonic()
        self.total_requests: int = 0
        self.total_failures: int = 0
        self.total_successes: int = 0
        self.half_open_calls: int = 0
        self.consecutive_opens: int = 0  # For exponential backoff on recovery timeout
        self._lock = asyncio.Lock()

    def _prune_old_failures(self, now: float) -> None:
        """Remove failures outside the sliding window."""
        cutoff = now - self.config.sliding_window_s
        while self._failures and self._failures[0].timestamp < cutoff:
            self._failures.popleft()

    @property
    def active_failure_count(self) -> int:
        """Count of failures within the sliding window."""
        now = time.monotonic()
        self._prune_old_failures(now)
        return len(self._failures)

    def _get_recovery_timeout(self) -> float:
        """
        Calculate recovery timeout with exponential backoff + jitter.

        On first OPEN: use base recovery_timeout_s.
        On consecutive OPENs: multiply by backoff_multiplier^(consecutive_opens-1).
        Add random jitter to prevent thundering herd.

        Reference: AWS Architecture Blog — "Exponential Backoff and Jitter"
        """
        base = self.config.recovery_timeout_s
        if self.consecutive_opens > 1:
            base = min(
                base * (self.config.backoff_multiplier ** (self.consecutive_opens - 1)),
                self.config.max_recovery_timeout_s,
            )
        # Add jitter: ±jitter_range% of base
        jitter = base * self.config.jitter_range * (2 * random.random() - 1)
        return base + jitter

    async def can_execute(self) -> bool:
        """Check if a request is allowed through this breaker."""
        async with self._lock:
            self.total_requests += 1
            now = time.monotonic()

            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                recovery_timeout = self._get_recovery_timeout()
                elapsed = now - self.last_failure_time
                if elapsed >= recovery_timeout:
                    # Transition to HALF_OPEN — allow a probe
                    self._transition(CircuitState.HALF_OPEN, now)
                    self.half_open_calls = 0
                    self.success_count = 0
                    logger.info(
                        f"Circuit breaker [{self.provider_id}]: OPEN → HALF_OPEN "
                        f"(after {elapsed:.1f}s recovery, attempt #{self.consecutive_opens})"
                    )
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                # Only allow limited probe calls
                if self.half_open_calls < self.config.half_open_max_calls:
                    self.half_open_calls += 1
                    return True
                return False

            return False  # Should never reach here

    async def record_success(self) -> None:
        """Record a successful request. May transition HALF_OPEN → CLOSED."""
        async with self._lock:
            self.total_successes += 1
            self.last_success_time = time.monotonic()

            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self._transition(CircuitState.CLOSED, self.last_success_time)
                    self._failures.clear()
                    self.consecutive_opens = 0  # Reset backoff
                    logger.info(
                        f"Circuit breaker [{self.provider_id}]: HALF_OPEN → CLOSED "
                        f"({self.success_count} successful probes)"
                    )

            elif self.state == CircuitState.CLOSED:
                # Success in CLOSED state — prune old failures
                self._prune_old_failures(self.last_success_time)

    async def record_failure(self, error: str, category: Optional[ErrorCategory] = None) -> None:
        """
        Record a failed request. May transition CLOSED → OPEN or HALF_OPEN → OPEN.

        Only TRANSIENT and UNKNOWN errors trip the breaker.
        AUTH and VALIDATION errors are logged but don't affect state.
        """
        if category is None:
            category = ErrorCategory.TRANSIENT

        async with self._lock:
            self.total_failures += 1
            now = time.monotonic()
            self.last_failure_time = now

            # Non-transient errors don't trip the breaker
            if category in (ErrorCategory.AUTH, ErrorCategory.VALIDATION):
                logger.debug(
                    f"Circuit breaker [{self.provider_id}]: {category.value} error ignored "
                    f"for state tracking: {error[:100]}"
                )
                return

            # Record in sliding window
            self._failures.append(_FailureRecord(
                timestamp=now,
                error_message=error[:200],
                category=category,
            ))
            self._prune_old_failures(now)

            if self.state == CircuitState.HALF_OPEN:
                # Probe failed — go back to OPEN
                self.consecutive_opens += 1
                self._transition(CircuitState.OPEN, now)
                logger.warning(
                    f"Circuit breaker [{self.provider_id}]: HALF_OPEN → OPEN "
                    f"(probe failed: {error[:100]})"
                )

            elif self.state == CircuitState.CLOSED:
                if len(self._failures) >= self.config.failure_threshold:
                    self.consecutive_opens += 1
                    self._transition(CircuitState.OPEN, now)
                    logger.warning(
                        f"Circuit breaker [{self.provider_id}]: CLOSED → OPEN "
                        f"({len(self._failures)} failures in {self.config.sliding_window_s}s window)"
                    )

    def _transition(self, new_state: CircuitState, now: float) -> None:
        """Internal state transition helper."""
        old_state = self.state
        self.state = new_state
        self.last_state_change = now
        if new_state == CircuitState.HALF_OPEN:
            self.half_open_calls = 0
            self.success_count = 0

    def get_health(self) -> ProviderHealth:
        """Derive human-readable health from circuit state."""
        if self.state == CircuitState.CLOSED:
            if self.active_failure_count > 0:
                return ProviderHealth.DEGRADED
            return ProviderHealth.HEALTHY
        if self.state == CircuitState.HALF_OPEN:
            return ProviderHealth.DEGRADED
        return ProviderHealth.UNAVAILABLE

    def get_status(self) -> Dict[str, Any]:
        """Full status snapshot for health endpoints and debugging."""
        now = time.monotonic()
        self._prune_old_failures(now)
        return {
            "provider_id": self.provider_id,
            "state": self.state.value,
            "health": self.get_health().value,
            "active_failures": len(self._failures),
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "consecutive_opens": self.consecutive_opens,
            "time_in_state_s": round(now - self.last_state_change, 1),
            "last_failure_ago_s": round(now - self.last_failure_time, 1) if self.last_failure_time else None,
            "last_success_ago_s": round(now - self.last_success_time, 1) if self.last_success_time else None,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout_s": self.config.recovery_timeout_s,
                "request_timeout_s": self.config.request_timeout_s,
            },
        }

    async def reset(self) -> None:
        """Reset breaker to CLOSED state. Used by admin/tests."""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self._failures.clear()
            self.success_count = 0
            self.half_open_calls = 0
            self.consecutive_opens = 0
            self.last_state_change = time.monotonic()
            logger.info(f"Circuit breaker [{self.provider_id}]: RESET → CLOSED")


# ──────────────────────────────────────────────────────────────────────────────
# Registry — manages per-provider breakers
# ──────────────────────────────────────────────────────────────────────────────

class CircuitBreakerRegistry:
    """
    Global registry of per-provider circuit breakers.

    Each LLM provider gets its own independent breaker so that one provider's
    outage doesn't affect others. This is the "bulkhead" pattern from
    Nygard (2007) applied to our multi-provider architecture.

    Usage:
        registry = get_circuit_breaker_registry()
        if await registry.can_execute("openai"):
            try:
                result = await call_openai(...)
                await registry.record_success("openai")
            except Exception as e:
                category = classify_error(e)
                await registry.record_failure("openai", str(e), category)
        else:
            # Provider circuit is OPEN — skip or use fallback
            pass
    """

    def __init__(self, default_config: Optional[CircuitBreakerConfig] = None) -> None:
        self._breakers: Dict[str, _BreakerState] = {}
        self._default_config = default_config or CircuitBreakerConfig()
        self._lock = asyncio.Lock()

    def _get_or_create(self, provider_id: str) -> _BreakerState:
        """Get existing breaker or create one with default config."""
        if provider_id not in self._breakers:
            self._breakers[provider_id] = _BreakerState(provider_id, self._default_config)
        return self._breakers[provider_id]

    async def can_execute(self, provider_id: str) -> bool:
        """Check if a provider's circuit allows a request."""
        breaker = self._get_or_create(provider_id)
        return await breaker.can_execute()

    async def record_success(self, provider_id: str) -> None:
        """Record a successful call to a provider."""
        breaker = self._get_or_create(provider_id)
        await breaker.record_success()

    async def record_failure(
        self,
        provider_id: str,
        error: str,
        category: Optional[ErrorCategory] = None,
    ) -> None:
        """Record a failed call to a provider."""
        breaker = self._get_or_create(provider_id)
        await breaker.record_failure(error, category)

    def get_health(self, provider_id: str) -> ProviderHealth:
        """Get health status for a single provider."""
        breaker = self._get_or_create(provider_id)
        return breaker.get_health()

    def get_all_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all known providers."""
        return {pid: breaker.get_status() for pid, breaker in self._breakers.items()}

    def get_healthy_providers(self) -> List[str]:
        """Return list of provider IDs that are HEALTHY or DEGRADED (not OPEN)."""
        return [
            pid for pid, breaker in self._breakers.items()
            if breaker.state != CircuitState.OPEN
        ]

    def get_unavailable_providers(self) -> List[str]:
        """Return list of provider IDs that are OPEN (unavailable)."""
        return [
            pid for pid, breaker in self._breakers.items()
            if breaker.state == CircuitState.OPEN
        ]

    async def reset(self, provider_id: str) -> None:
        """Reset a single provider's breaker."""
        if provider_id in self._breakers:
            await self._breakers[provider_id].reset()

    async def reset_all(self) -> None:
        """Reset all breakers. Used in tests and admin recovery."""
        for breaker in self._breakers.values():
            await breaker.reset()

    def configure_provider(
        self,
        provider_id: str,
        config: CircuitBreakerConfig,
    ) -> None:
        """Set custom config for a specific provider."""
        breaker = self._get_or_create(provider_id)
        breaker.config = config

    @property
    def provider_count(self) -> int:
        return len(self._breakers)


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the application-wide circuit breaker registry singleton."""
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry()
    return _registry
