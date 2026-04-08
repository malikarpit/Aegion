import pytest
import os
from app.domain.repo import FileRecord, SymbolRecord, ContextPackage
from app.domain.git_models import CommitRecord
from app.services.repo_intelligence.service import get_repo_service
from app.adapters.persistence.event_store import InMemoryEventStore
from datetime import datetime, timezone

@pytest.fixture
def mock_repo_service():
    store = InMemoryEventStore()
    service = get_repo_service(store, root_path=".") # Use current dir just to init scanner
    
    # Pre-populate dummy data directly into service
    service._files["a.py"] = FileRecord(
        file_path="a.py", content_hash="h1", language="python", size_bytes=10, 
        last_modified=datetime.now(timezone.utc), loc=5,
        symbols=[
            SymbolRecord(symbol_id="s1", name="ClassA", type="class", file_path="a.py", line_start=1, line_end=5)
        ]
    )
    
    service._commits["c1"] = CommitRecord(
        sha="c1", message="feat: add a", author_name="Dev", author_email="d@example.com",
        timestamp=datetime.now(timezone.utc), changed_files=["a.py"]
    )
    
    return service

@pytest.mark.asyncio
async def test_build_context_package(mock_repo_service):
    service = mock_repo_service
    
    pkg = await service.build_context(["a.py"], "test_ws")
    
    assert isinstance(pkg, ContextPackage)
    assert pkg.workspace_id == "test_ws"
    assert len(pkg.target_files) == 1
    assert pkg.target_files[0] == "a.py"
    
    # Check Records
    assert len(pkg.file_records) == 1
    assert pkg.file_records[0].file_path == "a.py"
    
    # Check Symbols
    assert len(pkg.related_symbols) == 1
    assert pkg.related_symbols[0].name == "ClassA"
    
    # Check Commits
    assert len(pkg.relevant_commits) == 1
    assert pkg.relevant_commits[0].message == "feat: add a"

@pytest.mark.asyncio
async def test_build_context_missing_file(mock_repo_service):
    service = mock_repo_service
    pkg = await service.build_context(["missing.py"], "test_ws")
    
    assert len(pkg.file_records) == 0
    assert len(pkg.relevant_commits) == 0
