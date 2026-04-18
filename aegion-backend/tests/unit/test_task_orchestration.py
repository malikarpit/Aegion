"""
Test Task Orchestration (Phase 28 - AG-010).

Tests for Task CRUD, status transitions, and run lifecycle.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext


@pytest.fixture
def client():
    """Create test client with mocked auth."""
    mock_user = AuthorityContext(
        user_id="test-user-tasks",
        role="developer",
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    c = TestClient(app)
    c.headers.update({
        "X-Aegion-Session": "test-session-tasks",
        "X-Aegion-Intent": "task_orchestration",
    })
    yield c
    app.dependency_overrides.clear()


def test_create_task(client):
    """Test creating a new task."""
    response = client.post(
        "/api/v1/tasks",
        json={
            "session_id": "test-session-1",
            "title": "Implement auth module",
            "description": "Add OAuth2 authentication",
            "priority": "high",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Implement auth module"
    assert data["status"] == "pending"
    assert data["priority"] == "high"
    assert data["task_id"]


def test_list_tasks(client):
    """Test listing tasks."""
    # Create two tasks
    client.post(
        "/api/v1/tasks",
        json={"session_id": "s1", "title": "Task A", "priority": "low"},
    )
    client.post(
        "/api/v1/tasks",
        json={"session_id": "s1", "title": "Task B", "priority": "critical"},
    )

    response = client.get("/api/v1/tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) >= 2

    # Critical should come first (sorted by priority)
    titles = [t["title"] for t in tasks]
    assert titles.index("Task B") < titles.index("Task A")


def test_list_tasks_filter_by_status(client):
    """Test filtering tasks by status."""
    client.post(
        "/api/v1/tasks",
        json={"session_id": "s-filter", "title": "Filterable"},
    )

    response = client.get("/api/v1/tasks?status_filter=pending")
    assert response.status_code == 200
    tasks = response.json()
    for t in tasks:
        assert t["status"] == "pending"


def test_get_task(client):
    """Test getting a specific task."""
    create_resp = client.post(
        "/api/v1/tasks",
        json={"session_id": "s2", "title": "Get me"},
    )
    task_id = create_resp.json()["task_id"]

    response = client.get(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Get me"


def test_get_task_not_found(client):
    """Test 404 for missing task."""
    response = client.get("/api/v1/tasks/nonexistent-id")
    assert response.status_code == 404


def test_update_task(client):
    """Test updating a task."""
    create_resp = client.post(
        "/api/v1/tasks",
        json={"session_id": "s3", "title": "Update me"},
    )
    task_id = create_resp.json()["task_id"]

    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Updated title", "priority": "critical"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"
    assert response.json()["priority"] == "critical"


def test_update_task_status_completed(client):
    """Test marking a task as completed."""
    create_resp = client.post(
        "/api/v1/tasks",
        json={"session_id": "s4", "title": "Complete me"},
    )
    task_id = create_resp.json()["task_id"]

    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "completed"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["completed_at"] is not None


def test_run_task(client):
    """Test triggering an agent run on a task."""
    create_resp = client.post(
        "/api/v1/tasks",
        json={"session_id": "s5", "title": "Run me"},
    )
    task_id = create_resp.json()["task_id"]

    response = client.post(
        f"/api/v1/tasks/{task_id}/run",
        json={"agent_id": "noesis", "async_execution": False},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["agent_id"] == "noesis"
    assert run["status"] in ["running", "completed"]
    assert run["run_id"]


def test_run_completed_task_fails(client):
    """Test that running a completed task fails."""
    create_resp = client.post(
        "/api/v1/tasks",
        json={"session_id": "s6", "title": "Already done"},
    )
    task_id = create_resp.json()["task_id"]

    # Complete it first
    client.patch(f"/api/v1/tasks/{task_id}", json={"status": "completed"})

    # Try to run
    response = client.post(
        f"/api/v1/tasks/{task_id}/run",
        json={"agent_id": "noesis"},
    )
    assert response.status_code == 400


def test_get_task_runs(client):
    """Test getting run history for a task."""
    create_resp = client.post(
        "/api/v1/tasks",
        json={"session_id": "s7", "title": "Show runs"},
    )
    task_id = create_resp.json()["task_id"]

    # Trigger a run
    client.post(
        f"/api/v1/tasks/{task_id}/run",
        json={"agent_id": "sentinel", "async_execution": False},
    )

    response = client.get(f"/api/v1/tasks/{task_id}/runs")
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) >= 1
    assert runs[0]["agent_id"] == "sentinel"


def test_task_run_updates_count(client):
    """Test that running a task increments the run count."""
    create_resp = client.post(
        "/api/v1/tasks",
        json={"session_id": "s8", "title": "Count runs"},
    )
    task_id = create_resp.json()["task_id"]
    assert create_resp.json()["run_count"] == 0

    client.post(f"/api/v1/tasks/{task_id}/run", json={"agent_id": "noesis", "async_execution": False})

    response = client.get(f"/api/v1/tasks/{task_id}")
    assert response.json()["run_count"] == 1
