"""
Cancellation Token — Phase 105: Interruptible AI.

Provides cooperative cancellation for long-running council operations.
The SSE stream, WebSocket handler, or HTTP request handler creates a
CancellationToken and passes it into the engine. Each pipeline stage
checks token.is_cancelled before proceeding.

Usage:
    token = CancellationToken()

    # Pass to council engine
    result = await engine.consult(workspace_id, query, council_type, context={"_cancel_token": token})

    # Cancel from the outside (e.g., user disconnects)
    token.cancel("User disconnected")

    # Inside pipeline stages:
    token.check()  # Raises CancelledException if cancelled
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional


class CancelledException(Exception):
    """Raised when an operation is cancelled via CancellationToken."""

    def __init__(self, reason: str = "Operation cancelled") -> None:
        self.reason = reason
        super().__init__(reason)


class CancellationToken:
    """
    Cooperative cancellation token for interruptible AI operations.

    Thread-safe and async-safe. Multiple coroutines can check the same token.
    """

    def __init__(self, timeout_seconds: Optional[float] = None) -> None:
        self._cancelled = False
        self._reason: str = ""
        self._cancel_time: Optional[float] = None
        self._created_at = time.monotonic()
        self._timeout = timeout_seconds

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        if self._cancelled:
            return True
        # Check timeout
        if self._timeout and (time.monotonic() - self._created_at) > self._timeout:
            self._cancelled = True
            self._reason = f"Timeout after {self._timeout}s"
            self._cancel_time = time.monotonic()
            return True
        return False

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._created_at

    def cancel(self, reason: str = "Cancelled") -> None:
        """Request cancellation. Idempotent — safe to call multiple times."""
        if not self._cancelled:
            self._cancelled = True
            self._reason = reason
            self._cancel_time = time.monotonic()

    def check(self) -> None:
        """
        Check if cancelled, raise CancelledException if so.

        Call this at the beginning of each pipeline stage.
        """
        if self.is_cancelled:
            raise CancelledException(self._reason)

    async def sleep_or_cancel(self, seconds: float) -> None:
        """Sleep for the given duration, but wake up early if cancelled."""
        interval = 0.1
        elapsed = 0.0
        while elapsed < seconds:
            if self.is_cancelled:
                raise CancelledException(self._reason)
            await asyncio.sleep(min(interval, seconds - elapsed))
            elapsed += interval

    def child(self) -> "CancellationToken":
        """
        Create a child token that is cancelled when the parent is cancelled.

        Useful for sub-council spawning — cancel the parent to cascade.
        """
        child = _ChildCancellationToken(self)
        return child


class _ChildCancellationToken(CancellationToken):
    """Child token that inherits cancellation from parent."""

    def __init__(self, parent: CancellationToken) -> None:
        super().__init__()
        self._parent = parent

    @property
    def is_cancelled(self) -> bool:
        return super().is_cancelled or self._parent.is_cancelled

    @property
    def reason(self) -> str:
        if self._cancelled:
            return self._reason
        if self._parent.is_cancelled:
            return f"Parent cancelled: {self._parent.reason}"
        return ""
