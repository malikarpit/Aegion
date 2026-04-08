import pytest
import os
import json
from pathlib import Path
from app.domain.events import Event, EventMetadata
from app.adapters.persistence.event_store import FileEventStore, InMemoryEventStore

@pytest.fixture
def temp_file_store(tmp_path):
    file_path = tmp_path / "events.jsonl"
    return FileEventStore(str(file_path)), file_path

@pytest.mark.asyncio
async def test_in_memory_store():
    store = InMemoryEventStore()
    event = Event(
        event_type="test.event",
        workspace_id="ws_1",
        data={"foo": "bar"},
        metadata=EventMetadata(
            correlation_id="corr_1",
            actor_id="user|test"
        )
    )
    await store.append(event)
    events = await store.get_all("ws_1")
    assert len(events) == 1
    assert events[0].event_id == event.event_id

@pytest.mark.asyncio
async def test_file_store_persistence(temp_file_store):
    store, file_path = temp_file_store
    
    # Write event
    event1 = Event(
        event_type="test.persist",
        workspace_id="ws_1",
        data={"val": 1},
        metadata=EventMetadata(correlation_id="c1", actor_id="u1")
    )
    await store.append(event1)
    
    # Simulate restart by creating new instance pointing to same file
    new_store = FileEventStore(str(file_path))
    events = await new_store.get_all("ws_1")
    
    assert len(events) == 1
    assert events[0].event_id == event1.event_id
    assert events[0].data["val"] == 1

@pytest.mark.asyncio
async def test_file_store_isolation(temp_file_store):
    store, _ = temp_file_store
    
    e1 = Event(event_type="t1", workspace_id="ws_A", data={}, metadata=EventMetadata(correlation_id="1", actor_id="u"))
    e2 = Event(event_type="t2", workspace_id="ws_B", data={}, metadata=EventMetadata(correlation_id="2", actor_id="u"))
    
    await store.append(e1)
    await store.append(e2)
    
    events_a = await store.get_all("ws_A")
    assert len(events_a) == 1
    assert events_a[0].workspace_id == "ws_A"
    
    events_b = await store.get_all("ws_B")
    assert len(events_b) == 1
    
    events_all = await store.get_all()
    assert len(events_all) == 2
