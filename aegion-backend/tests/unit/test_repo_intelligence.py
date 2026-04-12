import pytest
import asyncio
from app.domain.repo import FileRecord, SymbolRecord
from app.services.repo_intelligence.service import get_repo_service, RepoIntelligenceService
from app.adapters.persistence.event_store import InMemoryEventStore
from tests.helpers.in_memory_repo import InMemoryRepoRepository

# Reset singleton before test
import app.services.repo_intelligence.service as _svc
_svc._repo_service = None

@pytest.mark.asyncio
async def test_repo_intelligence_contract():
    """Verify core service contracts and entity serialization."""
    
    # 1. Setup Service
    store = InMemoryEventStore()
    repo = InMemoryRepoRepository()
    service = get_repo_service(store, repository=repo)
    
    # 2. Start Scan (runs in background)
    scan_id = await service.start_scan("test_ws")
    assert scan_id is not None
    
    # Wait for background task to complete
    await asyncio.sleep(1.0)
    
    # 3. Verify Scan Status
    scan = await service.get_scan_status(scan_id)
    assert scan.scan_id == scan_id
    assert scan.status in ["pending", "completed"]
    assert scan.workspace_id == "test_ws"
    
    # 4. Verify Event Emission
    events = await store.get_all("test_ws")
    # It might be 1 (started) or 2 (started + completed) depending on speed
    assert len(events) >= 1
    assert events[0].event_type == "repo.scan_started"
    assert events[0].data["scan_id"] == scan_id
    
    # 5. Verify Entity Validation
    file_record = FileRecord(
        file_path="app/main.py",
        content_hash="abc123hash",
        language="python",
        size_bytes=1024,
        last_modified="2024-01-01T00:00:00Z"
    )
    assert file_record.file_path == "app/main.py"
