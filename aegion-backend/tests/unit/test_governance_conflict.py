
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.services.governance_conflict import conflict_service
from app.api.v1.websocket import manager

# Mock auth dependency
def mock_auth_dependency(user_id="user-1"):
    async def override():
        from app.core.security import AuthorityContext, Role
        return AuthorityContext.from_role(user_id=user_id, role=Role.DEVELOPER)
    return override

@pytest.fixture
def mock_websocket_manager():
    original_broadcast = manager.broadcast_to_workspace
    manager.broadcast_to_workspace = AsyncMock()
    yield manager
    manager.broadcast_to_workspace = original_broadcast

@pytest.mark.asyncio
async def test_detect_conflicts_violation(mock_websocket_manager):
    # Setup
    workspace_id = "w1"
    file_path = "app/controllers/user_controller.py"
    # Content with forbidden import
    content = "import sqlalchemy\n\ndef get_user(): pass"
    
    # Execute
    conflicts = await conflict_service.detect_conflicts(workspace_id, file_path, content)
    
    # Verify
    assert len(conflicts) == 1
    assert conflicts[0].rule_id == "r1"
    assert conflicts[0].severity == "high"
    assert "sqlalchemy" in conflicts[0].message
    
    # Verify broadcast
    mock_websocket_manager.broadcast_to_workspace.assert_awaited_once()
    args = mock_websocket_manager.broadcast_to_workspace.await_args
    assert args[0][0] == workspace_id
    event = args[0][1]
    assert event["type"] == "conflict.detected"
    assert event["rule_id"] == "r1"

@pytest.mark.asyncio
async def test_detect_conflicts_clean():
    # Setup
    workspace_id = "w1"
    file_path = "app/domain/user.py"
    content = "class User: pass"
    
    # Execute
    conflicts = await conflict_service.detect_conflicts(workspace_id, file_path, content)
    
    # Verify
    assert len(conflicts) == 0

@pytest.mark.asyncio
async def test_api_scan_endpoint(mock_websocket_manager):
    # Setup API client with auth mock
    from app.core.security import get_current_user
    app.dependency_overrides[get_current_user] = mock_auth_dependency()
    
    client = TestClient(app)
    
    payload = {
        "workspace_id": "w1",
        "file_path": "app/bad_file.py",
        "content": "from app.infrastructure.database import db"
    }
    
    # Execute
    headers = {
        "X-Aegion-Session": "test-session",
        "X-Aegion-Intent": "test-scan"
    }
    response = client.post("/api/v1/governance/scan", json=payload, headers=headers)
    
    # Verify
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["rule_id"] == "r1"
    
    # Cleanup
    app.dependency_overrides = {}
