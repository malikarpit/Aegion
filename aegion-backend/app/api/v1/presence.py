"""
Aegion API v1 - Presence Endpoints.

REST endpoints for presence management and collaboration awareness.
WebSocket is in websocket.py; these endpoints complement it with
HTTP-based presence queries and heartbeat updates.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timezone

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger
from ...models.presence import UserPresence, PresenceStatus
from ...services.durable_store import JsonFileStore


router = APIRouter(prefix="/presence", tags=["presence"])


# ========== Durable Store ==========
_presence_store = JsonFileStore(".aegion_data/presence.json", UserPresence, "user_id")


# ========== Request/Response Models ==========


class HeartbeatRequest(BaseModel):
    status: Optional[str] = "online"
    active_file: Optional[str] = None
    cursor_line: Optional[int] = None
    session_id: Optional[str] = None


class PresenceResponse(BaseModel):
    user_id: str
    workspace_id: str
    session_id: Optional[str] = None
    status: str
    active_file: Optional[str] = None
    cursor_line: Optional[int] = None
    connected_at: str
    last_heartbeat: str


class WorkspacePresenceResponse(BaseModel):
    workspace_id: str
    online_count: int
    users: List[PresenceResponse]


# ========== Helpers ==========


def _to_response(p: UserPresence) -> PresenceResponse:
    return PresenceResponse(
        user_id=p.user_id,
        workspace_id=p.workspace_id,
        session_id=p.session_id,
        status=p.status.value,
        active_file=p.active_file,
        cursor_line=p.cursor_line,
        connected_at=p.connected_at.isoformat(),
        last_heartbeat=p.last_heartbeat.isoformat(),
    )


# ========== Endpoints ==========


@router.post("/heartbeat", response_model=PresenceResponse)
async def send_heartbeat(
    request: HeartbeatRequest,
    user: AuthorityContext = Depends(get_current_user),
    x_workspace_id: str = Header(default="default"),
):
    """Send a presence heartbeat (call periodically to stay online)."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    now = datetime.now(timezone.utc)
    uid = user.user_id

    existing = await _presence_store.get(uid)
    if existing:
        existing.status = PresenceStatus(request.status) if request.status else PresenceStatus.ONLINE
        existing.active_file = request.active_file
        existing.cursor_line = request.cursor_line
        existing.last_heartbeat = now
        if request.session_id:
            existing.session_id = request.session_id
        await _presence_store.save(existing)
    else:
        entry = UserPresence(
            user_id=uid,
            workspace_id=x_workspace_id,
            session_id=request.session_id,
            status=PresenceStatus(request.status) if request.status else PresenceStatus.ONLINE,
            active_file=request.active_file,
            cursor_line=request.cursor_line,
            connected_at=now,
            last_heartbeat=now,
        )
        await _presence_store.save(entry)

    saved = await _presence_store.get(uid)
    return _to_response(saved)


@router.get("", response_model=WorkspacePresenceResponse)
async def get_workspace_presence(
    user: AuthorityContext = Depends(get_current_user),
    x_workspace_id: str = Header(default="default"),
):
    """Get all users present in the workspace."""
    all_presence = await _presence_store.list_all()
    users = [p for p in all_presence if p.workspace_id == x_workspace_id]
    online = [u for u in users if u.status != PresenceStatus.OFFLINE]

    return WorkspacePresenceResponse(
        workspace_id=x_workspace_id,
        online_count=len(online),
        users=[_to_response(u) for u in users],
    )


@router.get("/{user_id}", response_model=PresenceResponse)
async def get_user_presence(
    user_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get a specific user's presence."""
    presence = await _presence_store.get(user_id)
    if not presence:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found in presence")
    return _to_response(presence)


@router.post("/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_presence(
    user: AuthorityContext = Depends(get_current_user),
):
    """Mark current user as offline and remove from presence."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    uid = user.user_id
    existing = await _presence_store.get(uid)
    if existing:
        await _presence_store.delete(uid)
    logger.info(f"User {uid} left presence")


# W5.2: Active user tracking with stale heartbeat cleanup
PRESENCE_TTL_SECONDS = 120  # Users with heartbeat older than 2 minutes are stale


@router.get("/active/users", response_model=WorkspacePresenceResponse)
async def get_active_users(
    user: AuthorityContext = Depends(get_current_user),
    x_workspace_id: str = Header(default="default"),
):
    """
    Get actively connected users (W5.2).
    
    Only returns users whose last heartbeat is within the TTL window.
    Stale users are automatically excluded.
    """
    now = datetime.now(timezone.utc)
    all_presence = await _presence_store.list_all()
    
    active_users = []
    for p in all_presence:
        if p.workspace_id != x_workspace_id:
            continue
        if p.status == PresenceStatus.OFFLINE:
            continue
        age = (now - p.last_heartbeat).total_seconds()
        if age <= PRESENCE_TTL_SECONDS:
            active_users.append(p)

    return WorkspacePresenceResponse(
        workspace_id=x_workspace_id,
        online_count=len(active_users),
        users=[_to_response(u) for u in active_users],
    )


@router.post("/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_stale_presence(
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Remove stale presence entries (W5.2).
    
    Marks users as offline and removes entries where the last heartbeat
    is older than the TTL. Returns count of cleaned entries.
    """
    now = datetime.now(timezone.utc)
    all_presence = await _presence_store.list_all()
    
    cleaned = 0
    for p in all_presence:
        age = (now - p.last_heartbeat).total_seconds()
        if age > PRESENCE_TTL_SECONDS:
            await _presence_store.delete(p.user_id)
            cleaned += 1
            logger.debug(f"Cleaned stale presence: {p.user_id} (age: {age:.0f}s)")

    if cleaned:
        logger.info(f"Presence cleanup: removed {cleaned} stale entries")
    
    return {"cleaned": cleaned, "remaining": len(all_presence) - cleaned}

