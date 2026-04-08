"""
Test War Room (Phase 33 - AG-015).

Tests for incident lifecycle and warroom overview aggregation.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext


@pytest.fixture
def client():
    mock_user = AuthorityContext(user_id="test-ops", role="admin")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    c = TestClient(app)
    c.headers.update({
        "X-Aegion-Session": "test-session-warroom",
        "X-Aegion-Intent": "warroom",
    })
    yield c
    app.dependency_overrides.clear()


# ========== Incident Tests ==========


def test_create_incident(client):
    """Test creating an incident."""
    response = client.post("/api/v1/warroom/incidents", json={
        "title": "Database Latency",
        "description": "High latency in prod DB",
        "severity": "high",
        "service": "database",
        "tags": ["db", "latency"],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Database Latency"
    assert data["severity"] == "high"
    assert data["status"] == "open"


def test_list_incidents(client):
    """Test listing incidents with filters."""
    client.post("/api/v1/warroom/incidents", json={"title": "A", "service": "api", "severity": "low"})
    client.post("/api/v1/warroom/incidents", json={"title": "B", "service": "web", "severity": "critical"})

    response = client.get("/api/v1/warroom/incidents")
    assert response.status_code == 200
    assert len(response.json()) >= 2

    response_crit = client.get("/api/v1/warroom/incidents?severity=critical")
    assert len(response_crit.json()) == 1
    assert response_crit.json()[0]["title"] == "B"


def test_resolve_incident(client):
    """Test resolving an incident."""
    create = client.post("/api/v1/warroom/incidents", json={"title": "Fix Me", "service": "api"})
    id = create.json()["incident_id"]

    response = client.patch(f"/api/v1/warroom/incidents/{id}?status_update=resolved")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["resolved_at"] is not None


# ========== Overview Tests ==========


def test_warroom_overview(client):
    """Test overview aggregation."""
    # Ensure clean state for aggregation check might be tricky with shared in-memory stores,
    # but we can check the structure and basic values.
    
    # Create a critical incident
    client.post("/api/v1/warroom/incidents", json={"title": "Critical One", "severity": "critical", "service": "core"})
    
    response = client.get("/api/v1/warroom/overview")
    assert response.status_code == 200
    data = response.json()
    
    assert data["system_status"] == "critical"
    assert data["critical_incidents"] >= 1
    assert "online_users" in data
    assert "active_checkpoints" in data
