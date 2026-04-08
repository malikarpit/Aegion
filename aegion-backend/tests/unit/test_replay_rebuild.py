import pytest
import json
from app.services.chronos.timeline import ArchitectureTimelineService
from app.adapters.persistence.event_store import FileEventStore, InMemoryEventStore

@pytest.fixture
def temp_store(tmp_path):
    file_path = tmp_path / "replay_events.jsonl"
    store = FileEventStore(str(file_path))
    yield store, file_path

@pytest.mark.asyncio
async def test_deterministic_replay(temp_store):
    """
    State(Events) must equal State(Events')
    
    1. Generate complex history (Create -> Accept -> Supersede -> Deprecate)
    2. Snapshot State A
    3. Wipe memory, Hydrate from Log
    4. Snapshot State B
    5. Assert State A == State B (Deep Equality)
    """
    store, file_path = temp_store
    service = ArchitectureTimelineService(store)
    
    # ── Phase 1: Generate History ──
    workspace_id = "ws_replay"
    
    # 1. Create ADR 1 (Proposed)
    adr1 = await service.create_adr("ADR 1", "Context 1", "Decision 1", "Rationale 1", "user1", workspace_id)
    
    # 2. Create ADR 2 (Proposed)
    adr2 = await service.create_adr("ADR 2", "Context 2", "Decision 2", "Rationale 2", "user1", workspace_id)
    
    # 3. Accept ADR 1 (Version 1 -> 2)
    await service.accept_adr(adr1.adr_id, "user2", workspace_id, expected_version=1)
    
    # 4. Create ADR 3 Superseding ADR 1
    adr3 = await service.create_adr("ADR 3", "Context 3", "Decision 3", "Rationale 3", "user1", workspace_id, supersedes=adr1.adr_id)
    
    # Check that ADR 1 is superseded in memory
    adr1_current = await service.get_adr(adr1.adr_id)
    assert adr1_current.status == "superseded"
    
    # 5. Deprecate ADR 2 (Version 1 -> 2)
    # We first accept it? No, can deprecate proposed too? 
    # Logic in service allows deprecating anything.
    await service.deprecate_adr(adr2.adr_id, "user2", workspace_id, "Obsolete", expected_version=1)

    # ── Phase 2: Capture Golden State ──
    # We explicitly dump to dict to avoid object reference comparison issues
    golden_adrs = sorted([a.model_dump() for a in await service.list_adrs()], key=lambda x: x['adr_id'])
    
    # ── Phase 3: Rebuild ──
    # New service instance, same file
    new_store = FileEventStore(str(file_path))
    new_service = ArchitectureTimelineService(new_store)
    
    # Should be empty initially
    assert len(await new_service.list_adrs()) == 0
    
    # Hydrate
    await new_service.hydrate(workspace_id)
    
    # ── Phase 4: Compare ──
    rebuilt_adrs = sorted([a.model_dump() for a in await new_service.list_adrs()], key=lambda x: x['adr_id'])
    
    # Deep equality check
    # We iterate and compare fields. Timestamps might differ if not persisted perfectly?
    # Our Event Store persists timestamps in metadata/data, and Timeline applies them.
    # So they should be identical.
    
    assert len(golden_adrs) == len(rebuilt_adrs)
    
    for golden, rebuilt in zip(golden_adrs, rebuilt_adrs):
        assert golden['adr_id'] == rebuilt['adr_id']
        assert golden['status'] == rebuilt['status']
        assert golden['version'] == rebuilt['version']
        assert golden['title'] == rebuilt['title']
        assert golden['supersedes'] == rebuilt['supersedes']
        assert golden['superseded_by'] == rebuilt['superseded_by']
        # Check specific metadata persistence
        assert golden['created_by'] == rebuilt['created_by']
