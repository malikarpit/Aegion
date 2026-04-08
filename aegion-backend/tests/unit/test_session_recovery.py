"""
Aegion Tests - Session Recovery.

Verifies "Crash Recovery" workflow:
1. List orphaned sessions.
2. Recover session -> Draft.

AG-005: Tests InMemorySessionStore via _get_session_store seam.
"""

from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import timezone, datetime, timedelta
from anyio import run
import pytest

from app.main import app
from app.models.session import Session, SessionStatus
from app.core.security import get_current_user, AuthorityContext, Role
from app.api.v1.stores import InMemorySessionStore, InMemoryDraftStore

MOCK_USER_ID = "user-dev-123"
MOCK_SESSION_ID = "sess-crash-001"

HEADERS = {
    "Authorization": "Bearer mock-token",
    "X-Aegion-Session": "sess-admin-check",
    "X-Aegion-Intent": "audit_recovery"
}


@pytest.fixture
def stores():
    return InMemorySessionStore(), InMemoryDraftStore()


@pytest.fixture
def client_with_auth(stores):
    session_store, draft_store = stores

    mock_user = AuthorityContext(
        user_id=MOCK_USER_ID,
        role=Role.DEVELOPER,
        can_approve_t1=False,
        can_approve_t2=False
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    with patch("app.api.v1.recovery._get_session_store", return_value=session_store), \
         patch("app.api.v1.recovery._get_draft_store", return_value=draft_store):
        yield TestClient(app), session_store, draft_store

    app.dependency_overrides = {}


def test_list_orphaned_sessions(client_with_auth):
    client, session_store, _ = client_with_auth

    # Seed a stale session
    stale_session = Session(
        session_id=MOCK_SESSION_ID,
        owner_id=MOCK_USER_ID,
        workspace_id="ws-1",
        status="active",
        created_at=datetime.now(timezone.utc),
        last_activity_at=datetime.now(timezone.utc) - timedelta(hours=2)
    )

    async def _seed():
        await session_store.create(stale_session)
    run(_seed)

    response = client.get("/api/v1/sessions/orphaned?threshold_minutes=60", headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["session_id"] == MOCK_SESSION_ID


def test_recover_session(client_with_auth):
    client, session_store, draft_store = client_with_auth

    # Seed an active session
    active_session = Session(
        session_id=MOCK_SESSION_ID,
        owner_id=MOCK_USER_ID,
        workspace_id="ws-1",
        status="active",
        created_at=datetime.now(timezone.utc),
        last_activity_at=datetime.now(timezone.utc),
        context_hash="hash-123"
    )

    async def _seed():
        await session_store.create(active_session)
    run(_seed)

    response = client.post(f"/api/v1/sessions/{MOCK_SESSION_ID}/recover", headers=HEADERS)

    # Verify
    assert response.status_code == 200
    draft = response.json()
    assert draft["context_data"]["source_session_id"] == MOCK_SESSION_ID
    assert draft["tags"] == ["recovered"]

    # Verify session was expired
    async def _check():
        session = await session_store.get_by_id(MOCK_SESSION_ID)
        assert session.status == "expired"
    run(_check)


def test_cannot_recover_inactive_session(client_with_auth):
    """Only active sessions can be recovered."""
    client, session_store, _ = client_with_auth

    closed_session = Session(
        session_id="sess-closed-001",
        owner_id=MOCK_USER_ID,
        workspace_id="ws-1",
        status="closed",
        created_at=datetime.now(timezone.utc),
        last_activity_at=datetime.now(timezone.utc)
    )

    async def _seed():
        await session_store.create(closed_session)
    run(_seed)

    response = client.post("/api/v1/sessions/sess-closed-001/recover", headers=HEADERS)
    assert response.status_code == 400
    assert "inactive" in response.json()["detail"]
