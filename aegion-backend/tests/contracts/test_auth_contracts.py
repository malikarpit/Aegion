"""
Authentication & Authorization Contract Tests.

Verifies that the API correctly enforces security boundaries:
1. Public endpoints are accessible without auth.
2. Protected endpoints return 401/403 without valid credentials.
3. CORS headers are correctly set.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.mark.unit
def test_public_health_endpoints():
    """Verify health endpoints are public and return correct formats."""
    # Liveness (Text)
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.text == "OK"

    # Health (JSON)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.unit
def test_protected_route_rejects_anonymous():
    """Verify protected route requires auth."""
    # Try to list workspaces without auth
    response = client.get("/api/v1/workspaces/")
    # Should be 401 or 403 depending on implementation
    assert response.status_code in [401, 403]

@pytest.mark.unit
def test_security_headers_present():
    """Verify critical security headers are set."""
    response = client.get("/api/v1/health/live")
    assert "X-Content-Type-Options" in response.headers
    assert "X-Frame-Options" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"

@pytest.mark.unit
def test_cors_preflight():
    """Verify CORS preflight requests."""
    response = client.options(
        "/api/v1/health/live",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" in response.headers
    assert "Access-Control-Allow-Methods" in response.headers
