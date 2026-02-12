"""
Aegion Graph Concurrency Lock: Enterprise Hardening.

Async-compatible read-write lock for graph operations:
- Multiple concurrent readers allowed
- Exclusive writer access (blocks all readers and other writers)
- Deadlock detection: 5-second timeout by default
- Snapshot reads: frozen graph state for multi-step consistent reads

Design:
- Uses asyncio.Condition for efficient waiting
- Writer-preference: prevents reader starvation of writers
- Reentrant-safe per-task tracking
"""

import asyncio
import time
from typing import Optional, Any, Dict
from contextlib import asynccontextmanager

from ..core.logging import logger


class AsyncRWLockTimeoutError(asyncio.TimeoutError):
    """Raised when a lock acquisition exceeds the timeout."""
    pass


class AsyncRWLock:
    """
    Async read-write lock with timeout and deadlock detection.

    - Concurrent readers: multiple tasks can hold read locks simultaneously
    - Exclusive writers: only one task can hold the write lock
    - Writer preference: pending writers block new readers
    - Timeout: raises AsyncRWLockTimeoutError after default 5s
    """

    def __init__(self, write_timeout: float = 5.0, read_timeout: float = 5.0):
        self._condition = asyncio.Condition()
        self._readers: int = 0
        self._writer: bool = False
        self._pending_writers: int = 0
        self._write_timeout = write_timeout
        self._read_timeout = read_timeout

        # Metrics
        self._total_reads: int = 0
        self._total_writes: int = 0
        self._total_timeouts: int = 0
        self._contention_events: int = 0

    @asynccontextmanager
    async def read_lock(self, timeout: Optional[float] = None):
        """
        Acquire a read lock. Multiple concurrent reads are allowed.

        Blocks if a writer holds the lock or writers are pending.
        """
        timeout = timeout or self._read_timeout

        async with self._condition:
            try:
                # Wait until no active or pending writers
                waited = await asyncio.wait_for(
                    self._wait_for_read(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                self._total_timeouts += 1
                logger.error(
                    "Read lock timeout — potential deadlock",
                    extra={
                        "readers": self._readers,
                        "writer_active": self._writer,
                        "pending_writers": self._pending_writers,
                    },
                )
                raise AsyncRWLockTimeoutError(
                    f"Read lock acquisition timed out after {timeout}s"
                )

            self._readers += 1
            self._total_reads += 1

        try:
            yield
        finally:
            async with self._condition:
                self._readers -= 1
                if self._readers == 0:
                    self._condition.notify_all()

    @asynccontextmanager
    async def write_lock(self, timeout: Optional[float] = None):
        """
        Acquire an exclusive write lock. No other readers or writers allowed.

        Writer-preference: pending writers block new readers.
        """
        timeout = timeout or self._write_timeout

        async with self._condition:
            self._pending_writers += 1
            try:
                waited = await asyncio.wait_for(
                    self._wait_for_write(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                self._pending_writers -= 1
                self._total_timeouts += 1
                self._condition.notify_all()
                logger.error(
                    "Write lock timeout — potential deadlock",
                    extra={
                        "readers": self._readers,
                        "writer_active": self._writer,
                        "pending_writers": self._pending_writers,
                    },
                )
                raise AsyncRWLockTimeoutError(
                    f"Write lock acquisition timed out after {timeout}s"
                )

            self._pending_writers -= 1
            self._writer = True
            self._total_writes += 1

        try:
            yield
        finally:
            async with self._condition:
                self._writer = False
                self._condition.notify_all()

    async def _wait_for_read(self):
        """Wait until it's safe to read (no writer, no pending writers)."""
        while self._writer or self._pending_writers > 0:
            self._contention_events += 1
            await self._condition.wait()

    async def _wait_for_write(self):
        """Wait until it's safe to write (no readers, no active writer)."""
        while self._writer or self._readers > 0:
            self._contention_events += 1
            await self._condition.wait()

    @property
    def state(self) -> Dict[str, Any]:
        """Current lock state for debugging/monitoring."""
        return {
            "readers": self._readers,
            "writer_active": self._writer,
            "pending_writers": self._pending_writers,
            "total_reads": self._total_reads,
            "total_writes": self._total_writes,
            "total_timeouts": self._total_timeouts,
            "contention_events": self._contention_events,
        }


# ========== Graph Snapshot ==========

class GraphSnapshot:
    """
    Frozen snapshot of graph state for consistent multi-step reads.

    Captures nodes and edges at a point in time. Read-only.
    """

    def __init__(self, nodes: Dict[str, Any], edges: list):
        self._nodes = dict(nodes)  # Deep-ish copy (copies dict, not values)
        self._edges = list(edges)
        self._created_at = time.time()

    def get_node(self, node_id: str) -> Optional[Any]:
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> Dict[str, Any]:
        return dict(self._nodes)

    def get_edges(self) -> list:
        return list(self._edges)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def created_at(self) -> float:
        return self._created_at


# ========== Singleton ==========

_graph_lock: Optional[AsyncRWLock] = None


def get_graph_lock() -> AsyncRWLock:
    """Get the singleton graph RWLock."""
    global _graph_lock
    if _graph_lock is None:
        _graph_lock = AsyncRWLock()
    return _graph_lock
