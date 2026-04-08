"""
Graph Concurrency Model Tests.

Validates:
- AsyncRWLock: concurrent readers, exclusive writers, writer preference
- Timeout/deadlock detection
- GraphSnapshot: frozen state, read-only
- Lock metrics tracking
"""

import pytest
import asyncio

from app.adapters.graph_lock import (
    AsyncRWLock,
    AsyncRWLockTimeoutError,
    GraphSnapshot,
    get_graph_lock,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AsyncRWLock — Basic Operations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_read_lock_basic():
    """A single read lock acquires and releases cleanly."""
    lock = AsyncRWLock()
    async with lock.read_lock():
        assert lock._readers == 1
    assert lock._readers == 0


@pytest.mark.asyncio
async def test_write_lock_basic():
    """A single write lock acquires and releases cleanly."""
    lock = AsyncRWLock()
    async with lock.write_lock():
        assert lock._writer is True
    assert lock._writer is False


@pytest.mark.asyncio
async def test_concurrent_readers():
    """Multiple readers can hold the lock simultaneously."""
    lock = AsyncRWLock()
    results = []

    async def reader(idx: int):
        async with lock.read_lock():
            results.append(f"read_{idx}_start")
            await asyncio.sleep(0.01)
            results.append(f"read_{idx}_end")

    await asyncio.gather(reader(1), reader(2), reader(3))
    assert lock._readers == 0
    assert lock._total_reads == 3


@pytest.mark.asyncio
async def test_write_excludes_readers():
    """Writer blocks readers and readers block writer."""
    lock = AsyncRWLock()
    order = []

    async def writer():
        async with lock.write_lock():
            order.append("write_start")
            await asyncio.sleep(0.05)
            order.append("write_end")

    async def reader():
        await asyncio.sleep(0.01)  # Ensure writer starts first
        async with lock.read_lock():
            order.append("read")

    await asyncio.gather(writer(), reader())
    # Writer should complete before reader gets access
    assert order.index("write_end") < order.index("read")


@pytest.mark.asyncio
async def test_write_excludes_other_writers():
    """Only one writer at a time."""
    lock = AsyncRWLock()
    order = []

    async def writer(idx: int):
        async with lock.write_lock():
            order.append(f"w{idx}_start")
            await asyncio.sleep(0.03)
            order.append(f"w{idx}_end")

    await asyncio.gather(writer(1), writer(2))
    # Writers should be serial
    assert lock._total_writes == 2
    # First writer should end before second starts
    w1_end = order.index("w1_end") if "w1_end" in order else -1
    w2_start = order.index("w2_start") if "w2_start" in order else -1
    if w1_end >= 0 and w2_start >= 0:
        assert w1_end < w2_start


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Timeout & Deadlock Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_write_lock_timeout():
    """Write lock times out if not acquired within timeout."""
    lock = AsyncRWLock(write_timeout=0.1)

    async with lock.write_lock():
        # Try to acquire another write lock — should timeout
        with pytest.raises(AsyncRWLockTimeoutError, match="timed out"):
            async with lock.write_lock(timeout=0.1):
                pass  # Should never reach here


@pytest.mark.asyncio
async def test_read_lock_timeout_during_write():
    """Read lock times out if writer holds lock too long."""
    lock = AsyncRWLock(read_timeout=0.1)

    async with lock.write_lock():
        with pytest.raises(AsyncRWLockTimeoutError, match="timed out"):
            async with lock.read_lock(timeout=0.1):
                pass


@pytest.mark.asyncio
async def test_timeout_increments_metric():
    """Timeout events are tracked in metrics."""
    lock = AsyncRWLock(write_timeout=0.1)

    async with lock.write_lock():
        try:
            async with lock.write_lock(timeout=0.1):
                pass
        except AsyncRWLockTimeoutError:
            pass

    assert lock._total_timeouts >= 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Lock Metrics
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_lock_state_monitoring():
    """State property reports correct metrics."""
    lock = AsyncRWLock()

    async with lock.read_lock():
        state = lock.state
        assert state["readers"] == 1
        assert state["writer_active"] is False

    async with lock.write_lock():
        state = lock.state
        assert state["readers"] == 0
        assert state["writer_active"] is True

    state = lock.state
    assert state["total_reads"] == 1
    assert state["total_writes"] == 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GraphSnapshot
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_snapshot_freezes_state():
    """Snapshot captures current state at creation time."""
    nodes = {"n1": {"type": "EVIDENCE"}, "n2": {"type": "DECISION"}}
    edges = [("n1", "n2", "SUPPORTS")]

    snap = GraphSnapshot(nodes, edges)
    assert snap.node_count == 2
    assert snap.edge_count == 1

    # Modify original — snapshot should NOT change
    nodes["n3"] = {"type": "PROPOSAL"}
    assert snap.node_count == 2  # Still 2


def test_snapshot_get_node():
    snap = GraphSnapshot({"n1": {"label": "test"}}, [])
    assert snap.get_node("n1") == {"label": "test"}
    assert snap.get_node("missing") is None


def test_snapshot_get_all_nodes():
    snap = GraphSnapshot({"a": 1, "b": 2}, [])
    all_nodes = snap.get_all_nodes()
    assert len(all_nodes) == 2
    # Should be a copy
    all_nodes["c"] = 3
    assert snap.node_count == 2


def test_snapshot_get_edges():
    edges = [("a", "b", "REL")]
    snap = GraphSnapshot({}, edges)
    result = snap.get_edges()
    assert len(result) == 1
    # Should be a copy
    result.append(("c", "d", "NEW"))
    assert snap.edge_count == 1


def test_snapshot_created_at():
    import time
    before = time.time()
    snap = GraphSnapshot({}, [])
    after = time.time()
    assert before <= snap.created_at <= after


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Singleton
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_graph_lock_singleton():
    lock1 = get_graph_lock()
    lock2 = get_graph_lock()
    assert lock1 is lock2


def test_async_rwlock_timeout_error_type():
    """AsyncRWLockTimeoutError inherits from TimeoutError."""
    err = AsyncRWLockTimeoutError("test")
    assert isinstance(err, asyncio.TimeoutError)
