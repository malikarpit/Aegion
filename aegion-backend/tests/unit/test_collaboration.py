import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.core.security import Role, AuthorityContext, get_current_user
from app.models.collaboration import SessionOwnership, OwnershipStatus, OwnershipTransfer
from app.services.session_manager import GovernanceError

# Helper to create a mock user context
def mock_auth_dependency(user_id="user-123", role=Role.DEVELOPER):
    async def override():
        return AuthorityContext.from_role(user_id=user_id, role=role)
    return override

@pytest.fixture
def mock_session_manager():
    with patch("app.api.v1.collaboration.session_manager") as mock:
        yield mock

@pytest.fixture
def mock_websocket_manager():
    with patch("app.api.v1.collaboration.manager") as mock:
        mock.broadcast_to_workspace = AsyncMock()
        yield mock

@pytest.mark.asyncio
async def test_get_ownership(mock_session_manager):
    # Mock return value
    mock_ownership = SessionOwnership(
        session_id="s1",
        workspace_id="w1",
        status=OwnershipStatus.RELEASED,
        updated_at=datetime.now(timezone.utc),
        history=[]
    )
    mock_session_manager.get_ownership = AsyncMock(return_value=mock_ownership)

    # Use TestClient (but need to override dependency or mock api call)
    # Since fastAPI dependency overrides are global, we can use app.dependency_overrides
    app.dependency_overrides[get_current_user] = mock_auth_dependency()
    
    with TestClient(app) as client:
        response = client.get("/api/v1/collaboration/session/s1/ownership", headers={"X-Aegion-Session": "s1", "X-Aegion-Intent": "test"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "s1"
        assert data["status"] == "released"

@pytest.mark.asyncio
async def test_claim_ownership_success(mock_session_manager, mock_websocket_manager):
    mock_ownership = SessionOwnership(
        session_id="s1",
        workspace_id="w1",
        owner_id="user-123",
        status=OwnershipStatus.CLAIMED,
        updated_at=datetime.now(timezone.utc),
        history=[]
    )
    mock_session_manager.claim_ownership = AsyncMock(return_value=mock_ownership)
    
    app.dependency_overrides[get_current_user] = mock_auth_dependency(user_id="user-123")
    
    with TestClient(app) as client:
        response = client.post("/api/v1/collaboration/session/s1/claim", headers={"X-Aegion-Session": "s1", "X-Aegion-Intent": "test"})
        assert response.status_code == 200
        
        # Verify broadcasts
        mock_websocket_manager.broadcast_to_workspace.assert_awaited_once()
        args = mock_websocket_manager.broadcast_to_workspace.await_args
        assert args[0][0] == "w1" # workspace_id
        assert args[0][1]["type"] == "ownership.changed"

@pytest.mark.asyncio
async def test_force_claim_permission_denied(mock_session_manager):
    # Developer cannot force claim
    app.dependency_overrides[get_current_user] = mock_auth_dependency(role=Role.DEVELOPER)
    
    with TestClient(app) as client:
        response = client.post("/api/v1/collaboration/session/s1/claim?force=true", headers={"X-Aegion-Session": "s1", "X-Aegion-Intent": "test"})
        assert response.status_code == 403
        assert "requires Admin or Architect" in response.json()["detail"]

@pytest.mark.asyncio
async def test_force_claim_permission_granted(mock_session_manager, mock_websocket_manager):
    # Admin can force claim
    mock_ownership = SessionOwnership(
        session_id="s1",
        workspace_id="w1",
        owner_id="admin-1",
        status=OwnershipStatus.CLAIMED,
        updated_at=datetime.now(timezone.utc),
        history=[]
    )
    mock_session_manager.claim_ownership = AsyncMock(return_value=mock_ownership)
    
    app.dependency_overrides[get_current_user] = mock_auth_dependency(role=Role.ADMIN)
    
    with TestClient(app) as client:
        response = client.post("/api/v1/collaboration/session/s1/claim?force=true", headers={"X-Aegion-Session": "s1", "X-Aegion-Intent": "test"})
        assert response.status_code == 200
        
        # Verify manager call had force=True
        mock_session_manager.claim_ownership.assert_awaited_with("s1", "user-123", force=True)

@pytest.mark.asyncio
async def test_transfer_ownership(mock_session_manager, mock_websocket_manager):
    mock_ownership = SessionOwnership(
        session_id="s1",
        workspace_id="w1",
        owner_id="owner-1",
        status=OwnershipStatus.PENDING,
        pending_transfer_to="target-1",
        updated_at=datetime.now(timezone.utc),
        history=[]
    )
    mock_session_manager.transfer_ownership = AsyncMock(return_value=mock_ownership)
    
    app.dependency_overrides[get_current_user] = mock_auth_dependency(user_id="owner-1")
    
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/collaboration/session/s1/transfer",
            json={"target_user_id": "target-1"},
            headers={"X-Aegion-Session": "s1", "X-Aegion-Intent": "test"}
        )
        assert response.status_code == 200
        assert response.json()["pending_transfer_to"] == "target-1"
        
        mock_websocket_manager.broadcast_to_workspace.assert_awaited_once()

@pytest.mark.asyncio
async def test_release_ownership(mock_session_manager, mock_websocket_manager):
    mock_ownership = SessionOwnership(
        session_id="s1",
        workspace_id="w1",
        owner_id=None,
        status=OwnershipStatus.RELEASED,
        updated_at=datetime.now(timezone.utc),
        history=[]
    )
    mock_session_manager.release_ownership = AsyncMock(return_value=mock_ownership)
    
    app.dependency_overrides[get_current_user] = mock_auth_dependency(user_id="owner-1")
    
    with TestClient(app) as client:
        response = client.post("/api/v1/collaboration/session/s1/release", headers={"X-Aegion-Session": "s1", "X-Aegion-Intent": "test"})
        assert response.status_code == 200
        assert response.json()["status"] == "released"
        
        mock_websocket_manager.broadcast_to_workspace.assert_awaited_once()
