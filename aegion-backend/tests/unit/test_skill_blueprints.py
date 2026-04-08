"""
Test Skill Blueprint Library (Phase 31 - AG-013).

Tests for skill CRUD, install lifecycle, signature validation,
catalog filtering, and provenance checks.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext


@pytest.fixture
def client():
    """Create test client with mocked auth."""
    mock_user = AuthorityContext(
        user_id="test-user-skills",
        role="developer",
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    c = TestClient(app)
    c.headers.update({
        "X-Aegion-Session": "test-session-sk",
        "X-Aegion-Intent": "skills",
    })
    yield c
    app.dependency_overrides.clear()


# ========== Skill CRUD Tests ==========


def test_create_skill(client):
    """Test creating a skill blueprint."""
    response = client.post("/api/v1/skills", json={
        "name": "Python Code Review",
        "description": "Reviews Python code for best practices",
        "prompt_template": "Review this {{language}} code: {{code}}",
        "category": "code_review",
        "tags": ["python", "review"],
        "parameters": ["language", "code"],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Python Code Review"
    assert data["category"] == "code_review"
    assert data["status"] == "available"
    assert data["signature"] is not None
    assert len(data["parameters"]) == 2


def test_create_skill_default_category(client):
    """Test creating a skill with default category."""
    response = client.post("/api/v1/skills", json={
        "name": "Custom Skill",
        "prompt_template": "Do {{task}}",
    })
    assert response.status_code == 201
    assert response.json()["category"] == "custom"


def test_list_skills_catalog(client):
    """Test listing skills (catalog view)."""
    client.post("/api/v1/skills", json={"name": "Skill A", "prompt_template": "{{a}}"})
    client.post("/api/v1/skills", json={"name": "Skill B", "prompt_template": "{{b}}"})

    response = client.get("/api/v1/skills")
    assert response.status_code == 200
    skills = response.json()
    assert len(skills) >= 2


def test_list_skills_filter_category(client):
    """Test filtering skills by category."""
    client.post("/api/v1/skills", json={"name": "Test Skill", "prompt_template": "{{x}}", "category": "testing"})

    response = client.get("/api/v1/skills?category=testing")
    assert response.status_code == 200
    skills = response.json()
    for s in skills:
        assert s["category"] == "testing"


def test_get_skill(client):
    """Test getting a specific skill."""
    create = client.post("/api/v1/skills", json={"name": "Fetch Me", "prompt_template": "{{x}}"})
    skill_id = create.json()["skill_id"]

    response = client.get(f"/api/v1/skills/{skill_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Fetch Me"


def test_get_skill_not_found(client):
    """Test 404 for missing skill."""
    response = client.get("/api/v1/skills/nonexistent")
    assert response.status_code == 404


def test_delete_skill(client):
    """Test deleting a skill."""
    create = client.post("/api/v1/skills", json={"name": "Delete Me", "prompt_template": "{{x}}"})
    skill_id = create.json()["skill_id"]

    response = client.delete(f"/api/v1/skills/{skill_id}")
    assert response.status_code == 204
    assert client.get(f"/api/v1/skills/{skill_id}").status_code == 404


# ========== Install Lifecycle Tests ==========


def test_install_skill(client):
    """Test installing a skill."""
    create = client.post("/api/v1/skills", json={"name": "Install Me", "prompt_template": "{{x}}"})
    skill_id = create.json()["skill_id"]

    response = client.post(f"/api/v1/skills/{skill_id}/install")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "installed"
    assert "successfully" in data["message"]

    # Verify status updated
    skill = client.get(f"/api/v1/skills/{skill_id}").json()
    assert skill["status"] == "installed"
    assert skill["install_count"] == 1


def test_install_already_installed(client):
    """Test installing an already-installed skill returns 409."""
    create = client.post("/api/v1/skills", json={"name": "Double Install", "prompt_template": "{{x}}"})
    skill_id = create.json()["skill_id"]

    client.post(f"/api/v1/skills/{skill_id}/install")
    response = client.post(f"/api/v1/skills/{skill_id}/install")
    assert response.status_code == 409


def test_install_not_found(client):
    """Test installing a nonexistent skill."""
    response = client.post("/api/v1/skills/nonexistent/install")
    assert response.status_code == 404


# ========== Signature/Provenance Tests ==========


def test_validate_signature_valid(client):
    """Test validating a skill with a correct signature."""
    create = client.post("/api/v1/skills", json={"name": "Valid Sig", "prompt_template": "{{x}}"})
    skill_id = create.json()["skill_id"]

    response = client.post(f"/api/v1/skills/{skill_id}/validate")
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert "valid" in data["message"].lower()


def test_validate_not_found(client):
    """Test validating a nonexistent skill."""
    response = client.post("/api/v1/skills/nonexistent/validate")
    assert response.status_code == 404


def test_list_installed_only(client):
    """Test filtering catalog to installed skills."""
    create = client.post("/api/v1/skills", json={"name": "Installed One", "prompt_template": "{{x}}"})
    skill_id = create.json()["skill_id"]
    client.post(f"/api/v1/skills/{skill_id}/install")

    client.post("/api/v1/skills", json={"name": "Not Installed", "prompt_template": "{{y}}"})

    response = client.get("/api/v1/skills?status_filter=installed")
    assert response.status_code == 200
    skills = response.json()
    for s in skills:
        assert s["status"] == "installed"
