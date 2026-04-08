"""
Test Checkpoint & Rollback (Phase 29 - AG-011).

Tests for checkpoint CRUD, rollback lifecycle, and edge cases.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext


@pytest.fixture
def client():
    """Create test client with mocked auth."""
    mock_user = AuthorityContext(
        user_id="test-user-checkpoints",
        role="developer",
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    c = TestClient(app)
    c.headers.update({
        "X-Aegion-Session": "test-session-cp",
        "X-Aegion-Intent": "checkpoint_management",
    })
    yield c
    app.dependency_overrides.clear()


def test_create_checkpoint(client):
    """Test creating a checkpoint."""
    response = client.post(
        "/api/v1/checkpoints",
        json={
            "session_id": "sess-cp-1",
            "label": "Before refactor",
            "reason": "manual",
            "state_snapshot": {"decisions": 3, "evidence": 5},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["label"] == "Before refactor"
    assert data["reason"] == "manual"
    assert data["status"] == "active"
    assert data["state_key_count"] == 2
    assert data["checkpoint_id"]


def test_create_checkpoint_default_label(client):
    """Test creating a checkpoint with auto-generated label."""
    response = client.post(
        "/api/v1/checkpoints",
        json={"session_id": "sess-cp-2"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["label"].startswith("Checkpoint ")
    assert data["status"] == "active"


def test_list_checkpoints(client):
    """Test listing checkpoints."""
    # Create two checkpoints
    client.post(
        "/api/v1/checkpoints",
        json={"session_id": "sess-list", "label": "CP-A"},
    )
    client.post(
        "/api/v1/checkpoints",
        json={"session_id": "sess-list", "label": "CP-B"},
    )

    response = client.get("/api/v1/checkpoints?session_id=sess-list")
    assert response.status_code == 200
    cps = response.json()
    assert len(cps) >= 2

    # Newest first
    labels = [c["label"] for c in cps]
    assert labels.index("CP-B") < labels.index("CP-A")


def test_list_checkpoints_filter_by_session(client):
    """Test filtering checkpoints by session."""
    client.post("/api/v1/checkpoints", json={"session_id": "sess-filter-A"})
    client.post("/api/v1/checkpoints", json={"session_id": "sess-filter-B"})

    response = client.get("/api/v1/checkpoints?session_id=sess-filter-A")
    cps = response.json()
    for c in cps:
        assert c["session_id"] == "sess-filter-A"


def test_get_checkpoint(client):
    """Test getting a specific checkpoint."""
    create_resp = client.post(
        "/api/v1/checkpoints",
        json={"session_id": "sess-get", "label": "Fetch me"},
    )
    cp_id = create_resp.json()["checkpoint_id"]

    response = client.get(f"/api/v1/checkpoints/{cp_id}")
    assert response.status_code == 200
    assert response.json()["label"] == "Fetch me"


def test_get_checkpoint_not_found(client):
    """Test 404 for missing checkpoint."""
    response = client.get("/api/v1/checkpoints/nonexistent-id")
    assert response.status_code == 404


def test_rollback_to_checkpoint(client):
    """Test rolling back to a checkpoint."""
    create_resp = client.post(
        "/api/v1/checkpoints",
        json={
            "session_id": "sess-rollback",
            "label": "Stable state",
            "state_snapshot": {"config": "v1", "modules": 4},
        },
    )
    cp_id = create_resp.json()["checkpoint_id"]

    response = client.post(f"/api/v1/checkpoints/{cp_id}/rollback")
    assert response.status_code == 200
    result = response.json()
    assert result["checkpoint_id"] == cp_id
    assert result["previous_state_keys"] == 2
    assert "Stable state" in result["message"]

    # Verify checkpoint is now marked as rolled_back
    get_resp = client.get(f"/api/v1/checkpoints/{cp_id}")
    assert get_resp.json()["status"] == "rolled_back"
    assert get_resp.json()["rolled_back_at"] is not None


def test_rollback_already_rolled_back(client):
    """Test that double rollback fails."""
    create_resp = client.post(
        "/api/v1/checkpoints",
        json={"session_id": "sess-double", "state_snapshot": {"x": 1}},
    )
    cp_id = create_resp.json()["checkpoint_id"]

    # First rollback
    client.post(f"/api/v1/checkpoints/{cp_id}/rollback")

    # Second rollback should fail
    response = client.post(f"/api/v1/checkpoints/{cp_id}/rollback")
    assert response.status_code == 400


def test_rollback_not_found(client):
    """Test rollback for nonexistent checkpoint."""
    response = client.post("/api/v1/checkpoints/fake-id/rollback")
    assert response.status_code == 404


def test_delete_checkpoint(client):
    """Test deleting a checkpoint."""
    create_resp = client.post(
        "/api/v1/checkpoints",
        json={"session_id": "sess-del", "label": "Delete me"},
    )
    cp_id = create_resp.json()["checkpoint_id"]

    response = client.delete(f"/api/v1/checkpoints/{cp_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_resp = client.get(f"/api/v1/checkpoints/{cp_id}")
    assert get_resp.status_code == 404


def test_delete_checkpoint_not_found(client):
    """Test deleting a nonexistent checkpoint."""
    response = client.delete("/api/v1/checkpoints/fake-id")
    assert response.status_code == 404
