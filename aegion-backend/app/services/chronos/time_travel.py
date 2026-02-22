from typing import List, Optional, Dict, Any
from datetime import datetime
import copy

from pydantic import BaseModel

from ...core.logging import logger
from ...core.time import TimeAuthority


class StateSnapshot:
    """A snapshot of system state at a point in time."""
    def __init__(self, timestamp: str, state: Dict[str, Any]):
        self.timestamp = timestamp
        self.state = state
        self.snapshot_id = f"snap-{timestamp.replace(':', '-').replace('.', '-')}"


class TimeTravelService:
    """
    Service for temporal state navigation.
    
    Features:
    - Point-in-time snapshots
    - State reconstruction
    - Temporal queries
    """
    
    def __init__(self):
        self._snapshots: List[StateSnapshot] = []
        self._max_snapshots = 100
    
    async def capture_snapshot(
        self,
        state: Dict[str, Any],
        actor: str
    ) -> StateSnapshot:
        """Capture current state as a snapshot."""
        timestamp = TimeAuthority.now()
        snapshot = StateSnapshot(timestamp, copy.deepcopy(state))
        
        self._snapshots.append(snapshot)
        
        # Trim old snapshots
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]
        
        logger.audit(
            action="STATE_SNAPSHOT_CAPTURED",
            actor=actor,
            target=snapshot.snapshot_id,
            justification="Time travel checkpoint"
        )
        
        return snapshot
    
    async def get_state_at(
        self,
        target_timestamp: str
    ) -> Optional[Dict[str, Any]]:
        """Get system state at or before a specific timestamp."""
        # Find the closest snapshot at or before the target
        closest = None
        for snapshot in self._snapshots:
            if snapshot.timestamp <= target_timestamp:
                if closest is None or snapshot.timestamp > closest.timestamp:
                    closest = snapshot
        
        return copy.deepcopy(closest.state) if closest else None
    
    async def list_snapshots(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List available snapshots."""
        snapshots = self._snapshots
        
        if start_time:
            snapshots = [s for s in snapshots if s.timestamp >= start_time]
        if end_time:
            snapshots = [s for s in snapshots if s.timestamp <= end_time]
        
        return [
            {
                "snapshot_id": s.snapshot_id,
                "timestamp": s.timestamp,
                "keys": list(s.state.keys())
            }
            for s in snapshots[-limit:]
        ]
    
    async def diff_states(
        self,
        timestamp_a: str,
        timestamp_b: str
    ) -> Dict[str, Any]:
        """Compute difference between two points in time."""
        state_a = await self.get_state_at(timestamp_a)
        state_b = await self.get_state_at(timestamp_b)
        
        if not state_a or not state_b:
            return {"error": "Could not find states for comparison"}
        
        diff = {
            "added": {},
            "removed": {},
            "changed": {}
        }
        
        all_keys = set(state_a.keys()) | set(state_b.keys())
        
        for key in all_keys:
            if key not in state_a:
                diff["added"][key] = state_b[key]
            elif key not in state_b:
                diff["removed"][key] = state_a[key]
            elif state_a[key] != state_b[key]:
                diff["changed"][key] = {
                    "from": state_a[key],
                    "to": state_b[key]
                }
        
        return diff


# Singleton
_time_travel: Optional[TimeTravelService] = None


def get_time_travel() -> TimeTravelService:
    """Get singleton time travel service."""
    global _time_travel
    if _time_travel is None:
        _time_travel = TimeTravelService()
    return _time_travel


# Compatibility aliases for existing imports
TimeTravel = TimeTravelService


class SessionSnapshot(BaseModel):
    """Session state snapshot for time travel."""
    snapshot_id: str
    session_id: str
    timestamp: str
    state: Dict[str, Any]


class DecisionDiff(BaseModel):
    """Difference between two decision states."""
    from_timestamp: str
    to_timestamp: str
    added: Dict[str, Any]
    removed: Dict[str, Any]
    changed: Dict[str, Any]
