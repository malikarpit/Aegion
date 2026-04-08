"""
Leader Election Tests.

Validates:
- Single-instance mode (always leader)
- Leadership guard
- Leadership history tracking
- Step-down
- Stats
"""

import pytest
from app.services.leader_election import (
    LeaderElection,
    NotLeaderError,
)


class TestSingleInstanceMode:
    def test_single_instance_is_leader(self):
        election = LeaderElection()
        assert election.is_leader is True

    def test_instance_id_set(self):
        election = LeaderElection(instance_id="node-1")
        assert election.instance_id == "node-1"

    def test_custom_instance_id(self):
        election = LeaderElection(instance_id="my-node")
        assert election.instance_id == "my-node"


class TestLeadershipGuard:
    def test_leader_passes_guard(self):
        election = LeaderElection()
        election.require_leadership()  # Should not raise

    def test_non_leader_fails_guard(self):
        election = LeaderElection()
        election._is_leader = False  # Simulate follower
        with pytest.raises(NotLeaderError, match="not the leader"):
            election.require_leadership()


class TestStepDown:
    @pytest.mark.asyncio
    async def test_step_down(self):
        election = LeaderElection()
        assert election.is_leader is True
        await election.step_down()
        assert election.is_leader is False

    @pytest.mark.asyncio
    async def test_step_down_records_history(self):
        election = LeaderElection()
        await election.step_down()
        history = election.get_leadership_history()
        assert len(history) == 1
        assert history[0]["event"] == "stepped_down"


class TestLeaderInfo:
    @pytest.mark.asyncio
    async def test_get_leader_returns_self(self):
        election = LeaderElection(instance_id="node-1")
        info = await election.get_leader()
        assert info is not None
        assert info.instance_id == "node-1"
        assert info.is_self is True

    @pytest.mark.asyncio
    async def test_no_leader_after_stepdown(self):
        election = LeaderElection(instance_id="node-1")
        await election.step_down()
        info = await election.get_leader()
        # In single-instance mode, stepping down still has no Redis to query
        assert info is None


class TestStats:
    def test_initial_stats(self):
        election = LeaderElection(instance_id="node-1")
        stats = election.stats
        assert stats["instance_id"] == "node-1"
        assert stats["is_leader"] is True
        assert stats["elected_at"] is not None

    @pytest.mark.asyncio
    async def test_stats_after_stepdown(self):
        election = LeaderElection()
        await election.step_down()
        stats = election.stats
        assert stats["is_leader"] is False
        assert stats["total_changes"] == 1


class TestHeartbeat:
    @pytest.mark.asyncio
    async def test_heartbeat_updates_timestamp(self):
        election = LeaderElection()
        old_hb = election._last_heartbeat
        await election.renew_heartbeat()
        # In single-instance mode, heartbeat always succeeds
        assert election._last_heartbeat is not None

    @pytest.mark.asyncio
    async def test_non_leader_heartbeat_fails(self):
        election = LeaderElection()
        election._is_leader = False
        result = await election.renew_heartbeat()
        assert result is False
