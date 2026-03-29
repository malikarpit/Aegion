import json
import os
import hashlib
from typing import Optional, List, Dict, Any
from pathlib import Path
from pydantic import BaseModel

from ...core.logging import logger
from ...domain.repo import WorkspaceScan, FileRecord, SymbolRecord
from ...domain.git_models import CommitRecord
from .contracts import RepoIntelligenceRepository

class FileRepoIntelligenceRepository(RepoIntelligenceRepository):
    """
    File-system persistence for Repo Intelligence.
    Structure:
    .aegion/intelligence/
        scans/
            {scan_id}.json
        files/
            {path_hash}.json
        symbols/
            {symbol_id}.json
        commits/
            {sha}.json
    """
    
    def __init__(self, data_dir: str):
        self.root = Path(data_dir)
        self.scans_dir = self.root / "scans"
        self.files_dir = self.root / "files"
        self.symbols_dir = self.root / "symbols"
        self.commits_dir = self.root / "commits"
        self._ensure_dirs()
        
    def _ensure_dirs(self):
        for d in [self.scans_dir, self.files_dir, self.symbols_dir, self.commits_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _hash_path(self, path: str) -> str:
        return hashlib.md5(path.encode()).hexdigest()

    async def save_scan(self, scan: WorkspaceScan) -> None:
        path = self.scans_dir / f"{scan.scan_id}.json"
        with open(path, "w") as f:
            f.write(scan.model_dump_json(indent=2))

    async def get_scan(self, scan_id: str) -> Optional[WorkspaceScan]:
        path = self.scans_dir / f"{scan_id}.json"
        if not path.exists():
            return None
        with open(path, "r") as f:
            return WorkspaceScan.model_validate_json(f.read())

    async def list_scans(self, workspace_id: str) -> List[WorkspaceScan]:
        scans = []
        for p in self.scans_dir.glob("*.json"):
            try:
                with open(p, "r") as f:
                    s = WorkspaceScan.model_validate_json(f.read())
                    if s.workspace_id == workspace_id:
                        scans.append(s)
            except Exception:
                continue
        return sorted(scans, key=lambda s: s.start_time, reverse=True)

    async def save_file_record(self, record: FileRecord) -> None:
        path = self.files_dir / f"{self._hash_path(record.file_path)}.json"
        with open(path, "w") as f:
            f.write(record.model_dump_json(indent=2))

    async def get_file_record(self, file_path: str) -> Optional[FileRecord]:
        path = self.files_dir / f"{self._hash_path(file_path)}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                return FileRecord.model_validate_json(f.read())
        except Exception:
            return None

    async def save_symbol(self, symbol: SymbolRecord) -> None:
        # Use symbol_id (uuid) or hash name? SymbolRecord has symbol_id.
        path = self.symbols_dir / f"{symbol.symbol_id}.json"
        with open(path, "w") as f:
            f.write(symbol.model_dump_json(indent=2))

    async def search_symbols(self, query: str, limit: int = 10) -> List[SymbolRecord]:
        # Inefficient scan for File impl.
        # Acceptable for local dev.
        results = []
        query = query.lower()
        count = 0
        
        # Sort by mtime to search recent? No.
        # Just scan until limit.
        for p in self.symbols_dir.glob("*.json"):
            if count >= limit:
                break
            try:
                with open(p, "r") as f:
                    # Optimize: Read partial? No, JSON.
                    # Load all symbols effectively. 
                    # If this is too slow, we need local index.
                    # For V1 remediation, this is acceptable.
                    s = SymbolRecord.model_validate_json(f.read())
                    if query in s.name.lower():
                        results.append(s)
                        count += 1
            except Exception:
                continue
        return results

    async def save_commit(self, commit: CommitRecord) -> None:
        path = self.commits_dir / f"{commit.sha}.json"
        with open(path, "w") as f:
            f.write(commit.model_dump_json(indent=2))

    async def get_commits(self, limit: int = 100) -> List[CommitRecord]:
        commits = []
        # Sort by mtime works if mined sequentially? No.
        # We accept unsorted or read-all-and-sort.
        # Read-all is strictly necessary for correct sorting.
        # Limit to 1000 files check?
        files = list(self.commits_dir.glob("*.json"))
        # Sort by filename might map to time? No, SHA.
        
        # Performance tradeoff: Read all.
        loaded = []
        for p in files[:1000]: # Cap at 1000 for safety
            try:
                with open(p, "r") as f:
                    loaded.append(CommitRecord.model_validate_json(f.read()))
            except (json.JSONDecodeError, ValueError, OSError):
                continue
        
        loaded.sort(key=lambda c: c.timestamp, reverse=True)
        return loaded[:limit]
