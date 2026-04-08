
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone
from app.main import app
from app.core.security import get_current_user, AuthorityContext, Role
from app.models.workspace import WorkspaceMember, WorkspaceRole

@pytest.fixture
def client():
    return TestClient(app)

def test_stream_access_allowed(client):
    """Test that a member can access the event stream."""
    
    # Mock Auth
    mock_user = AuthorityContext(user_id="user-1", role=Role.DEVELOPER)
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    with patch("app.adapters.firestore.workspace_repository.FirestoreWorkspaceRepository") as MockRepo:
        mock_repo_instance = MockRepo.return_value
        
        # Mock member check returning a member
        mock_member = WorkspaceMember(
            user_id="user-1",
            workspace_id="ws-1",
            role=WorkspaceRole.DEVELOPER,
            joined_at=datetime.now(timezone.utc)
        )
        mock_repo_instance.get_member = AsyncMock(return_value=mock_member)
        
        # Mock subscribe_workspace to provide a controlled queue
        with patch("app.api.v1.stream.subscribe_workspace") as mock_subscribe:
            mock_queue = MagicMock()
            
            # Create a dummy event that simulates EventMessage
            mock_event = MagicMock()
            mock_event.event_type = "test.event"
            mock_event.event_id = "evt-1"
            mock_event.payload = {"foo": "bar"}
            mock_event.timestamp = datetime.now(timezone.utc)
            
            # mock_queue.get() is async, so return_value should be the result of await
            # Use side_effect to return one event then raise exception to break loop
            import asyncio
            mock_queue.get = AsyncMock(side_effect=[mock_event, asyncio.CancelledError]) 
            mock_subscribe.return_value = ("sub-1", mock_queue)
            
            
            headers = {
                "X-Aegion-Session": "sess-sec-1",
                "X-Aegion-Intent": "stream.connect"
            }
            
            with client.stream("GET", "/api/v1/events/stream/ws-1", headers=headers) as response:
                assert response.status_code == 200
                # Consume one chunk to ensure generator runs
                for line in response.iter_lines():
                    break
            
            # Verify get_member was called correctly
            mock_repo_instance.get_member.assert_called_with("ws-1", "user-1")

    app.dependency_overrides = {}

def test_stream_access_denied(client):
    """Test that a non-member is denied access."""
    
    # Mock Auth
    mock_user = AuthorityContext(user_id="user-intruder", role=Role.DEVELOPER)
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    with patch("app.adapters.firestore.workspace_repository.FirestoreWorkspaceRepository") as MockRepo:
        mock_repo_instance = MockRepo.return_value
        
        # Mock member check returning None
        mock_repo_instance.get_member = AsyncMock(return_value=None)
        
        headers = {
            "X-Aegion-Session": "sess-intruder-1",
            "X-Aegion-Intent": "stream.connect"
        }
        
        response = client.get("/api/v1/events/stream/ws-1", headers=headers)
        assert response.status_code == 403
        assert "Not a member" in response.json()["detail"]
        
        # Verify get_member was called
        mock_repo_instance.get_member.assert_called_with("ws-1", "user-intruder")
    
    app.dependency_overrides = {}
