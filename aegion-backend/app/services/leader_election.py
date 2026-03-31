"""
Aegion Leader Election: Multi-Instance Scaling.

Redis-based leader election using SET NX EX pattern:
- Only leader mutates governance state (preserves Archon authority)
- Heartbeat renewal (every 10s, 30s TTL)
- Leadership change events
- Graceful leader step-down
"""

import asyncio
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class LeaderInfo:
    """Information about the current leader."""
    instance_id: str
    elected_at: str
    last_heartbeat: str
    is_self: bool


class LeaderElection:
    """
    Redis-based leader election for multi-instance Aegion deployments.

    Uses SET NX EX pattern:
    - SET leader_key instance_id NX EX 30
    - Only one instance succeeds (becomes leader)
    - Leader renews heartbeat every 10s
    - If leader dies, lock expires after 30s, new election happens

    In-memory fallback for single-instance deployments.
    """

    LOCK_KEY = "aegion:leader"
    TTL_SECONDS = 30
    HEARTBEAT_INTERVAL = 10

    def __init__(self, redis_client=None, instance_id: Optional[str] = None):
        self._redis = redis_client
        self._instance_id = instance_id or str(uuid.uuid4())[:8]
        self._is_leader = False
        self._elected_at: Optional[str] = None
        self._last_heartbeat: Optional[str] = None
        self._leadership_changes: List[Dict[str, str]] = []
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Single-instance mode (no Redis)
        if self._redis is None:
            self._is_leader = True
            self._elected_at = datetime.now(timezone.utc).isoformat()
            self._last_heartbeat = self._elected_at

    @property
    def instance_id(self) -> str:
        return self._instance_id

    @property
    def is_leader(self) -> bool:
        return self._is_leader

    async def try_acquire(self) -> bool:
        """Attempt to acquire leadership."""
        if self._redis is None:
            # Single-instance: always leader
            return True

        # Try SET NX EX
        acquired = await self._redis.set(
            self.LOCK_KEY,
            self._instance_id,
            nx=True,
            ex=self.TTL_SECONDS,
        )

        if acquired:
            self._is_leader = True
            self._elected_at = datetime.now(timezone.utc).isoformat()
            self._last_heartbeat = self._elected_at
            self._record_change("elected")
            return True

        return False

    async def renew_heartbeat(self) -> bool:
        """Renew leadership heartbeat (extend TTL)."""
        if not self._is_leader:
            return False

        if self._redis is None:
            self._last_heartbeat = datetime.now(timezone.utc).isoformat()
            return True

        # Verify we're still the leader, then extend
        current = await self._redis.get(self.LOCK_KEY)
        if current and current.decode() == self._instance_id:
            await self._redis.expire(self.LOCK_KEY, self.TTL_SECONDS)
            self._last_heartbeat = datetime.now(timezone.utc).isoformat()
            return True

        # Lost leadership
        self._is_leader = False
        self._record_change("lost")
        return False

    async def step_down(self) -> None:
        """Voluntarily release leadership."""
        if not self._is_leader:
            return

        if self._redis is not None:
            current = await self._redis.get(self.LOCK_KEY)
            if current and current.decode() == self._instance_id:
                await self._redis.delete(self.LOCK_KEY)

        self._is_leader = False
        self._record_change("stepped_down")

    async def get_leader(self) -> Optional[LeaderInfo]:
        """Get info about the current leader."""
        if self._redis is None:
            if self._is_leader:
                return LeaderInfo(
                    instance_id=self._instance_id,
                    elected_at=self._elected_at or "",
                    last_heartbeat=self._last_heartbeat or "",
                    is_self=True,
                )
            return None

        current = await self._redis.get(self.LOCK_KEY)
        if current:
            leader_id = current.decode()
            return LeaderInfo(
                instance_id=leader_id,
                elected_at=self._elected_at or "" if leader_id == self._instance_id else "",
                last_heartbeat=self._last_heartbeat or "" if leader_id == self._instance_id else "",
                is_self=(leader_id == self._instance_id),
            )
        return None

    def require_leadership(self) -> None:
        """Guard: raises if not leader. Use before governance mutations."""
        if not self._is_leader:
            raise NotLeaderError(
                f"Instance {self._instance_id} is not the leader. "
                "Governance mutations require leadership."
            )

    def _record_change(self, event: str) -> None:
        self._leadership_changes.append({
            "event": event,
            "instance_id": self._instance_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_leadership_history(self) -> List[Dict[str, str]]:
        return list(self._leadership_changes)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "instance_id": self._instance_id,
            "is_leader": self._is_leader,
            "elected_at": self._elected_at,
            "total_changes": len(self._leadership_changes),
        }


class NotLeaderError(Exception):
    """Raised when a non-leader instance attempts governance mutation."""
    pass


# ========== Singleton ==========

_election: Optional[LeaderElection] = None


def get_leader_election() -> LeaderElection:
    global _election
    if _election is None:
        _election = LeaderElection()  # Single-instance by default
    return _election
