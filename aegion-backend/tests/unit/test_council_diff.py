"""
Tests for Council diff generation after P0-2 unification.

The invoke endpoint now routes through CouncilService.convene_session().
We mock the service dependency to verify diff extraction from recommendations.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext
from app.services.council.council_service import CouncilService
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_user():
    return AuthorityContext(
        user_id="user-1",
        scopes=["read", "write"],
        role="architect",
        can_approve_t1=True,
    )


@pytest.fixture
def client(mock_user):
    """Client with mocked auth and CouncilService that returns a code block."""
    mock_session = MagicMock()
    mock_session.consensus_reached = True
    mock_session.summary = """
    I suggest this implementation:
    ```python
    def new_feature():
        # New logic
        return True
    ```
    """
    mock_session.confidence = 0.9
    mock_session.sentinel_blocked = False
    mock_session.verdict = "supported"

    mock_service = MagicMock(spec=CouncilService)
    mock_service.convene_session = AsyncMock(return_value=mock_session)

    app.dependency_overrides[get_current_user] = lambda: mock_user

    # Override the CouncilService dependency via app state
    if not hasattr(app.state, '_original_council_service'):
        app.state._original_council_service = getattr(app.state, 'council_service', None)
    app.state.council_service = mock_service

    c = TestClient(app)
    yield c

    # Cleanup
    app.dependency_overrides.clear()
    if app.state._original_council_service is not None:
        app.state.council_service = app.state._original_council_service


def test_council_returns_dynamic_diff(client):
    """Test that council returns a dynamically generated diff."""
    payload = {
        "session_id": "sess-123",
        "prompt": "Write a function",
        "context": {}
    }

    headers = {"X-Aegion-Session": "sess-123", "X-Aegion-Intent": "invoke_council"}

    response = client.post(
        "/api/v1/council/invoke",
        json=payload,
        headers=headers
    )

    assert response.status_code == 200
    data = response.json()

    # Check that diff was generated from the code block
    assert data["diff"] is not None
    assert "+++ b/" in data["diff"]


def test_council_sentinel_fail_safe(client, mock_user):
    """If CouncilService raises, sentinel should engage (fail-safe)."""
    mock_service = MagicMock(spec=CouncilService)
    mock_service.convene_session = AsyncMock(side_effect=RuntimeError("LLM unreachable"))
    app.state.council_service = mock_service
    app.dependency_overrides[get_current_user] = lambda: mock_user

    c = TestClient(app)
    response = c.post(
        "/api/v1/council/invoke",
        json={"session_id": "s-1", "prompt": "test", "context": {}},
        headers={"X-Aegion-Session": "s-1", "X-Aegion-Intent": "invoke_council"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sentinel_blocking"] is True
    assert "fail-safe" in data["recommendation"].lower() or "failed" in data["recommendation"].lower()
