"""
Test Collaboration Presence (Phase 32 - AG-014).

Tests for heartbeat, workspace presence, user presence,
multi-user attribution, and leave/disconnect.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext


def _make_client(user_id: str, workspace_id: str = "ws-1"):
    """Create a test client with specific user."""
    mock_user = AuthorityContext(user_id=user_id, role="developer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    c = TestClient(app)
    c.headers.update({
        "X-Aegion-Session": "test-session-presence",
        "X-Aegion-Intent": "presence",
        "X-Workspace-Id": workspace_id,
    })
    return c


@pytest.fixture
def client():
    c = _make_client("user-alpha")
    yield c
    app.dependency_overrides.clear()


# ========== Heartbeat Tests ==========


def test_heartbeat_creates_presence(client):
    """Test that heartbeat creates a presence entry."""
    response = client.post("/api/v1/presence/heartbeat", json={
        "status": "online",
        "active_file": "src/main.py",
        "cursor_line": 42,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user-alpha"
    assert data["status"] == "online"
    assert data["active_file"] == "src/main.py"
    assert data["cursor_line"] == 42


def test_heartbeat_updates_presence(client):
    """Test that subsequent heartbeats update the existing presence."""
    client.post("/api/v1/presence/heartbeat", json={"active_file": "file1.py"})
    response = client.post("/api/v1/presence/heartbeat", json={
        "active_file": "file2.py",
        "cursor_line": 10,
    })
    assert response.status_code == 200
    assert response.json()["active_file"] == "file2.py"


def test_heartbeat_status_away(client):
    """Test setting status to away."""
    response = client.post("/api/v1/presence/heartbeat", json={"status": "away"})
    assert response.json()["status"] == "away"


# ========== Workspace Presence Tests ==========


def test_workspace_presence_empty(client):
    """Test workspace presence when empty."""
    # Use a unique workspace
    c = _make_client("user-empty", "ws-empty")
    response = c.get("/api/v1/presence")
    assert response.status_code == 200
    data = response.json()
    assert data["online_count"] == 0
    assert len(data["users"]) == 0


def test_workspace_presence_with_users(client):
    """Test workspace presence with multiple users."""
    ws = "ws-multi"
    
    # User 1
    mock_user1 = AuthorityContext(user_id="user-1", role="developer")
    app.dependency_overrides[get_current_user] = lambda: mock_user1
    client.post("/api/v1/presence/heartbeat", headers={"X-Workspace-Id": ws}, json={"active_file": "a.py"})

    # User 2
    mock_user2 = AuthorityContext(user_id="user-2", role="developer")
    app.dependency_overrides[get_current_user] = lambda: mock_user2
    client.post("/api/v1/presence/heartbeat", headers={"X-Workspace-Id": ws}, json={"active_file": "b.py"})

    # Check presence (as User 2)
    response = client.get("/api/v1/presence", headers={"X-Workspace-Id": ws})
    assert response.status_code == 200
    data = response.json()
    assert data["workspace_id"] == ws
    assert data["online_count"] >= 2
    user_ids = [u["user_id"] for u in data["users"]]
    assert "user-1" in user_ids
    assert "user-2" in user_ids


# ========== User Presence Tests ==========


def test_get_user_presence(client):
    """Test getting a specific user's presence."""
    client.post("/api/v1/presence/heartbeat", json={"active_file": "test.py"})
    response = client.get("/api/v1/presence/user-alpha")
    assert response.status_code == 200
    assert response.json()["active_file"] == "test.py"


def test_get_user_not_found(client):
    """Test 404 for missing user."""
    response = client.get("/api/v1/presence/nonexistent-user")
    assert response.status_code == 404


# ========== Leave Tests ==========


def test_leave_presence(client):
    """Test leaving presence."""
    client.post("/api/v1/presence/heartbeat", json={})
    response = client.post("/api/v1/presence/leave")
    assert response.status_code == 204

    # User should be gone
    assert client.get("/api/v1/presence/user-alpha").status_code == 404


def test_leave_without_presence(client):
    """Test leaving when not present (should not error)."""
    response = client.post("/api/v1/presence/leave")
    assert response.status_code == 204


# ========== Multi-user Attribution Tests ==========


def test_session_attribution():
    """Test that presence tracks session attribution."""
    c = _make_client("user-session-test", "ws-attr")
    c.post("/api/v1/presence/heartbeat", json={
        "session_id": "session-abc",
        "active_file": "main.ts",
    })
    response = c.get("/api/v1/presence/user-session-test")
    assert response.json()["session_id"] == "session-abc"
    app.dependency_overrides.clear()
