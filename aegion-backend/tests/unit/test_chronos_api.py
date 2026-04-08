import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import get_current_user, AuthorityContext

# Mock auth
async def mock_get_current_user():
    return AuthorityContext(user_id="test_user", permissions=["admin"], role="admin")

app.dependency_overrides[get_current_user] = mock_get_current_user

import pytest_asyncio

@pytest_asyncio.fixture
async def client():
    headers = {
        "X-Aegion-Session": "test-session-123",
        "X-Aegion-Intent": "test-intent"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as ac:
        yield ac

@pytest.mark.asyncio
async def test_chronos_api_flow(client):
    # 1. Create ADR
    response = await client.post("/api/v1/chronos/adrs", json={
        "title": "API Test ADR",
        "context": "Context",
        "decision": "Decision",
        "rationale": "Rationale",
        "workspace_id": "ws_api"
    })
    assert response.status_code == 201
    data = response.json()
    adr_id = data["adr_id"]
    version = data["version"]
    assert version == 1
    
    # 2. Get ADR
    response = await client.get(f"/api/v1/chronos/adrs/{adr_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "API Test ADR"
    
    # 3. Accept ADR (Correct Version)
    response = await client.post(f"/api/v1/chronos/adrs/{adr_id}/accept", json={
        "expected_version": 1,
        "workspace_id": "ws_api"
    })
    assert response.status_code == 200
    new_version = response.json()["version"]
    assert new_version == 2
    
    # 4. Deprecate ADR (Stale Version) -> Conflict
    response = await client.post(f"/api/v1/chronos/adrs/{adr_id}/deprecate", json={
        "expected_version": 1, 
        "reason": "Obsolete",
        "workspace_id": "ws_api"
    })
    assert response.status_code == 409
    assert response.json()["detail"]["current_version"] == 2
    
    # 5. Deprecate ADR (Correct Version)
    response = await client.post(f"/api/v1/chronos/adrs/{adr_id}/deprecate", json={
        "expected_version": 2, 
        "reason": "Obsolete",
        "workspace_id": "ws_api"
    })
    assert response.status_code == 200
    assert response.json()["version"] == 3
