"""
In-memory RepoIntelligenceRepository for unit tests.

Avoids file-system I/O and provides predictable behavior.
"""

from typing import Optional, List
from app.services.repo_intelligence.contracts import RepoIntelligenceRepository
from app.domain.repo import WorkspaceScan, FileRecord, SymbolRecord
from app.domain.git_models import CommitRecord


class InMemoryRepoRepository(RepoIntelligenceRepository):
    """In-memory implementation of RepoIntelligenceRepository for testing."""

    def __init__(self):
        self._scans: dict[str, WorkspaceScan] = {}
        self._files: dict[str, FileRecord] = {}
        self._symbols: dict[str, SymbolRecord] = {}
        self._commits: dict[str, CommitRecord] = {}

    async def save_scan(self, scan: WorkspaceScan) -> None:
        self._scans[scan.scan_id] = scan

    async def get_scan(self, scan_id: str) -> Optional[WorkspaceScan]:
        return self._scans.get(scan_id)

    async def list_scans(self, workspace_id: str) -> List[WorkspaceScan]:
        scans = [s for s in self._scans.values() if s.workspace_id == workspace_id]
        return sorted(scans, key=lambda s: s.start_time, reverse=True)

    async def save_file_record(self, record: FileRecord) -> None:
        self._files[record.file_path] = record

    async def get_file_record(self, file_path: str) -> Optional[FileRecord]:
        return self._files.get(file_path)

    async def save_symbol(self, symbol: SymbolRecord) -> None:
        self._symbols[symbol.symbol_id] = symbol

    async def search_symbols(self, query: str, limit: int = 10) -> List[SymbolRecord]:
        q = query.lower()
        results = [s for s in self._symbols.values() if q in s.name.lower()]
        return results[:limit]

    async def save_commit(self, commit: CommitRecord) -> None:
        self._commits[commit.sha] = commit

    async def get_commits(self, limit: int = 100) -> List[CommitRecord]:
        commits = sorted(self._commits.values(), key=lambda c: c.timestamp, reverse=True)
        return commits[:limit]
