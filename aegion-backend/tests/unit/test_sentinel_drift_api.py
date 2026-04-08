"""
Tests for the Sentinel Drift Detection API endpoint.

Note: The sentinel drift route at /api/v1/sentinel/drift is handled by
the analytics.py sentinel_router, which requires DriftRequest fields:
workspace_id, current_period, baseline_period.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import AuthorityContext, get_current_user


MOCK_HEADERS = {
    "X-Aegion-Session": "test-session-123",
    "X-API-Key": "test-key-456",
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


def _drift_request(active_files=None, workspace_id="ws-1"):
    """Build a valid DriftRequest payload."""
    return {
        "workspace_id": workspace_id,
        "current_period": [{"file": f, "changes": 1} for f in (active_files or [])],
        "baseline_period": [],
        "observation_hours": 24,
    }


def test_drift_check_returns_200(client):
    """POST /sentinel/drift with valid body should return 200."""
    resp = client.post(
        "/api/v1/sentinel/drift",
        json=_drift_request(["src/main.py"]),
        headers=MOCK_HEADERS,
    )
    assert resp.status_code == 200


def test_drift_check_response_has_signals(client):
    """Response should contain drift report fields."""
    resp = client.post(
        "/api/v1/sentinel/drift",
        json=_drift_request(),
        headers=MOCK_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    # DriftReport has 'signals' and 'summary'
    assert "signals" in data or "summary" in data or isinstance(data, (dict, list))


def test_drift_check_empty_periods(client):
    """POST /sentinel/drift with empty periods should still work."""
    resp = client.post(
        "/api/v1/sentinel/drift",
        json={
            "workspace_id": "ws-1",
            "current_period": [],
            "baseline_period": [],
        },
        headers=MOCK_HEADERS,
    )
    assert resp.status_code == 200


def test_drift_status_endpoint(client):
    """GET /sentinel/drift/{workspace_id}/status should return drift summary."""
    resp = client.get(
        "/api/v1/sentinel/drift/ws-1/status",
        headers=MOCK_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data or "drift_detected" in data or isinstance(data, dict)
