import pytest
import os
from app.domain.repo import FileRecord, SymbolRecord, ContextPackage
from app.domain.git_models import CommitRecord
from app.services.repo_intelligence.service import RepoIntelligenceService
from app.adapters.persistence.event_store import InMemoryEventStore
from tests.helpers.in_memory_repo import InMemoryRepoRepository
from datetime import datetime, timezone
import asyncio

@pytest.fixture
async def mock_repo_service():
    store = InMemoryEventStore()
    repo = InMemoryRepoRepository()
    service = RepoIntelligenceService(store, repo, root_path=".")
    
    # Pre-populate dummy data via repository
    symbol = SymbolRecord(symbol_id="s1", name="ClassA", type="class", file_path="a.py", line_start=1, line_end=5)
    file_record = FileRecord(
        file_path="a.py", content_hash="h1", language="python", size_bytes=10, 
        last_modified=datetime.now(timezone.utc), loc=5,
        symbols=[symbol]
    )
    commit = CommitRecord(
        sha="c1", message="feat: add a", author_name="Dev", author_email="d@example.com",
        timestamp=datetime.now(timezone.utc), changed_files=["a.py"]
    )

    await repo.save_file_record(file_record)
    await repo.save_symbol(symbol)
    await repo.save_commit(commit)
    
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
