
import pytest
import datetime
from app.services.governance_conflict import GovernanceConflictService
from app.adapters.persistence.event_store import InMemoryEventStore
from app.models.conflict import Conflict, ConflictStatus

@pytest.mark.asyncio
async def test_conflict_persistence_and_hydration():
    """Verify conflicts are persisted to event store and rehydrated."""
    
    # 1. Setup
    workspace_id = "ws-test-persistence"
    event_store = InMemoryEventStore()
    service = GovernanceConflictService(event_store=event_store)
    
    # 2. Detect a conflict
    # Triggers 'import_check' rule by having "import sqlalchemy" in content
    file_path = "app/controllers/legacy.py"
    content = "import sqlalchemy\n\ndef check(): pass"
    
    conflicts = await service.detect_conflicts(workspace_id, file_path, content)
    assert len(conflicts) == 1
    original_conflict_id = conflicts[0].conflict_id
    
    # 3. Verify event emitted
    events = await event_store.get_all(workspace_id)
    assert len(events) >= 1
    assert events[0].event_type == "conflict.detected"
    assert events[0].data["conflict_id"] == original_conflict_id
    
    # 4. Resolve the conflict
    # We need to loop manually to simulate async resolution persistence if it was fire-and-forget
    # But since InMemoryStore append is async and we called create_task, we might need a small sleep
    # However, create_task might not run immediately in test loop without yield.
    # The service code uses: loop.create_task(self._event_store.append(...))
    # We'll see if it runs.
    
    service.resolve_conflict(original_conflict_id, "user-123")
    
    import asyncio
    await asyncio.sleep(0.1) # Let background persistence task run
    
    # 5. Verify resolve event
    events = await event_store.get_all(workspace_id)
    assert len(events) >= 2 # detected + resolved
    # Find the resolved event
    resolved_events = [e for e in events if e.event_type == "conflict.resolved"]
    assert len(resolved_events) == 1
    assert resolved_events[0].data["conflict_id"] == original_conflict_id
    assert resolved_events[0].data["resolved_by"] == "user-123"
    
    # 6. Hydrate a fresh service
    new_service = GovernanceConflictService(event_store=event_store)
    # Check it's empty
    assert len(new_service.get_active_conflicts(workspace_id)) == 0
    # Also internal list should be empty
    assert len(new_service._conflicts) == 0
    
    # Hydrate
    await new_service.hydrate(workspace_id)
    
    # 7. Verify state restored
    # The conflict was resolved, so status should be RESOLVED
    # get_active_conflicts filters for OPEN, so it should return empty
    active = new_service.get_active_conflicts(workspace_id)
    assert len(active) == 0
    
    # Check internal list for the resolved conflict
    all_conflicts = new_service._conflicts
    assert len(all_conflicts) == 1
    restored = all_conflicts[0]
    assert restored.conflict_id == original_conflict_id
    assert restored.status == ConflictStatus.RESOLVED
    assert restored.resolved_by == "user-123"
    
