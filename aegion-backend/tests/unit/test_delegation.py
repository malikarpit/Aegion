"""
Test Cloud Delegation (Phase 35 - AG-017).

Tests for delegation service and API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext
from app.services.delegation_service import get_delegation_service, DelegationService
from app.ports.cloud_delegate import CloudProvider, DeploymentStatus

# Mock the dependency to avoid real AWS calls (already mocked in adapter, but good to be safe)
@pytest.fixture
def client():
    mock_user = AuthorityContext(user_id="test-arch", role="admin")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as c:
        c.headers.update({"X-Session-Id": "test-session-123", "X-Workspace-Id": "ws-test"})
        yield c
    app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_delegation_flow(client):
    """Test full delegation flow: deploy, status, resources, logs."""
    headers = {
        "X-Aegion-Session": "test-session-123",
        "X-Workspace-Id": "ws-test",
        "X-Aegion-Intent": "delegation-test"
    }
    
    # 1. Trigger Deployment
    deploy_payload = {
        "artifact_id": "build-123",
        "target_env": "staging",
        "config": {"instance_type": "t3.micro"}
    }
    response = client.post("/api/v1/delegation/deploy", json=deploy_payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["in_progress", "success"]
    deployment_id = data["deployment_id"]
    
    # 2. Check Status
    response = client.get(f"/api/v1/delegation/deployments/{deployment_id}", headers=headers)
    assert response.status_code == 200
    status_data = response.json()
    assert status_data["deployment_id"] == deployment_id
    
    # 3. List Resources (mock adapter simulates creating them)
    # The async deployment in mock adapter is awaited immediately for simplicity in this MVP
    response = client.get("/api/v1/delegation/resources?env=staging", headers=headers)
    assert response.status_code == 200
    resources = response.json()
    assert len(resources) >= 2  # S3 + Lambda
    assert any(r["type"] == "storage" for r in resources)
    
    # 4. Get Logs
    resource_id = resources[0]["resource_id"]
    response = client.get(f"/api/v1/delegation/resources/{resource_id}/logs", headers=headers)
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)
    assert len(logs) > 0

@pytest.mark.anyio
async def test_provider_health(client):
    headers = {
        "X-Aegion-Session": "test-session-123",
        "X-Aegion-Intent": "health-check"
    }
    response = client.get("/api/v1/delegation/health", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "connected"
    assert data["provider"] == "aws"

@pytest.mark.anyio
async def test_remote_run_lifecycle(client):
    """Test remote run lifecycle: trigger -> pending -> running -> completed."""
    import asyncio
    
    headers = {
        "X-Aegion-Session": "test-session-123",
        "X-Workspace-Id": "ws-test",
        "X-Aegion-Intent": "run-test"
    }

    # 1. Trigger Run
    run_payload = {
        "command": "pytest tests/unit",
        "image": "aegion-test-runner",
        "resource_size": "small"
    }
    response = client.post("/api/v1/delegation/runs", json=run_payload, headers=headers)
    assert response.status_code == 200
    run_data = response.json()
    run_id = run_data["run_id"]
    assert run_data["status"] == "pending"

    # 2. Wait for simulation (AWSDelegate sleeps 0.5s provisioning + 1.0s execution)
    # Check intermediate status
    await asyncio.sleep(0.6)
    response = client.get(f"/api/v1/delegation/runs/{run_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "running"

    # 3. Wait for completion
    await asyncio.sleep(1.1) 
    response = client.get(f"/api/v1/delegation/runs/{run_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["exit_code"] == 0
    assert "s3://" in data["logs_url"]

    # 4. List Runs
    response = client.get("/api/v1/delegation/runs", headers=headers)
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) >= 1
    assert any(r["run_id"] == run_id for r in runs)
