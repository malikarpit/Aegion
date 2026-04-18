"""
Tests for Section 2 Features (Enhance Then Implement).
Covers: Checkpoints, Audit, Skills, Council Analytics, WarRoom, Admin, Secrets, Durable Store.
"""

import pytest
import os
import shutil
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.core.security import AuthorityContext, Role
from app.services.durable_store import JsonFileStore
from app.services.audit_store import get_audit_store
from app.services.vault import get_vault
from app.models.session import Session, SessionStatus

client = TestClient(app)

# Headers for middleware - passed explicitly in every request
AUTH_HEADERS = {
    "X-Aegion-Session": "test-sess-123",
    "X-Aegion-Intent": "test-intent"
}

# Mock User Contexts
def mock_admin_auth():
    return AuthorityContext(
        user_id="admin-user",
        role=Role.ADMIN,
        permissions=["*"]
    )

def mock_dev_auth():
    return AuthorityContext(
        user_id="dev-user",
        role=Role.DEVELOPER,
        permissions=["propose"]
    )

# Override dependency function - MUST MATCH THE ONE IMPORTED IN APP CODE
from app.core.security import get_current_user


@pytest.fixture(autouse=True)
def _override_auth():
    """Ensure dev auth override is active for every test in this module."""
    app.dependency_overrides[get_current_user] = mock_dev_auth
    yield
    app.dependency_overrides.pop(get_current_user, None)

# --- Phase A: Checkpoints & Audit ---

def test_checkpoint_evidence_links():
    """Feature: Checkpoints carry evidence/decision IDs."""
    response = client.post("/api/v1/checkpoints", json={
        "session_id": "test-sess-1",
        "evidence_ids": ["ev-1", "ev-2"],
        "decision_ids": ["dec-1"]
    }, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["evidence_ids"] == ["ev-1", "ev-2"]
    assert data["decision_ids"] == ["dec-1"]
    
    # Cleanup
    cp_id = data["checkpoint_id"]
    client.delete(f"/api/v1/checkpoints/{cp_id}", headers=AUTH_HEADERS)

def test_audit_store_recording_and_query():
    """Feature: Audit store query/replay."""
    app.dependency_overrides[get_current_user] = mock_admin_auth

    # Record event
    response = client.post("/api/v1/audit/events", json={
        "action": "test_action",
        "target": "test_target",
        "task_id": "task-123"
    }, headers=AUTH_HEADERS)
    assert response.status_code == 201
    
    # Query event
    response = client.get("/api/v1/audit/events", params={"action": "test_action"}, headers=AUTH_HEADERS)
    assert response.status_code == 200
    events = response.json()
    assert len(events) >= 1
    assert events[0]["action"] == "test_action"

    # Replay
    response = client.get("/api/v1/audit/replay/task-123", headers=AUTH_HEADERS)
    assert response.status_code == 200
    replay = response.json()
    assert replay["task_id"] == "task-123"
    assert len(replay["events"]) > 0

# --- Phase B: Skills ---

def test_skill_attestation():
    """Feature: Skill execution attestation."""
    app.dependency_overrides[get_current_user] = mock_dev_auth

    # Create skill first
    create_res = client.post("/api/v1/skills", json={
        "name": "Attest Skill",
        "prompt_template": "Run this",
        "category": "custom",
        "version": "1.0.0",
        "tags": ["test"],
        "parameters": []
    }, headers=AUTH_HEADERS)
    assert create_res.status_code == 201
    skill_id = create_res.json()["skill_id"]

    # Attest
    attest_res = client.post(f"/api/v1/skills/{skill_id}/attest", json={
        "execution_context": {"input": "foo"},
        "result_hash": "abc123hash",
        "duration_ms": 100
    }, headers=AUTH_HEADERS)
    assert attest_res.status_code == 200
    assert attest_res.json()["attestor"] == "dev-user"

    # Verify count in get
    get_res = client.get(f"/api/v1/skills/{skill_id}", headers=AUTH_HEADERS)
    assert get_res.json()["attestation_count"] == 1

def test_marketplace_search():
    """Feature: Marketplace search."""
    app.dependency_overrides[get_current_user] = mock_dev_auth

    # Ensure at least one matching skill exists
    create_res = client.post("/api/v1/skills", json={
        "name": "Attest Skill 2",
        "prompt_template": "Run this too",
        "category": "custom"
    }, headers=AUTH_HEADERS)
    assert create_res.status_code == 201

    response = client.get("/api/v1/skills/marketplace", params={"query": "Attest"}, headers=AUTH_HEADERS)
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    assert "Attest" in results[0]["name"]

# --- Phase C: Council/WarRoom/Admin ---

def test_council_analytics():
    """Feature: Council heatmap."""
    app.dependency_overrides[get_current_user] = mock_dev_auth

    response = client.post("/api/v1/council/analytics/analyze", json={
        "session_id": "sess-1",
        "opinions": [
            {"agent_id": "A", "verdict": "approve", "confidence": 0.9, "justification": "Looks good because..."},
            {"agent_id": "B", "verdict": "reject", "confidence": 0.8, "justification": "Risky"},
            {"agent_id": "C", "verdict": "approve", "confidence": 0.7, "justification": "I agree"}
        ]
    }, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "heatmap" in data
    assert data["heatmap"]["B"] > data["heatmap"]["A"] # B disagreed with majority

def test_warroom_telemetry():
    """Feature: War room telemetry."""
    app.dependency_overrides[get_current_user] = mock_dev_auth

    response = client.get("/api/v1/warroom/telemetry", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "cpu_usage_percent" in data

    response = client.get("/api/v1/warroom/alerts", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_admin_dashboard():
    """Feature: Admin dashboard."""
    app.dependency_overrides[get_current_user] = mock_admin_auth

    response = client.get("/api/v1/admin/usage", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "total_tokens_24h" in response.json()

# --- Phase D: Secrets & Durable Store ---

def test_secrets_vault():
    """Feature: Secrets vault."""
    app.dependency_overrides[get_current_user] = mock_admin_auth

    # Store
    client.post("/api/v1/secrets", json={"key": "api-key", "value": "secret-123"}, headers=AUTH_HEADERS)
    
    # Get Token
    token_res = client.get("/api/v1/secrets/api-key/token", headers=AUTH_HEADERS)
    assert token_res.status_code == 200
    token = token_res.json()["token"]

    # Redeem
    redeem_res = client.post("/api/v1/secrets/redeem", params={"token": token}, headers=AUTH_HEADERS)
    assert redeem_res.status_code == 200
    assert redeem_res.json()["value"] == "secret-123"

@pytest.mark.asyncio
async def test_durable_file_store():
    """Feature: Durable file store."""
    test_file = "data/test_store.json"
    if os.path.exists(test_file):
        os.remove(test_file)
        
    store = JsonFileStore(test_file, Session, "session_id")
    
    sess = Session(
        session_id="durable-1",
        workspace_id="ws-1",
        owner_id="user-1",
        created_at=datetime.now(timezone.utc),
        last_activity_at=datetime.now(timezone.utc),
        status=SessionStatus.ACTIVE
    )
    
    await store.save(sess)
    
    # Reload from new store instance
    store2 = JsonFileStore(test_file, Session, "session_id")
    loaded = await store2.get("durable-1")
    
    assert loaded is not None
    assert loaded.session_id == "durable-1"
    
    # Clean up
    if os.path.exists(test_file):
        os.remove(test_file)
