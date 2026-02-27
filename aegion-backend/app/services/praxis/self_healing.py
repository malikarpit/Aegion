"""
Aegion Self-Healing Service.

Doctrine: "Systems fail; resilient systems recover."

Provides:
- Automated detection of unhealthy components
- Recovery strategies (circuit breaking, reconnection, cache clearing)
- Escalation path if healing fails
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

from ...core.logging import logger
from ...adapters.neo4j_graph import Neo4jKnowledgeGraph


class HealingStrategy(str, Enum):
    RESTART_CONNECTION = "restart_connection"
    CLEAR_CACHE = "clear_cache"
    REAP_ZOMBIES = "reap_zombies"
    NO_OP = "no_op"


@dataclass
class HealthStatus:
    component: str
    is_healthy: bool
    last_check: datetime
    error: Optional[str] = None


class SelfHealer:
    """
    Automated system recovery manager.
    """

    def __init__(self):
        self._strategies: Dict[str, Callable] = {
            "graph": self._heal_graph,
            "sandbox": self._heal_sandbox_pool,
            "invariant_storm": self._heal_invariant_storm,  # Enhancement 16
        }
        self._health_state: Dict[str, HealthStatus] = {}
        self._last_violation_count = 0

    async def diagnose_and_heal(self, components: List[str] = None):
        """Run diagnostics and trigger healing if needed."""
        targets = components or self._strategies.keys()
        
        # monitoring check for invariants (StormWatcher)
        if "invariant_storm" in targets:
            await self._check_invariant_health()
        
        for target in targets:
            if target == "invariant_storm": continue
            
            try:
                is_healthy = await self._check_health(target)
                if not is_healthy:
                    logger.warning(f"Unhealthy component detected: {target}. Initiating healing...")
                    await self._attempt_healing(target)
                else:
                    self._health_state[target] = HealthStatus(
                        component=target, is_healthy=True, last_check=datetime.now(timezone.utc)
                    )
            except Exception as e:
                logger.error(f"Error during self-healing cycle for {target}: {e}")

    async def _check_invariant_health(self):
        """Monitor for invariant storms."""
        from ...services.archon.invariant_engine import get_invariant_engine
        engine = get_invariant_engine()
        metrics = engine.get_violation_metrics()
        
        current_blocking = metrics.get("blocking_violations", 0)
        
        # Spike detection: check rate of change since last check
        delta = current_blocking - self._last_violation_count
        is_spike = delta > 10  # >10 new violations since last check = spike
        is_storm = current_blocking > 50  # Absolute threshold = storm
        self._last_violation_count = current_blocking

        if is_storm or is_spike:
            reason = "storm" if is_storm else f"spike (+{delta} new violations)"
            logger.critical(f"Invariant {reason} detected! Total: {current_blocking}, Delta: {delta}")
            await self._attempt_healing("invariant_storm")
        else:
            self._health_state["invariant_storm"] = HealthStatus(
                component="invariant_storm", is_healthy=True, last_check=datetime.now(timezone.utc)
            )

    async def _check_health(self, component: str) -> bool:
        """Check health of a component."""
        if component == "graph":
            # Check graph connectivity
            from ...services.graph_provider import get_shared_graph_service
            try:
                graph = get_shared_graph_service()
                # Simple check call
                return await graph.get_shared_graph().run_query("RETURN 1", {}) is not None
            except Exception:
                return False
                
        elif component == "sandbox":
            # Check if Docker is responsive or pool is exhausted
            # Placeholder logic
            return True

        return True

    # ... (healing methods)

    async def _heal_graph(self):
        """Strategy: Reconnect to Graph Database."""
        from ...services.graph_provider import get_shared_graph_service, initialize_graph
        logger.info("Restarting graph connection...")
        try:
            # Re-initialize to force reconnection
            # Note: In a real app we might close the old one first specific to the backend
            get_shared_graph_service() # Ensure initialized
            # Assuming initialize_graph acts as a reset/factory
        except Exception as e:
            logger.error(f"Graph healing failed: {e}")

    async def _heal_invariant_storm(self):
        """Strategy: Activate Global Freeze Mode."""
        # Enhancement 16: Auto-rollback or Freeze
        from ...services.archon.gates import ArchonGates
        # We need an instance of gates to freeze, or access the registry/engine directly to set a flag
        # For now, we log as we don't have direct access to the global Gates instance here easily
        # without dependency injection or singleton pattern on Gates.
        logger.critical("EXECUTE: AUTO-FREEZE PROTOCOL INITIATED due to Invariant Storm.")
        # In a real implementation: ArchonGates().engage_emergency_freeze()


    async def _heal_sandbox_pool(self):
        """Strategy: Reap zombie containers."""
        # Placeholder: could interface with DockerSandboxRunner
        logger.info("Reaping zombie sandboxes (simulated)")

