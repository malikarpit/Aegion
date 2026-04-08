import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext
from unittest.mock import patch

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_user():
    return AuthorityContext(
        user_id="user-1",
        scopes=["read", "write"],
        role="developer",
        can_approve_t1=True
    )

@pytest.fixture
def override_auth(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides = {}

def test_ghost_text_completion_confidence(client, override_auth):
    """Test generating a simple ghost text completion with confidence check."""
    payload = {
        "file_path": "/src/main.py",
        "file_content": "def my_func",
        "cursor_position": {"line": 0, "character": 11}, # End of line
        "language_id": "python",
        "workspace_id": "ws-123"
    }
    
    headers = {
        "X-Aegion-Session": "sess-test-1",
        "X-Aegion-Intent": "ghost_text_completion",
    }
    
    response = client.post(
        "/api/v1/ghost-text/complete",
        json=payload,
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "text" in data
    assert data["confidence"] >= 0.8  # 'def' keyword should imply high confidence
    assert "Implementation of" in data["text"]

def test_ghost_text_context_injection(client, override_auth):
    """Test that context is injected into comments."""
    from unittest.mock import MagicMock, AsyncMock
    
    # Mock Graph Node
    mock_node = MagicMock()
    mock_node.node_id = "dec-123"
    mock_node.properties = {"title": "Use JWT for Auth"}
    
    with patch("app.api.v1.ghost_text._ghost_service._graph_service") as mock_service:
        mock_service.search_nodes = AsyncMock(return_value=[mock_node])
        
        payload = {
            "file_path": "/src/auth.py",
            "file_content": "def authenticate", 
            "cursor_position": {"line": 0, "character": 16},
            "language_id": "python",
            "workspace_id": "ws-123"
        }
        
        headers = {"X-Aegion-Session": "sess-test-1", "X-Aegion-Intent": "ghost_text_context"}
        
        response = client.post(
            "/api/v1/ghost-text/complete",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check if context reference was injected into the comment
        assert "# Ref: Use JWT for Auth" in data["text"]
        assert data["confidence"] > 0.8
