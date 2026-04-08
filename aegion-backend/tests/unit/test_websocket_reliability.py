
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.api.v1.websocket import manager

# Mocks for auth and DB
@pytest.fixture
def mock_auth_and_db():
    with patch("app.core.auth_config.verify_token", new_callable=AsyncMock) as mock_token, \
         patch("app.adapters.firestore.workspace_repository.FirestoreWorkspaceRepository") as mock_repo_cls:
        
        # Setup token verification
        mock_token.return_value = {"uid": "user-1", "role": "developer"}
        
        # Setup workspace membership
        mock_repo = mock_repo_cls.return_value
        mock_member = MagicMock()
        mock_member.role = "developer" # simple attribute or enum
        mock_repo.get_member = AsyncMock(return_value=mock_member)
        
        yield mock_token, mock_repo

@pytest.mark.asyncio
async def test_websocket_sequence_ids(mock_auth_and_db):
    client = TestClient(app)
    
    # reset manager state for isolation
    manager._workspace_sequences.clear()
    manager._workspace_buffers.clear()
    
    with client.websocket_connect("/api/v1/ws/w1?token=valid-token") as websocket:
        # 1. Receive initial participant list (not versioned usually, but check)
        data = websocket.receive_json()
        assert data["type"] == "participants.list"
        
        # 2. Simulate another user joining to trigger a broadcast
        # We can simulate this by calling manager.broadcast_to_workspace directly
        # or by connecting a second client (TestClient doesn't easily support concurrent WS in one thread? 
        # actually it might block. Async client is better but TestClient is sync wrapper).
        # Let's interact with manager directly to simulate external events.
        
        await manager.broadcast_to_workspace("w1", {"type": "test.event", "data": "hello"})
        
        msg = websocket.receive_json()
        assert msg["type"] == "test.event"
        assert "sequence_id" in msg
        seq_1 = msg["sequence_id"]
        # seq 1 is usually participant.joined from the connection itself
        assert seq_1 >= 2 
        
        await manager.broadcast_to_workspace("w1", {"type": "test.event", "data": "world"})
        msg = websocket.receive_json()
        seq_2 = msg["sequence_id"]
        assert seq_2 == seq_1 + 1

@pytest.mark.asyncio
async def test_websocket_replay_missed_events(mock_auth_and_db):
    client = TestClient(app)
    
    # reset manager
    manager._workspace_sequences.clear()
    manager._workspace_buffers.clear()
    
    # 1. Generate some events while "disconnected"
    await manager.broadcast_to_workspace("w1", {"type": "event.1"}) # seq 1
    await manager.broadcast_to_workspace("w1", {"type": "event.2"}) # seq 2
    await manager.broadcast_to_workspace("w1", {"type": "event.3"}) # seq 3
    
    # 2. Connect with last_event_id=1. Should receive 2 and 3.
    # Note: Connect triggers participant.joined (seq 4), which is buffered and replayed too.
    with client.websocket_connect("/api/v1/ws/w1?token=valid-token&last_event_id=1") as websocket:
        
        # First: Replayed events
        msg1 = websocket.receive_json()
        assert msg1["type"] == "event.2"
        assert msg1["sequence_id"] == 2
        
        msg2 = websocket.receive_json()
        assert msg2["type"] == "event.3"
        assert msg2["sequence_id"] == 3
        
        msg_joined = websocket.receive_json()
        assert msg_joined["type"] == "participant.joined"
        assert msg_joined["sequence_id"] == 4
        
        # Then: Participants list
        msg3 = websocket.receive_json()
        assert msg3["type"] == "participants.list"

@pytest.mark.asyncio
async def test_websocket_buffer_rotation(mock_auth_and_db):
    # Test that buffer respects max size
    from app.api.v1.websocket import MAX_BUFFER_SIZE
    
    manager._workspace_sequences.clear()
    manager._workspace_buffers.clear()
    
    workspace_id = "w1"
    
    # Fill buffer beyond max
    for i in range(MAX_BUFFER_SIZE + 10):
        await manager.broadcast_to_workspace(workspace_id, {"type": "flood", "index": i})
    
    buffer = manager._workspace_buffers[workspace_id]
    assert len(buffer) == MAX_BUFFER_SIZE
    
    # First item should be index 10 (since 0-9 dropped)
    # Sequence ID for first item in buffer:
    # 0..MAX+9 => total MAX+10. 
    # Buffer contains last MAX.
    # Seq IDs are 1-based. 1 to 100+10 = 110.
    # Buffer should have 11..110.
    
    first_msg = buffer[0]
    assert first_msg["type"] == "flood"
    # index 10 corresponds to 11th message => seq_id 11
    assert first_msg["sequence_id"] == 11 
    
    last_msg = buffer[-1]
    assert last_msg["sequence_id"] == MAX_BUFFER_SIZE + 10
