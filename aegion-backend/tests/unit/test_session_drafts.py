"""
Aegion Tests - Session Drafts.

Verifies the "Partial Persistence" behavior.
- Drafts are mutable.
- Drafts are user-scoped.
- Drafts can be restored (consumed).

AG-005: Tests InMemoryDraftStore via _get_draft_store seam.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.models.draft import SessionDraft
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app.core.security import get_current_user, AuthorityContext, Role
from app.api.v1.stores import InMemoryDraftStore


@pytest.fixture
def mock_store():
    return InMemoryDraftStore()


@pytest.fixture
def client_with_auth(mock_store):
    mock_user = AuthorityContext(
        user_id="dev-user",
        role=Role.DEVELOPER,
        can_approve_t1=False,
        can_approve_t2=False
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    with patch("app.api.v1.drafts._get_draft_store", return_value=mock_store):
        yield TestClient(app)

    app.dependency_overrides = {}


HEADERS = {
    "Authorization": "Bearer mock-token",
    "X-Aegion-Session": "sess-test-draft-context",
    "X-Aegion-Intent": "manage_drafts"
}


def test_draft_lifecycle(client_with_auth):
    client = client_with_auth

    # 1. Save Draft
    draft_payload = {
        "draft_id": "draft-test-01",
        "user_id": "dev-user",
        "workspace_id": "ws-1",
        "title": "My WIP Session",
        "context_data": {"note": "stopped at line 50"}
    }

    response = client.post("/api/v1/sessions/drafts/", json=draft_payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "My WIP Session"
    assert data["updated_at"] is not None

    # 2. Update Draft (Mutable)
    draft_payload["title"] = "My WIP Session (Updated)"
    response = client.post("/api/v1/sessions/drafts/", json=draft_payload, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["title"] == "My WIP Session (Updated)"

    # 3. List Drafts
    response = client.get("/api/v1/sessions/drafts/", headers=HEADERS)
    assert response.status_code == 200
    assert len(response.json()) >= 1

    # 4. Restore Draft (Consume)
    response = client.post("/api/v1/sessions/drafts/draft-test-01/restore", headers=HEADERS)
    assert response.status_code == 201

    # 5. Verify Draft Gone
    response = client.get("/api/v1/sessions/drafts/draft-test-01", headers=HEADERS)
    assert response.status_code == 404


def test_draft_user_isolation(client_with_auth):
    """Drafts from another user should be inaccessible."""
    client = client_with_auth

    # Save draft as dev-user, then try to access as someone else
    draft_payload = {
        "draft_id": "draft-other-01",
        "user_id": "dev-user",
        "workspace_id": "ws-1",
        "title": "My Secret Draft"
    }
    client.post("/api/v1/sessions/drafts/", json=draft_payload, headers=HEADERS)

    # Switch to other user
    other_user = AuthorityContext(
        user_id="other-user",
        role=Role.DEVELOPER,
        can_approve_t1=False,
        can_approve_t2=False
    )
    app.dependency_overrides[get_current_user] = lambda: other_user

    # Should be forbidden
    response = client.get("/api/v1/sessions/drafts/draft-other-01", headers=HEADERS)
    assert response.status_code == 403
