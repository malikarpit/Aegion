"""
Aegion WebSocket Endpoint.

Enables bi-directional real-time collaboration.
Used for session state synchronization and live collaboration.

Doctrine: "Collaboration is governance-aware."
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, List, Set, Optional
import json
import asyncio
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from collections import deque

from ...core.logging import logger
from ...ports.events import Event, EventCategory


router = APIRouter(prefix="/ws", tags=["websocket"])
MAX_BUFFER_SIZE = 100


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    connection_id: str
    websocket: WebSocket
    user_id: str
    workspace_id: str
    session_id: Optional[str] = None
    role: str = "viewer"
    connected_at: datetime = field(default_factory=datetime.utcnow)


class ConnectionManager:
    """Manages WebSocket connections for real-time collaboration."""
    
    def __init__(self):
        # workspace_id -> set of ConnectionInfo
        self._connections: Dict[str, Dict[str, ConnectionInfo]] = {}
        # session_id -> set of connection_ids
        self._session_connections: Dict[str, Set[str]] = {}
        
        # Reliability: Sequence IDs and Message Buffers per Workspace
        self._workspace_sequences: Dict[str, int] = {}
        self._workspace_buffers: Dict[str, deque] = {}
    
    def _get_next_sequence(self, workspace_id: str) -> int:
        """Get next monotonic sequence ID for workspace."""
        if workspace_id not in self._workspace_sequences:
            self._workspace_sequences[workspace_id] = 0
        self._workspace_sequences[workspace_id] += 1
        return self._workspace_sequences[workspace_id]
        
    def _buffer_message(self, workspace_id: str, message: dict):
        """Buffer message for replay."""
        if workspace_id not in self._workspace_buffers:
            self._workspace_buffers[workspace_id] = deque(maxlen=MAX_BUFFER_SIZE)
        self._workspace_buffers[workspace_id].append(message)

    async def connect(
        self, 
        websocket: WebSocket, 
        workspace_id: str,
        user_id: str,
        role: str = "viewer"
    ) -> ConnectionInfo:
        """Accept and register a new connection."""
        await websocket.accept()
        
        connection_id = str(uuid.uuid4())
        conn = ConnectionInfo(
            connection_id=connection_id,
            websocket=websocket,
            user_id=user_id,
            workspace_id=workspace_id,
            role=role
        )
        
        if workspace_id not in self._connections:
            self._connections[workspace_id] = {}
        self._connections[workspace_id][connection_id] = conn
        
        logger.info(
            f"WebSocket connected",
            connection_id=connection_id,
            user_id=user_id,
            workspace_id=workspace_id
        )
        
        # Notify others about new participant
        await self.broadcast_to_workspace(
            workspace_id,
            {
                "type": "participant.joined",
                "user_id": user_id,
                "role": role,
            },
            exclude_connection=connection_id
        )
        
        return conn
    
    async def disconnect(self, connection: ConnectionInfo):
        """Remove a connection."""
        workspace_id = connection.workspace_id
        connection_id = connection.connection_id
        
        if workspace_id in self._connections:
            self._connections[workspace_id].pop(connection_id, None)
            if not self._connections[workspace_id]:
                del self._connections[workspace_id]
                # Optional: cleanup buffer/sequence if empty? 
                # Better to keep them for a while for reconnects.
        
        # Remove from session tracking
        if connection.session_id:
            if connection.session_id in self._session_connections:
                self._session_connections[connection.session_id].discard(connection_id)
        
        logger.info(
            f"WebSocket disconnected",
            connection_id=connection_id,
            user_id=connection.user_id
        )
        
        # Notify others
        await self.broadcast_to_workspace(
            workspace_id,
            {
                "type": "participant.left",
                "user_id": connection.user_id,
            }
        )
    
    def join_session(self, connection: ConnectionInfo, session_id: str):
        """Register connection as participating in a session."""
        connection.session_id = session_id
        if session_id not in self._session_connections:
            self._session_connections[session_id] = set()
        self._session_connections[session_id].add(connection.connection_id)
    
    async def broadcast_to_workspace(
        self, 
        workspace_id: str, 
        message: dict,
        exclude_connection: str = None
    ):
        """Send versioned message to all connections in workspace."""
        # Add sequence ID and timestamp
        seq_id = self._get_next_sequence(workspace_id)
        message["sequence_id"] = seq_id
        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Buffer for replay
        self._buffer_message(workspace_id, message)
        
        connections = self._connections.get(workspace_id, {})
        
        for conn_id, conn in connections.items():
            if conn_id == exclude_connection:
                continue
            try:
                await conn.websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to {conn_id}: {e}")
    
    async def broadcast_to_session(
        self, 
        session_id: str, 
        message: dict,
        exclude_connection: str = None
    ):
        """Send versioned message to all connections in a session."""
        # Iterate workspaces to find which one this session belongs to?
        # A session belongs to a workspace (implicit in Aegion design).
        # We need the workspace_id to sequence it correctly within the workspace stream.
        
        # Find workspace_id from any connection in the session
        connection_ids = self._session_connections.get(session_id, set())
        if not connection_ids:
            return

        # Optimization: Just pick one valid connection to get workspace_id
        target_workspace_id = None
        for workspace_id, workspace_conns in self._connections.items():
             for conn_id in workspace_conns:
                 if conn_id in connection_ids:
                     target_workspace_id = workspace_id
                     break
             if target_workspace_id:
                 break
        
        if not target_workspace_id:
            logger.warning(f"Could not find workspace for session {session_id} broadcast")
            return

        # Sequence and buffer
        seq_id = self._get_next_sequence(target_workspace_id)
        message["sequence_id"] = seq_id
        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._buffer_message(target_workspace_id, message)

        # Broadcast
        workspace_conns = self._connections.get(target_workspace_id, {})
        for conn_id, conn in workspace_conns.items():
            if conn_id in connection_ids and conn_id != exclude_connection:
                try:
                    await conn.websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send to {conn_id}: {e}")
    
    async def send_to_user(self, workspace_id: str, user_id: str, message: dict):
        """Send message to specific user (Unversioned/System messages)."""
        # Note: We usually don't sequence unicast messages like "state.current" responses 
        # unless they are part of the critical state stream.
        # For now, let's keep them unversioned or add a special system sequence if needed.
        # Using 0 or None for sequence_id to indicate "do not order/gap-check".
        
        connections = self._connections.get(workspace_id, {})
        
        for conn in connections.values():
            if conn.user_id == user_id:
                try:
                    await conn.websocket.send_json(message)
                except Exception as e:
                    logger.debug(f"WebSocket send failed for user {user_id}: {e}")
    
    async def replay_missed_events(self, connection: ConnectionInfo, last_event_id: int):
        """Replay messages with sequence_id > last_event_id."""
        workspace_id = connection.workspace_id
        buffer = self._workspace_buffers.get(workspace_id)
        if not buffer:
            return
            
        logger.info(f"Replaying events for {connection.user_id} from {last_event_id}")
        
        for msg in buffer:
            msg_seq = msg.get("sequence_id")
            if msg_seq is not None and msg_seq > last_event_id:
                try:
                    await connection.websocket.send_json(msg)
                except Exception as e:
                    logger.error(f"Failed to replay to {connection.connection_id}: {e}")

    def get_participants(self, workspace_id: str) -> List[dict]:
        """Get list of current participants in workspace."""
        connections = self._connections.get(workspace_id, {})
        return [
            {
                "user_id": conn.user_id,
                "role": conn.role,
                "session_id": conn.session_id,
                "connected_at": conn.connected_at.isoformat()
            }
            for conn in connections.values()
        ]


# Singleton connection manager
manager = ConnectionManager()


@router.websocket("/{workspace_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    workspace_id: str,
    ticket: Optional[str] = Query(None),
    token: Optional[str] = Query(None),  # Deprecated: backwards compat during migration
    last_event_id: Optional[int] = Query(None)
):
    """
    WebSocket endpoint for real-time collaboration.
    
    Authentication (Phase 89):
    - Primary: `ticket` query param (short-lived, one-time use via /auth/ws-ticket).
    - Fallback: `token` query param (deprecated — will be removed after migration).
    
    Message Types (Client -> Server):
    - join_session: Join a governance session
    - leave_session: Leave current session
    - cursor_update: Share cursor position
    - state_sync: Request state synchronization
    
    Message Types (Server -> Client):
    - participant.joined: New participant joined
    - participant.left: Participant left
    - cursor.updated: Cursor position from another user
    - state.changed: Session state changed
    - proposal.updated: Proposal was modified
    """
    user_id = None
    role = "viewer"

    # Phase 89: Prefer ticket-exchange (secure)
    if ticket:
        from .auth import consume_ws_ticket
        user_id = consume_ws_ticket(ticket)
        if not user_id:
            await websocket.close(code=4001, reason="Unauthorized: invalid or expired ticket")
            return
    elif token:
        # Deprecated fallback — log warning for migration tracking
        logger.warning(
            "WebSocket connected with deprecated token param — migrate to ticket-exchange",
            workspace_id=workspace_id,
        )
        from ...core.auth_config import verify_token
        try:
            claims = await verify_token(token)
        except Exception:
            claims = None
        if not claims or "uid" not in claims:
            await websocket.close(code=4001, reason="Unauthorized: invalid token")
            return
        user_id = claims["uid"]
        role = claims.get("role", "viewer")
    else:
        await websocket.close(code=4001, reason="Unauthorized: no ticket or token provided")
        return

    # Verify workspace membership (mirrors SSE gate in stream.py)
    from ...adapters.firestore.workspace_repository import FirestoreWorkspaceRepository
    repo = FirestoreWorkspaceRepository()
    member = await repo.get_member(workspace_id, user_id)
    if not member:
        logger.warning(
            f"Unauthorized WebSocket attempt for workspace {workspace_id}",
            user_id=user_id,
        )
        await websocket.close(code=4003, reason="Not a member of this workspace")
        return
    # Use workspace role instead of token role for proper authorization
    role = member.role.value if hasattr(member.role, "value") else member.role

    connection = await manager.connect(websocket, workspace_id, user_id, role)
    
    # Replay missed events if requested
    if last_event_id is not None:
        await manager.replay_missed_events(connection, last_event_id)
    
    # Send current participants list
    await websocket.send_json({
        "type": "participants.list",
        "participants": manager.get_participants(workspace_id)
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "join_session":
                session_id = data.get("session_id")
                if session_id:
                    manager.join_session(connection, session_id)
                    await manager.broadcast_to_session(
                        session_id,
                        {
                            "type": "session.participant_joined",
                            "user_id": user_id,
                            "session_id": session_id
                        }
                    )
            
            elif msg_type == "cursor_update":
                # Broadcast cursor position to others in workspace
                await manager.broadcast_to_workspace(
                    workspace_id,
                    {
                        "type": "cursor.updated",
                        "user_id": user_id,
                        "position": data.get("position"),
                        "file": data.get("file")
                    },
                    exclude_connection=connection.connection_id
                )
            
            elif msg_type == "state_sync":
                # Request state sync
                await websocket.send_json({
                    "type": "state.current",
                    "session_id": connection.session_id,
                    "participants": manager.get_participants(workspace_id)
                })
            
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            
            else:
                # Echo unknown messages for debugging
                logger.debug(f"Unknown message type: {msg_type}")
    
    except WebSocketDisconnect:
        await manager.disconnect(connection)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(connection)
