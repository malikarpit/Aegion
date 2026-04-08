import pytest
import shutil
from pathlib import Path
from app.services.chronos.timeline import ArchitectureTimelineService
from app.adapters.persistence.event_store import FileEventStore
from app.contracts.adr import ADRStatus

@pytest.fixture
def temp_store(tmp_path):
    # Setup
    file_path = tmp_path / "events.jsonl"
    store = FileEventStore(str(file_path))
    yield store, file_path
    # Teardown handled by tmp_path

@pytest.mark.asyncio
async def test_timeline_persistence_and_hydration(temp_store):
    store, file_path = temp_store
    
    # 1. Start Service A, Create ADR
    service_a = ArchitectureTimelineService(store)
    adr_1 = await service_a.create_adr(
        title="Use Postgres",
        context="Need DB",
        decision="Postgres",
        rationale="Robust",
        created_by="arpit",
        workspace_id="ws_1"
    )
    
    # Verify in-memory state of A
    assert len(await service_a.list_adrs()) == 1
    assert (await service_a.get_adr(adr_1.adr_id)).title == "Use Postgres"

    # 2. Simulate complete restart (New Service Instance, Same File Store)
    new_store_instance = FileEventStore(str(file_path))
    service_b = ArchitectureTimelineService(new_store_instance)
    
    # Verify B is empty before hydration
    assert len(await service_b.list_adrs()) == 0
    
    # 3. Hydrate B
    await service_b.hydrate("ws_1")
    
    # 4. Verify B recovered state
    adrs = await service_b.list_adrs()
    assert len(adrs) == 1
    assert adrs[0].adr_id == adr_1.adr_id
    assert adrs[0].title == "Use Postgres"

@pytest.mark.asyncio
async def test_supersession_recovery(temp_store):
    store, _ = temp_store
    service = ArchitectureTimelineService(store)
    
    # Create V1
    v1 = await service.create_adr(
        title="V1", context="...", decision="...", rationale="...", 
        created_by="u1", workspace_id="ws_1"
    )
    
    # Create V2 superseding V1
    v2 = await service.create_adr(
        title="V2", context="...", decision="...", rationale="...", 
        created_by="u1", workspace_id="ws_1",
        supersedes=v1.adr_id
    )
    
    # Verify V1 status update in memory
    assert (await service.get_adr(v1.adr_id)).status == ADRStatus.SUPERSEDED
    
    # Restart & Hydrate
    new_service = ArchitectureTimelineService(store)
    await new_service.hydrate("ws_1")
    
    # Verify Supersession Logic Replayed
    v1_recovered = await new_service.get_adr(v1.adr_id)
    assert v1_recovered.status == ADRStatus.SUPERSEDED
    assert v1_recovered.superseded_by == v2.adr_id
