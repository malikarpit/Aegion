from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from datetime import datetime
from ...domain.repo import WorkspaceScan, FileRecord, SymbolRecord
from ...domain.git_models import CommitRecord

class RepoIntelligenceProvider(ABC):
    """Abstract contract for Repo Intelligence Service."""

    @abstractmethod
    async def start_scan(self, workspace_id: str) -> str:
        """
        Start a full workspace scan.
        Returns: scan_id
        """
        pass

    @abstractmethod
    async def get_scan_status(self, scan_id: str) -> Optional[WorkspaceScan]:
        """Get status of a specific scan."""
        pass

    @abstractmethod
    async def get_latest_scan(self, workspace_id: str) -> Optional[WorkspaceScan]:
        """Get the most recent scan for a workspace."""
        pass

    @abstractmethod
    async def query_symbols(self, query: str, workspace_id: str, limit: int = 10) -> List[SymbolRecord]:
        """Search for symbols by name."""
        pass

    @abstractmethod
    async def get_file_record(self, file_path: str, workspace_id: str) -> Optional[FileRecord]:
        """Get detailed record for a file."""
        pass

    @abstractmethod
    async def get_file_lineage(self, file_path: str, workspace_id: str, limit: int = 10) -> List[CommitRecord]:
        """Get commit history for a file."""
        pass

class RepoIntelligenceRepository(ABC):
    """
    Persistence adapter for Repo Intelligence data.
    """
    @abstractmethod
    async def save_scan(self, scan: WorkspaceScan) -> None:
        pass
        
    @abstractmethod
    async def get_scan(self, scan_id: str) -> Optional[WorkspaceScan]:
        pass
        
    @abstractmethod
    async def list_scans(self, workspace_id: str) -> List[WorkspaceScan]:
        pass
        
    @abstractmethod
    async def save_file_record(self, record: FileRecord) -> None:
        pass
        
    @abstractmethod
    async def get_file_record(self, file_path: str) -> Optional[FileRecord]:
        pass
        
    @abstractmethod
    async def save_symbol(self, symbol: SymbolRecord) -> None:
        pass
        
    @abstractmethod
    async def search_symbols(self, query: str, limit: int = 10) -> List[SymbolRecord]:
        pass
        
    @abstractmethod
    async def save_commit(self, commit: CommitRecord) -> None:
        pass
        
    @abstractmethod
    async def get_commits(self, limit: int = 100) -> List[CommitRecord]:
        pass

