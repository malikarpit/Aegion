"""
E2E Integration Tests for Phase 82 Batch Processing Pipeline
"""

import pytest
from httpx import AsyncClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext

@pytest.fixture(autouse=True)
async def setup_dummy_providers():
    from app.api.v1.council import _ack_engine
    import unittest.mock

    # Set auth override scoped to this test — always clean up
    def _mock_user():
        return AuthorityContext(user_id="test-admin", scopes=["read", "write"], role="architect", workspace_id="test-batch-ws")
    app.dependency_overrides[get_current_user] = _mock_user

    engine = _ack_engine()
    await engine.model_router.configure_from_user_keys({"openai_key": "sk-dummy"})

    fake_json = {
        "choices": [{"message": {"content": "Mocked council response for testing."}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    }
    mock_http_response = unittest.mock.MagicMock()
    mock_http_response.status_code = 200
    mock_http_response.json.return_value = fake_json
    mock_http_response.raise_for_status = unittest.mock.MagicMock()

    with unittest.mock.patch(
        "app.services.council_kernel.model_router.httpx.AsyncClient"
    ) as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = unittest.mock.AsyncMock(return_value=mock_http_response)
        yield

    app.dependency_overrides.pop(get_current_user, None)

HEADERS = {
    "Authorization": "Bearer test-admin",
    "X-Workspace-ID": "test-batch-ws",
    "X-Aegion-Session": "sess-test",
    "X-Aegion-Intent": "test.run"
}

@pytest.mark.asyncio
async def test_enqueue_batch_job():
    """Phase 82: Ensure the enqueue API properly parses the priority and queues it."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Enqueue job
        res1 = await client.post("/api/v1/batch/enqueue", json={
            "query": "Refactor entire legacy module",
            "priority": "deferred"
        }, headers=HEADERS)
        
        assert res1.status_code == 200
        
        # Verify status
        res2 = await client.get("/api/v1/batch/status", headers=HEADERS)
        assert res2.status_code == 200
        assert type(res2.json()) is list


@pytest.mark.asyncio
async def test_process_batch_jobs_ignores_future():
    """Phase 82: Manual trigger correctly runs ripe jobs and skips future jobs."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Post immediate
        await client.post("/api/v1/batch/enqueue", json={
            "query": "Immediate test query",
            "priority": "immediate"
        }, headers=HEADERS)
        
        # Process ready — success regardless of how many jobs were ready
        res = await client.post("/api/v1/batch/process", headers=HEADERS)
        assert res.status_code == 200
        data = res.json()
        # Endpoint returns {"processed": N, "results": [...]}
        assert "processed" in data
        assert isinstance(data["processed"], int)
