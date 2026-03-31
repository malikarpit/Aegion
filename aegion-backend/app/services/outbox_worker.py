"""
Aegion Outbox Worker (P2-019).

Background task that periodically drains the transactional outbox,
publishing pending events through the active EventBusPort.

Registered at application startup via lifespan hooks.
"""

import asyncio
from typing import Optional

from ..core.logging import logger


class OutboxWorker:
    """
    Polls the transactional outbox at a fixed interval and relays pending
    events to the event bus.
    """

    def __init__(
        self,
        outbox,
        poll_interval_seconds: float = 5.0,
    ):
        """
        Args:
            outbox: A TransactionalOutboxPort implementation (e.g. FirestoreOutbox)
            poll_interval_seconds: How often to poll for pending events
        """
        self._outbox = outbox
        self._interval = poll_interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the background relay loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="outbox-worker")
        logger.info(
            f"OutboxWorker started (poll every {self._interval}s)",
        )

    async def stop(self) -> None:
        """Gracefully stop the worker."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("OutboxWorker stopped")

    async def _run(self) -> None:
        """Main loop: poll → publish → sleep → repeat."""
        while self._running:
            try:
                published = await self._outbox.process_pending()
                if published > 0:
                    logger.debug(
                        f"OutboxWorker: relayed {published} events",
                    )
            except Exception as e:
                logger.error(f"OutboxWorker error: {e}")

            await asyncio.sleep(self._interval)
