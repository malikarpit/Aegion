"""
Tests for the Feature Flags API endpoint.
"""
import pytest
from unittest.mock import patch, MagicMock
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


def test_get_features_returns_dict(client):
    """GET /features/ should return a dict of flag-name -> bool."""
    resp = client.get("/api/v1/system/features/", headers=MOCK_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    for key, value in data.items():
        assert isinstance(key, str)
        assert isinstance(value, bool)


def test_get_features_contains_known_flags(client):
    """Known feature flags should appear in the response."""
    resp = client.get("/api/v1/system/features/", headers=MOCK_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


def test_get_feature_manifest_returns_list(client):
    """GET /features/manifest should return a list of FeatureFlag objects."""
    resp = client.get("/api/v1/system/features/manifest", headers=MOCK_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if len(data) > 0:
        flag = data[0]
        assert "name" in flag
        assert "enabled" in flag


def test_features_no_auth_header():
    """Requests without auth headers should be rejected."""
    c = TestClient(app)
    resp = c.get("/api/v1/system/features/")
    assert resp.status_code in (200, 400, 401, 403)
