"""
Aegion SSE Streaming Endpoint.

Server-Sent Events for real-time updates.
Enables live collaboration and proposal tracking.

Doctrine: "State flows from source of truth."
- Per-subscriber fan-out queues (multiple clients per workspace)
- Event bus → SSE bridge (governance events auto-relayed)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, Dict
import asyncio
import json
import uuid as _uuid
from datetime import datetime, timezone

from ...core.security import get_current_user, AuthorityContext
from ...core.logging import logger
from ...ports.events import EventMessage, Event, EventTypes


router = APIRouter(prefix="/events", tags=["events"])


# ========== Per-Subscriber Fan-Out ==========
# Each SSE client gets its own queue, so all subscribers receive every event.

_workspace_subscribers: Dict[str, Dict[str, asyncio.Queue]] = {}
# workspace_id → { subscriber_id → Queue }


def subscribe_workspace(workspace_id: str) -> tuple[str, asyncio.Queue]:
    """Register a new subscriber, returns (subscriber_id, queue)."""
    subscriber_id = str(_uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    if workspace_id not in _workspace_subscribers:
        _workspace_subscribers[workspace_id] = {}
    _workspace_subscribers[workspace_id][subscriber_id] = queue

    logger.debug(
        f"SSE subscriber {subscriber_id} registered for workspace {workspace_id}"
    )
    return subscriber_id, queue


def unsubscribe_workspace(workspace_id: str, subscriber_id: str) -> None:
    """Remove subscriber on disconnect."""
    subs = _workspace_subscribers.get(workspace_id, {})
    subs.pop(subscriber_id, None)
    if not subs:
        _workspace_subscribers.pop(workspace_id, None)

    logger.debug(
        f"SSE subscriber {subscriber_id} unregistered from workspace {workspace_id}"
    )


async def broadcast_to_workspace(workspace_id: str, event: EventMessage) -> None:
    """
    Fan-out: deliver event to ALL subscribers on this workspace.

    If a subscriber's queue is full, the oldest event is dropped
    to prevent backpressure from one slow client blocking others.
    """
    subs = _workspace_subscribers.get(workspace_id, {})
    for sub_id, queue in subs.items():
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # Drop oldest event to prevent backpressure
            try:
                queue.get_nowait()
                queue.put_nowait(event)
            except asyncio.QueueEmpty:
                pass


# ========== Event Bus → SSE Bridge ==========

_bridge_initialized = False


async def setup_event_bridge() -> None:
    """
    Subscribe to governance events on the InProcessEventBus and
    relay them to SSE subscribers.

    Called once at application startup.
    """
    global _bridge_initialized
    if _bridge_initialized:
        return
    _bridge_initialized = True

    from ...adapters.inprocess.event_bus import get_event_bus

    bus = get_event_bus()

    governance_events = [
        EventTypes.DECISION_PROPOSED,
        EventTypes.DECISION_APPROVED,
        EventTypes.DECISION_REJECTED,
        EventTypes.DECISION_SUPERSEDED,
        EventTypes.SESSION_STARTED,
        EventTypes.SESSION_CLOSED,
        EventTypes.FREEZE_ACTIVATED,
        EventTypes.FREEZE_DEACTIVATED,
        EventTypes.POLICY_UPDATED,
    ]

    for event_type in governance_events:
        await bus.subscribe(event_type, _relay_to_sse)

    logger.info(
        f"Event bus → SSE bridge initialized ({len(governance_events)} event types)"
    )


async def _relay_to_sse(event: Event) -> None:
    """Forward event bus event to all SSE subscribers in the workspace."""
    if event.workspace_id:
        await broadcast_to_workspace(event.workspace_id, event)


# ========== SSE Generator ==========


async def event_generator(
    workspace_id: str,
    user: AuthorityContext,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE events for workspace.

    SSE Format:
    data: {"type": "event_type", "payload": {...}}

    """
    subscriber_id, queue = subscribe_workspace(workspace_id)

    try:
        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'workspace_id': workspace_id, 'subscriber_id': subscriber_id})}\n\n"

        # Keep-alive counter
        keepalive_interval = 30  # seconds

        while True:
            try:
                # Wait for event with timeout for keepalive
                event = await asyncio.wait_for(
                    queue.get(),
                    timeout=keepalive_interval,
                )

                # Format as SSE
                event_data = {
                    "type": event.event_type,
                    "event_id": event.event_id,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat(),
                }
                yield f"data: {json.dumps(event_data)}\n\n"

            except asyncio.TimeoutError:
                # Send keepalive
                yield f": keepalive {datetime.now(timezone.utc).isoformat()}\n\n"
    finally:
        # Cleanup on disconnect
        unsubscribe_workspace(workspace_id, subscriber_id)


@router.get("/stream/{workspace_id}")
async def stream_events(
    workspace_id: str,
    user: AuthorityContext = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream real-time events for workspace.

    Uses Server-Sent Events (SSE) for efficient push updates.

    Events include:
    - proposal.created
    - proposal.updated
    - proposal.review_submitted
    - proposal.approved
    - proposal.rejected
    - workspace.member_joined
    - workspace.member_left
    - decision.created
    - session.started
    - session.closed
    """
    # Verify user has access to workspace
    from ...adapters.firestore.workspace_repository import FirestoreWorkspaceRepository

    repo = FirestoreWorkspaceRepository()

    member = await repo.get_member(workspace_id, user.user_id)
    if not member:
        logger.warning(
            f"Unauthorized SSE access attempt for workspace {workspace_id}",
            user_id=user.user_id,
        )
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    logger.info(
        f"SSE connection opened for workspace {workspace_id}",
        user_id=user.user_id,
    )

    return StreamingResponse(
        event_generator(workspace_id, user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/broadcast/{workspace_id}")
async def broadcast_event(
    workspace_id: str,
    event_type: str = Query(...),
    payload: dict = None,
    user: AuthorityContext = Depends(get_current_user),
) -> dict:
    """
    Broadcast event to workspace (internal use).

    For testing and internal services.
    """
    from ...services.archon import get_archon, GovernanceError

    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    event = EventMessage(
        event_id=str(_uuid.uuid4()),
        event_type=event_type,
        payload=payload or {},
        metadata={"broadcaster": user.user_id},
        timestamp=datetime.now(timezone.utc),
    )

    await broadcast_to_workspace(workspace_id, event)

    return {
        "status": "broadcast",
        "event_id": event.event_id,
        "workspace_id": workspace_id,
    }
