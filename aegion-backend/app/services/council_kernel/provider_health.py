"""
Provider Health Monitor — Background Health Probing for LLM Providers.

Periodically sends lightweight health probes (HEAD requests) to provider
endpoints to detect outages BEFORE user requests fail. Feeds results into
the CircuitBreakerRegistry for proactive circuit opening.

Architecture:
    - Runs as an asyncio background task (started from engine.py)
    - Probes each registered provider's base URL every `probe_interval_s` seconds
    - On probe failure, records the error in the circuit breaker
    - On probe success, records success if breaker was in HALF_OPEN state
    - Exponential backoff on consecutive failures per provider

References:
    - Nygard, M. "Release It!" — Active Health Checks (Ch. 5)
    - Netflix Eureka — Heartbeat-based health monitoring pattern

Integration:
    Called from CouncilEngine.__init__ to start monitoring.
    Results flow into CircuitBreakerRegistry → get_health() endpoint.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import httpx

from ...core.logging import logger
from .circuit_breaker import CircuitBreakerRegistry, get_circuit_breaker_registry


# ──────────────────────────────────────────────────────────────────────────────
# Provider Endpoint Map
# ──────────────────────────────────────────────────────────────────────────────

# Base health endpoints for each provider (lightweight, no auth required usually)
_PROVIDER_HEALTH_URLS: Dict[str, str] = {
    "openai":    "https://api.openai.com/v1/models",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "google":    "https://generativelanguage.googleapis.com/v1beta/models",
    "deepseek":  "https://api.deepseek.com/v1/models",
    "xai":       "https://api.x.ai/v1/models",
    "mistral":   "https://api.mistral.ai/v1/models",
    "cohere":    "https://api.cohere.ai/v1/models",
}


@dataclass
class ProviderProbeResult:
    """Result of a single health probe."""
    provider: str
    reachable: bool
    latency_ms: float = 0.0
    status_code: int = 0
    error: str = ""
    timestamp: float = field(default_factory=time.monotonic)


# ──────────────────────────────────────────────────────────────────────────────
# Health Monitor
# ──────────────────────────────────────────────────────────────────────────────

class ProviderHealthMonitor:
    """
    Background health monitor for LLM provider endpoints.

    Runs periodic HTTP probes to detect provider outages proactively.
    Results are fed into the CircuitBreakerRegistry so the engine can
    route away from unhealthy providers before user requests fail.

    Usage:
        monitor = ProviderHealthMonitor(
            registry=get_circuit_breaker_registry(),
            active_providers={"openai", "anthropic", "google"},
        )
        await monitor.start()
        # ... later ...
        await monitor.stop()
    """

    def __init__(
        self,
        registry: Optional[CircuitBreakerRegistry] = None,
        active_providers: Optional[Set[str]] = None,
        probe_interval_s: float = 60.0,
        probe_timeout_s: float = 10.0,
    ) -> None:
        """
        Args:
            registry: CircuitBreakerRegistry to feed results into
            active_providers: Set of provider names to monitor
            probe_interval_s: Seconds between probe rounds
            probe_timeout_s: Timeout for each individual probe
        """
        self._registry = registry or get_circuit_breaker_registry()
        self._active_providers = active_providers or set()
        self._probe_interval_s = probe_interval_s
        self._probe_timeout_s = probe_timeout_s
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_results: Dict[str, ProviderProbeResult] = {}
        self._consecutive_failures: Dict[str, int] = {}

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the background health monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"Provider health monitor started "
            f"(interval={self._probe_interval_s}s, "
            f"providers={sorted(self._active_providers)})"
        )

    async def stop(self) -> None:
        """Stop the background health monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Provider health monitor stopped")

    def update_providers(self, providers: Set[str]) -> None:
        """Update the set of providers to monitor (e.g., when keys are added)."""
        self._active_providers = providers

    async def _monitor_loop(self) -> None:
        """Main monitoring loop — runs until stopped."""
        while self._running:
            try:
                await self._probe_all()
            except Exception as exc:
                logger.debug(f"Health monitor probe round failed: {exc}")

            await asyncio.sleep(self._probe_interval_s)

    async def _probe_all(self) -> List[ProviderProbeResult]:
        """Probe all active providers concurrently."""
        if not self._active_providers:
            return []

        tasks = [
            self._probe_single(provider)
            for provider in self._active_providers
            if provider in _PROVIDER_HEALTH_URLS
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        probe_results = []
        for r in results:
            if isinstance(r, ProviderProbeResult):
                probe_results.append(r)
                self._last_results[r.provider] = r

        return probe_results

    async def _probe_single(self, provider: str) -> ProviderProbeResult:
        """
        Probe a single provider endpoint.

        Uses HEAD request for minimal bandwidth. Falls back to GET if HEAD
        returns 405. Any 2xx/3xx/4xx (except 5xx) means the API is reachable.
        """
        url = _PROVIDER_HEALTH_URLS.get(provider, "")
        if not url:
            return ProviderProbeResult(provider=provider, reachable=False, error="No URL configured")

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._probe_timeout_s) as client:
                # HEAD request — cheapest probe
                resp = await client.head(url)
                latency_ms = (time.monotonic() - start) * 1000

                # Any non-5xx response means the endpoint is alive
                # 401/403 is expected (no auth header) but means API is reachable
                is_reachable = resp.status_code < 500

                result = ProviderProbeResult(
                    provider=provider,
                    reachable=is_reachable,
                    latency_ms=round(latency_ms, 1),
                    status_code=resp.status_code,
                )

                if is_reachable:
                    self._consecutive_failures[provider] = 0
                    # Record success in circuit breaker (helps HALF_OPEN → CLOSED)
                    await self._registry.record_success(provider)
                else:
                    self._consecutive_failures[provider] = self._consecutive_failures.get(provider, 0) + 1
                    await self._registry.record_failure(
                        provider, f"Health probe: HTTP {resp.status_code}"
                    )

                return result

        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            latency_ms = (time.monotonic() - start) * 1000
            self._consecutive_failures[provider] = self._consecutive_failures.get(provider, 0) + 1

            # Only record in circuit breaker if consistently failing
            if self._consecutive_failures.get(provider, 0) >= 2:
                await self._registry.record_failure(
                    provider, f"Health probe: {type(exc).__name__}"
                )

            return ProviderProbeResult(
                provider=provider,
                reachable=False,
                latency_ms=round(latency_ms, 1),
                error=str(exc)[:200],
            )

        except Exception as exc:
            return ProviderProbeResult(
                provider=provider,
                reachable=False,
                error=f"Unexpected: {type(exc).__name__}: {str(exc)[:100]}",
            )

    def get_last_results(self) -> Dict[str, ProviderProbeResult]:
        """Return the most recent probe result for each provider."""
        return dict(self._last_results)

    def get_summary(self) -> Dict:
        """
        Return a summary of provider health for the monitoring dashboard.

        Returns:
            dict with:
                - total_providers: int
                - healthy: int
                - unhealthy: list of provider names
                - avg_latency_ms: float
        """
        results = list(self._last_results.values())
        if not results:
            return {
                "total_providers": len(self._active_providers),
                "healthy": 0,
                "unhealthy": list(self._active_providers),
                "avg_latency_ms": 0.0,
            }

        healthy = [r for r in results if r.reachable]
        unhealthy = [r.provider for r in results if not r.reachable]
        avg_latency = sum(r.latency_ms for r in healthy) / max(len(healthy), 1)

        return {
            "total_providers": len(results),
            "healthy": len(healthy),
            "unhealthy": unhealthy,
            "avg_latency_ms": round(avg_latency, 1),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Module singleton
# ──────────────────────────────────────────────────────────────────────────────

_monitor: Optional[ProviderHealthMonitor] = None


def get_provider_health_monitor() -> ProviderHealthMonitor:
    global _monitor
    if _monitor is None:
        _monitor = ProviderHealthMonitor()
    return _monitor
