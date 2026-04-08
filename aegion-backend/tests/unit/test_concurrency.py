import pytest
from app.services.chronos.timeline import ArchitectureTimelineService
from app.adapters.persistence.event_store import InMemoryEventStore
from app.core.errors import ConcurrencyError
from app.contracts.adr import ADRStatus

@pytest.fixture
def service():
    store = InMemoryEventStore()
    return ArchitectureTimelineService(store)

@pytest.mark.asyncio
async def test_optimistic_concurrency(service):
    # 1. Create ADR (v1)
    adr = await service.create_adr(
        title="Test OCC",
        context="Context",
        decision="Decision",
        rationale="Rationale",
        created_by="tester",
        workspace_id="ws_1"
    )
    assert adr.version == 1

    # 2. Actor A accepts the ADR (v1 -> v2)
    # They pass expected_version=1, which matches current.
    updated_adr = await service.accept_adr(
        adr_id=adr.adr_id,
        accepted_by="actor_a",
        workspace_id="ws_1",
        expected_version=1
    )
    assert updated_adr.status == ADRStatus.ACCEPTED
    assert updated_adr.version == 2

    # 3. Actor B tries to deprecate the ADR, but they still have v1 in mind.
    # They pass expected_version=1.
    # Current version is 2.
    # Should raise ConcurrencyError.
    with pytest.raises(ConcurrencyError) as exc_info:
        await service.deprecate_adr(
            adr_id=adr.adr_id,
            deprecated_by="actor_b",
            workspace_id="ws_1",
            reason="Obsolete",
            expected_version=1
        )
    
    assert exc_info.value.current_version == 2
    assert exc_info.value.expected_version == 1

    # 4. Actor B refreshes and retries with correct version (v2 -> v3)
    final_adr = await service.deprecate_adr(
        adr_id=adr.adr_id,
        deprecated_by="actor_b",
        workspace_id="ws_1",
        reason="Obsolete",
        expected_version=2
    )
    assert final_adr.status == ADRStatus.DEPRECATED
    assert final_adr.version == 3
