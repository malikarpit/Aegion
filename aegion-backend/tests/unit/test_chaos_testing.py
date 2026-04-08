"""
Chaos Testing Framework Tests.

Validates:
- Scenario registration and execution
- Pass/fail result tracking
- Async handler support
- Built-in chaos handlers (snapshot corruption, lock contention, rate limiter stress)
- Stats calculation
"""

import asyncio
import pytest
from app.services.chaos_testing import (
    ChaosTestRunner,
    ChaosScenario,
    ChaosResult,
    simulate_snapshot_corruption,
    simulate_lock_contention,
    simulate_rate_limiter_stress,
)


class TestChaosTestRunner:
    @pytest.fixture
    def runner(self):
        return ChaosTestRunner()

    @pytest.mark.asyncio
    async def test_unregistered_scenario_fails(self, runner):
        result = await runner.run_scenario(ChaosScenario.CONTAINER_KILL)
        assert result.passed is False
        assert "No handler" in result.detail

    @pytest.mark.asyncio
    async def test_sync_handler(self, runner):
        def ok_handler(**kwargs):
            return "All good"

        runner.register_handler(ChaosScenario.LOCK_CONTENTION, ok_handler)
        result = await runner.run_scenario(ChaosScenario.LOCK_CONTENTION)
        assert result.passed is True
        assert "All good" in result.detail

    @pytest.mark.asyncio
    async def test_async_handler(self, runner):
        async def async_handler(**kwargs):
            await asyncio.sleep(0.01)
            return "Async OK"

        runner.register_handler(ChaosScenario.DB_CONNECTION_DROP, async_handler)
        result = await runner.run_scenario(ChaosScenario.DB_CONNECTION_DROP)
        assert result.passed is True
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_failing_handler(self, runner):
        def fail_handler(**kwargs):
            raise RuntimeError("Simulated failure")

        runner.register_handler(ChaosScenario.SANDBOX_CRASH, fail_handler)
        result = await runner.run_scenario(ChaosScenario.SANDBOX_CRASH)
        assert result.passed is False
        assert "Simulated failure" in result.detail

    @pytest.mark.asyncio
    async def test_run_all(self, runner):
        runner.register_handler(ChaosScenario.LOCK_CONTENTION, lambda **kw: "OK")
        runner.register_handler(ChaosScenario.SNAPSHOT_CORRUPTION, lambda **kw: "OK")
        results = await runner.run_all()
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_stats(self, runner):
        runner.register_handler(ChaosScenario.LOCK_CONTENTION, lambda **kw: "OK")

        def fail(**kw):
            raise Exception("boom")

        runner.register_handler(ChaosScenario.SANDBOX_CRASH, fail)
        await runner.run_all()
        stats = runner.stats
        assert stats["total_runs"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1


class TestBuiltInHandlers:
    def test_snapshot_corruption_detected(self):
        result = simulate_snapshot_corruption({"nodes": 42, "edges": 10})
        assert "Corruption detected" in result

    def test_lock_contention_within_limits(self):
        result = simulate_lock_contention(50, 5)
        assert "50R/5W" in result

    def test_lock_contention_too_high(self):
        with pytest.raises(ValueError, match="too high"):
            simulate_lock_contention(200, 50)

    def test_rate_limiter_stress_ok(self):
        result = simulate_rate_limiter_stress(1000, 5)
        assert "5000" in result

    def test_rate_limiter_stress_too_large(self):
        with pytest.raises(ValueError, match="too large"):
            simulate_rate_limiter_stress(100000, 10)
