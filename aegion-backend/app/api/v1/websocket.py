"""
Aegion WebSocket Routes — initial implementation.

Basic WebSocket accept and message forwarding.
ConnectionManager with replay/reconnect will be added later.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict
from ...core.logging import logger

router = APIRouter(tags=["websocket"])

# Simple connection tracking
active_connections: Dict[str, WebSocket] = {}


@router.websocket("/ws/{workspace_id}")
async def websocket_endpoint(websocket: WebSocket, workspace_id: str):
    """Accept WebSocket connection for real-time updates."""
    await websocket.accept()
    active_connections[workspace_id] = websocket
    logger.info(f"WebSocket connected: {workspace_id}")

    try:
        while True:
            data = await websocket.receive_json()
            # Echo for now
            await websocket.send_json({"type": "ack", "data": data})
    except WebSocketDisconnect:
        active_connections.pop(workspace_id, None)
        logger.info(f"WebSocket disconnected: {workspace_id}")
