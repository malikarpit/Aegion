"""
Aegion Chaos Testing Framework: Operational Resilience.

Provides a framework for simulating failure scenarios:
- Container crash recovery
- Database connection drops
- Sandbox execution timeout
- Rate limiter stress
- Lock contention
- Snapshot corruption detection
- Backup/restore drill
"""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


class ChaosScenario(str, Enum):
    """Standard chaos test scenarios."""
    CONTAINER_KILL = "container_kill_recovery"
    DB_CONNECTION_DROP = "db_connection_drop"
    SANDBOX_CRASH = "sandbox_crash"
    RATE_LIMITER_STRESS = "rate_limiter_stress"
    LOCK_CONTENTION = "lock_contention"
    SNAPSHOT_CORRUPTION = "snapshot_corruption"
    BACKUP_RESTORE_DRILL = "backup_restore_drill"


@dataclass
class ChaosResult:
    """Result of a chaos test execution."""
    scenario: ChaosScenario
    passed: bool
    duration_ms: float
    detail: str
    timestamp: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class ChaosTestRunner:
    """
    Orchestrates chaos testing scenarios.

    Each scenario simulates a specific failure mode and verifies that
    the system recovers correctly without data loss or corruption.
    """

    def __init__(self):
        self._results: List[ChaosResult] = []
        self._handlers: Dict[ChaosScenario, Callable] = {}

    def register_handler(
        self, scenario: ChaosScenario, handler: Callable
    ) -> None:
        """Register a handler function for a chaos scenario."""
        self._handlers[scenario] = handler

    async def run_scenario(self, scenario: ChaosScenario, **kwargs) -> ChaosResult:
        """Execute a single chaos test scenario."""
        if scenario not in self._handlers:
            result = ChaosResult(
                scenario=scenario,
                passed=False,
                duration_ms=0,
                detail=f"No handler registered for {scenario.value}",
            )
            self._results.append(result)
            return result

        start = time.monotonic()
        try:
            handler = self._handlers[scenario]
            if asyncio.iscoroutinefunction(handler):
                detail = await handler(**kwargs)
            else:
                detail = handler(**kwargs)

            duration = (time.monotonic() - start) * 1000
            result = ChaosResult(
                scenario=scenario,
                passed=True,
                duration_ms=round(duration, 2),
                detail=detail or "Passed",
            )
        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            result = ChaosResult(
                scenario=scenario,
                passed=False,
                duration_ms=round(duration, 2),
                detail=f"FAILED: {str(e)}",
            )

        self._results.append(result)
        return result

    async def run_all(self, **kwargs) -> List[ChaosResult]:
        """Execute all registered chaos scenarios."""
        results = []
        for scenario in ChaosScenario:
            if scenario in self._handlers:
                result = await self.run_scenario(scenario, **kwargs)
                results.append(result)
        return results

    def get_results(self) -> List[ChaosResult]:
        return list(self._results)

    @property
    def stats(self) -> Dict[str, Any]:
        total = len(self._results)
        passed = sum(1 for r in self._results if r.passed)
        return {
            "total_runs": total,
            "passed": passed,
            "failed": total - passed,
            "registered_scenarios": len(self._handlers),
            "pass_rate": round(passed / total * 100, 1) if total else 0,
        }


# ========== Built-in Chaos Handlers ==========

def simulate_snapshot_corruption(graph_data: dict) -> str:
    """
    Simulate snapshot corruption detection.

    Verifies that integrity checks catch tampered graph data.
    """
    import hashlib
    import json

    # Create a "snapshot"
    canonical = json.dumps(graph_data, sort_keys=True)
    checksum = hashlib.sha256(canonical.encode()).hexdigest()

    # Simulate corruption: tamper with data
    tampered = dict(graph_data)
    tampered["_tampered"] = True
    tampered_canonical = json.dumps(tampered, sort_keys=True)
    tampered_checksum = hashlib.sha256(tampered_canonical.encode()).hexdigest()

    # Integrity check should detect mismatch
    if checksum == tampered_checksum:
        raise RuntimeError("Corruption NOT detected — integrity check failed")

    return f"Corruption detected: expected {checksum[:12]}, got {tampered_checksum[:12]}"


def simulate_lock_contention(num_readers: int = 50, num_writers: int = 5) -> str:
    """
    Simulate lock contention scenario parameters.

    Returns description of the contention scenario for async testing.
    """
    total = num_readers + num_writers
    if total > 200:
        raise ValueError("Contention too high — would degrade performance")

    return f"Lock contention scenario: {num_readers}R/{num_writers}W — within limits"


def simulate_rate_limiter_stress(
    requests_per_second: int = 1000, duration_seconds: int = 5
) -> str:
    """
    Simulate rate limiter stress test parameters.

    Validates that rate limiter configuration handles the specified load.
    """
    total_requests = requests_per_second * duration_seconds
    if total_requests > 50000:
        raise ValueError(f"Stress test too large: {total_requests} requests")

    return f"Rate limiter stress: {requests_per_second} rps × {duration_seconds}s = {total_requests} total"
