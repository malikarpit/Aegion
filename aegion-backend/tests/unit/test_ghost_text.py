import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext
from unittest.mock import patch, MagicMock, AsyncMock

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
    # Mock the ghost text engine to avoid needing LLM keys
    from app.services.ghost_text import GhostTextResult
    mock_result = GhostTextResult(
        text="Implementation of my_func that handles the core logic",
        model="gemini-2.0-flash",
        provider="google",
        source="llm",
        cost_usd=0.001,
        confidence=0.9,
        latency_ms=150,
    )

    with patch("app.api.v1.ghost_text.get_ghost_text") as mock_ghost:
        mock_engine = MagicMock()
        mock_engine.complete = AsyncMock(return_value=mock_result)
        mock_ghost.return_value = mock_engine

        payload = {
            "file_path": "/src/main.py",
            "file_content": "def my_func",
            "cursor_position": {"line": 0, "character": 11},
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
    assert data["confidence"] >= 0.8
    assert "Implementation of" in data["text"]

def test_ghost_text_context_injection(client, override_auth):
    """Test that context is injected into comments."""
    from app.services.ghost_text import GhostTextResult

    mock_result = GhostTextResult(
        text="# Ref: Use JWT for Auth\ndef authenticate(token: str):\n    pass",
        model="gpt-4o-mini",
        provider="openai",
        source="llm",
        cost_usd=0.002,
        confidence=0.85,
        latency_ms=200,
    )

    with patch("app.api.v1.ghost_text.get_ghost_text") as mock_ghost:
        mock_engine = MagicMock()
        mock_engine.complete = AsyncMock(return_value=mock_result)
        mock_ghost.return_value = mock_engine

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
