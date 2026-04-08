"""
Test Memory & Rules System (Phase 30 - AG-012).

Tests for memory CRUD, scope filtering, tag search,
rule CRUD, enable/disable, precedence, and evaluation.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext


@pytest.fixture
def client():
    """Create test client with mocked auth."""
    mock_user = AuthorityContext(
        user_id="test-user-memory",
        role="developer",
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    c = TestClient(app)
    c.headers.update({
        "X-Aegion-Session": "test-session-mr",
        "X-Aegion-Intent": "memory_rules",
    })
    yield c
    app.dependency_overrides.clear()


# ========== Memory Tests ==========


def test_store_memory(client):
    """Test storing a memory entry."""
    response = client.post(
        "/api/v1/memory",
        json={
            "key": "auth_pattern",
            "value": {"type": "OAuth2", "provider": "Firebase"},
            "scope": "repository",
            "tags": ["auth", "security"],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["key"] == "auth_pattern"
    assert data["scope"] == "repository"
    assert "auth" in data["tags"]
    assert data["confidence"] == 1.0


def test_list_memory(client):
    """Test listing memory entries."""
    client.post("/api/v1/memory", json={"key": "pattern_a", "value": "A"})
    client.post("/api/v1/memory", json={"key": "pattern_b", "value": "B"})

    response = client.get("/api/v1/memory")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) >= 2


def test_list_memory_filter_by_scope(client):
    """Test filtering memory by scope."""
    client.post("/api/v1/memory", json={"key": "org_key", "value": "v", "scope": "organization"})
    client.post("/api/v1/memory", json={"key": "repo_key", "value": "v", "scope": "repository"})

    response = client.get("/api/v1/memory?scope=organization")
    assert response.status_code == 200
    entries = response.json()
    for e in entries:
        assert e["scope"] == "organization"


def test_list_memory_filter_by_tag(client):
    """Test filtering memory by tag."""
    client.post("/api/v1/memory", json={"key": "tagged", "value": "v", "tags": ["special"]})

    response = client.get("/api/v1/memory?tag=special")
    assert response.status_code == 200
    entries = response.json()
    assert any(e["key"] == "tagged" for e in entries)


def test_list_memory_filter_by_key_prefix(client):
    """Test filtering memory by key prefix."""
    client.post("/api/v1/memory", json={"key": "config.db.host", "value": "localhost"})
    client.post("/api/v1/memory", json={"key": "config.db.port", "value": 5432})

    response = client.get("/api/v1/memory?key_prefix=config.db")
    assert response.status_code == 200
    entries = response.json()
    assert all(e["key"].startswith("config.db") for e in entries)


def test_get_memory(client):
    """Test getting a specific memory entry."""
    create_resp = client.post("/api/v1/memory", json={"key": "fetch_me", "value": 42})
    mem_id = create_resp.json()["memory_id"]

    response = client.get(f"/api/v1/memory/{mem_id}")
    assert response.status_code == 200
    assert response.json()["key"] == "fetch_me"


def test_get_memory_not_found(client):
    """Test 404 for missing memory."""
    response = client.get("/api/v1/memory/nonexistent")
    assert response.status_code == 404


def test_supersede_memory(client):
    """Test superseding a memory entry (immutability doctrine)."""
    create_resp = client.post("/api/v1/memory", json={"key": "supersede_me", "value": "bye"})
    mem_id = create_resp.json()["memory_id"]

    response = client.post(f"/api/v1/memory/{mem_id}/supersede", json={"reason": "outdated"})
    assert response.status_code == 200
    data = response.json()
    assert data["superseded"] is True
    assert data["reason"] == "outdated"

    # Entry should still exist but be superseded
    get_resp = client.get(f"/api/v1/memory/{mem_id}")
    assert get_resp.status_code == 200


# ========== Rules Tests ==========


def test_create_rule(client):
    """Test creating a rule."""
    response = client.post(
        "/api/v1/rules",
        json={
            "name": "Require Python linting",
            "condition": "file.extension == .py",
            "action": "require_review",
            "priority": "high",
            "tags": ["python", "quality"],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Require Python linting"
    assert data["action"] == "require_review"
    assert data["priority"] == "high"
    assert data["enabled"] is True


def test_list_rules(client):
    """Test listing rules sorted by priority."""
    client.post("/api/v1/rules", json={"name": "Low rule", "condition": "x", "action": "warn", "priority": "low"})
    client.post("/api/v1/rules", json={"name": "Critical rule", "condition": "y", "action": "block", "priority": "critical"})

    response = client.get("/api/v1/rules")
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) >= 2

    # Critical first
    names = [r["name"] for r in rules]
    assert names.index("Critical rule") < names.index("Low rule")


def test_get_rule(client):
    """Test getting a specific rule."""
    create_resp = client.post("/api/v1/rules", json={"name": "Fetch rule", "condition": "a", "action": "b"})
    rule_id = create_resp.json()["rule_id"]

    response = client.get(f"/api/v1/rules/{rule_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Fetch rule"


def test_get_rule_not_found(client):
    """Test 404 for missing rule."""
    response = client.get("/api/v1/rules/nonexistent")
    assert response.status_code == 404


def test_update_rule_toggle_enabled(client):
    """Test toggling a rule's enabled state."""
    create_resp = client.post("/api/v1/rules", json={"name": "Toggle me", "condition": "c", "action": "d"})
    rule_id = create_resp.json()["rule_id"]

    # Disable
    response = client.patch(f"/api/v1/rules/{rule_id}", json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["updated_at"] is not None

    # Re-enable
    response = client.patch(f"/api/v1/rules/{rule_id}", json={"enabled": True})
    assert response.json()["enabled"] is True


def test_update_rule_priority(client):
    """Test changing a rule's priority."""
    create_resp = client.post("/api/v1/rules", json={"name": "Priority change", "condition": "e", "action": "f"})
    rule_id = create_resp.json()["rule_id"]

    response = client.patch(f"/api/v1/rules/{rule_id}", json={"priority": "critical"})
    assert response.json()["priority"] == "critical"


def test_delete_rule(client):
    """Test deleting a rule."""
    create_resp = client.post("/api/v1/rules", json={"name": "Delete me", "condition": "g", "action": "h"})
    rule_id = create_resp.json()["rule_id"]

    response = client.delete(f"/api/v1/rules/{rule_id}")
    assert response.status_code == 204

    assert client.get(f"/api/v1/rules/{rule_id}").status_code == 404


def test_evaluate_rules(client):
    """Test evaluating rules against context."""
    client.post("/api/v1/rules", json={"name": "Python check", "condition": "file.extension == .py", "action": "lint", "priority": "high"})
    client.post("/api/v1/rules", json={"name": "JS check", "condition": "file.extension == .js", "action": "eslint", "priority": "medium"})

    response = client.post("/api/v1/rules/evaluate", json={"context": {"file": "test.py", "extension": ".py"}})
    assert response.status_code == 200
    result = response.json()
    assert result["total_evaluated"] >= 2
    assert "lint" in result["actions"]


def test_evaluate_rules_disabled_excluded(client):
    """Test that disabled rules are excluded from evaluation."""
    create_resp = client.post("/api/v1/rules", json={"name": "Disabled rule", "condition": "always", "action": "block"})
    rule_id = create_resp.json()["rule_id"]
    client.patch(f"/api/v1/rules/{rule_id}", json={"enabled": False})

    response = client.post("/api/v1/rules/evaluate", json={"context": {"always": "true"}})
    result = response.json()
    matched_ids = [r["rule_id"] for r in result["matched_rules"]]
    assert rule_id not in matched_ids
