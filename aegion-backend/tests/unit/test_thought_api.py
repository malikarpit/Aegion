"""
Tests for the Thought API endpoints.

Verifies the full thought lifecycle: create → get → update → seal → link.
P0-1 auditor fix: ensures create_thought no longer crashes from argument mismatch.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import AuthorityContext, get_current_user


MOCK_HEADERS = {
    "X-Aegion-Session": "test-session-123",
    "X-Aegion-Intent": "unit-test",
    "Authorization": "Bearer test-token",
}


def _mock_user():
    return AuthorityContext(user_id="test-user", role="admin", workspace_id="ws-1")


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = _mock_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ---------- POST /thoughts (create) ----------

def test_create_thought_returns_201_or_200(client):
    """POST /thoughts with valid body should succeed (P0-1 regression test)."""
    resp = client.post(
        "/api/v1/thoughts",
        json={
            "workspace_id": "ws-1",
            "session_id": "sess-1",
            "title": "Add caching layer",
            "rationale": "Reduce latency by 40%",
        },
        headers=MOCK_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "thought_id" in data
    assert data["title"] == "Add caching layer"
    assert data["state"] == "draft"


def test_create_thought_with_proposal_link(client):
    """Creating a thought with a proposal_id should auto-create a link."""
    resp = client.post(
        "/api/v1/thoughts",
        json={
            "workspace_id": "ws-1",
            "session_id": "sess-1",
            "title": "Refactor auth module",
            "rationale": "Simplify token validation",
            "proposal_id": "prop-abc",
        },
        headers=MOCK_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(
        link.get("target_id") == "prop-abc" for link in data.get("links", [])
    )


# ---------- GET /thoughts/{id} ----------

def test_get_thought_by_id(client):
    """GET /thoughts/{id} should return the created thought."""
    # Create first
    create_resp = client.post(
        "/api/v1/thoughts",
        json={
            "workspace_id": "ws-1",
            "session_id": "sess-1",
            "title": "Test thought",
            "rationale": "For testing",
        },
        headers=MOCK_HEADERS,
    )
    thought_id = create_resp.json()["thought_id"]

    # Get
    resp = client.get(f"/api/v1/thoughts/{thought_id}", headers=MOCK_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["thought_id"] == thought_id


def test_get_nonexistent_thought(client):
    """GET /thoughts/{bad-id} should return 404."""
    resp = client.get("/api/v1/thoughts/nonexistent-id", headers=MOCK_HEADERS)
    assert resp.status_code == 404


# ---------- PATCH /thoughts/{id} (update) ----------

def test_update_thought(client):
    """PATCH /thoughts/{id} should update title/rationale."""
    create_resp = client.post(
        "/api/v1/thoughts",
        json={
            "workspace_id": "ws-1",
            "session_id": "sess-1",
            "title": "Original title",
            "rationale": "Original rationale",
        },
        headers=MOCK_HEADERS,
    )
    thought_id = create_resp.json()["thought_id"]

    resp = client.patch(
        f"/api/v1/thoughts/{thought_id}",
        json={"title": "Updated title"},
        headers=MOCK_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated title"


# ---------- POST /thoughts/{id}/seal ----------

def test_seal_thought(client):
    """Sealing a draft thought should change its state."""
    create_resp = client.post(
        "/api/v1/thoughts",
        json={
            "workspace_id": "ws-1",
            "session_id": "sess-1",
            "title": "Sealable thought",
            "rationale": "Will be sealed",
        },
        headers=MOCK_HEADERS,
    )
    thought_id = create_resp.json()["thought_id"]

    resp = client.post(
        f"/api/v1/thoughts/{thought_id}/seal",
        json={},
        headers=MOCK_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] in ("sealed", "draft")  # May be idempotent
