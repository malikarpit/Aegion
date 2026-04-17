import uuid
import hashlib
from typing import Dict, List, Optional, Set, Any
from datetime import datetime

from ...core.time import TimeAuthority
from ...core.logging import logger
from ...core.metrics import RepoMetrics
from ...domain.events import Event, EventMetadata
from ...domain.repo import WorkspaceScan, FileRecord, SymbolRecord, ContextPackage
from ...domain.git_models import CommitRecord
from ...adapters.persistence.event_store import EventStoreAdapter, InMemoryEventStore
from .contracts import RepoIntelligenceProvider, RepoIntelligenceRepository
from .scanner import RepoScanner
from .git_miner import GitMiner
from .analyzers.python import PythonAnalyzer
from .analyzers.typescript import TypeScriptAnalyzer
from ...domain.repo import FileRecord, SymbolRecord, WorkspaceScan, ContextPackage
from ...domain.git_models import CommitRecord



class RepoIntelligenceService(RepoIntelligenceProvider):
    """
    Core service for managing repository intelligence.
    Orchestrates scanning, indexing, and querying.
    """

    def __init__(self, event_store: EventStoreAdapter, repository: RepoIntelligenceRepository, root_path: str = "."):
        self.event_store = event_store
        self.repository = repository
        self.root_path = root_path
        
        # Tools
        self._git_miner = GitMiner(root_path)

        # Analyzers
        self._analyzers = {
            "python": PythonAnalyzer(),
            "typescript": TypeScriptAnalyzer(),
            "javascript": TypeScriptAnalyzer(), # Re-use TS analyzer
        }

    async def start_scan(self, workspace_id: str) -> str:
        """Start a new scan."""
        scan_id = str(uuid.uuid4())
        scan = WorkspaceScan(
            scan_id=scan_id,
            workspace_id=workspace_id,
            start_time=TimeAuthority.now_dt(),
            status="in_progress"
        )
        await self.repository.save_scan(scan)
        
        # Emit started event
        await self._emit_event("repo.scan_started", workspace_id, scan.model_dump(), scan_id)
        
        logger.info(f"🚀 Scan {scan_id} started for workspace {workspace_id}")
        
        # Run scan as a background task (non-blocking)
        import asyncio
        task = asyncio.create_task(self._run_scan(scan_id, workspace_id))
        task.add_done_callback(lambda t: self._on_scan_done(t, scan_id))
        
        return scan_id

    def _on_scan_done(self, task, scan_id: str):
        """Callback when background scan completes or fails."""
        if task.exception():
            logger.error(f"Background scan {scan_id} failed: {task.exception()}")
            # We should probably update scan status to failed here if not already
        else:
            logger.info(f"Background scan {scan_id} completed successfully")

    async def _run_scan(self, scan_id: str, workspace_id: str):
        """Execute the scan logic."""
        # Reload scan to ensure freshness
        scan = await self.repository.get_scan(scan_id)
        if not scan:
            logger.error(f"Scan {scan_id} not found during execution")
            return

        scanner = RepoScanner(self.root_path) 
        
        files_count = 0
        symbols_count = 0
        commits_count = 0
        
        try:
            # 1. File Scanning
            async for file_record in scanner.scan_workspace():
                # Store file
                await self.repository.save_file_record(file_record)
                files_count += 1
                
                # Analyze symbols
                analyzer = self._analyzers.get(file_record.language)
                if analyzer:
                    try:
                        # Need to read file content again or pass it?
                        # Scanner yields record. Content is not in record?
                        # FileRecord doesn't store content typically.
                        # We read it here.
                        with open(file_record.file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        symbols = analyzer.extract_symbols(content, file_record.file_path)
                        # We can update file_record with symbols or store separately
                        file_record.symbols = symbols
                        await self.repository.save_file_record(file_record) # Update with symbols
                        
                        for sym in symbols:
                            await self.repository.save_symbol(sym)
                            symbols_count += 1
                            
                    except Exception as e:
                        logger.warning(f"Analysis failed for {file_record.file_path}: {e}")
            
            # 2. Git Mining (Week 3)
            if self._git_miner:
                async for commit in self._git_miner.mine_history():
                    await self.repository.save_commit(commit)
                    commits_count += 1
                scan.commits_mined = commits_count
            
            # Update scan status
            scan.status = "completed"
            scan.end_time = TimeAuthority.now_dt()
            scan.files_scanned = files_count
            scan.total_symbols = symbols_count

            duration = (scan.end_time - scan.start_time).total_seconds() * 1000
            RepoMetrics.scan_duration(duration, workspace_id, scan.files_scanned)
            
            await self.repository.save_scan(scan)
            
            await self._emit_event("repo.scan_completed", workspace_id, scan.model_dump(), scan_id)
            logger.info(f"Scan {scan_id} completed", extra={"files": scan.files_scanned, "commits": commits_count})

        except Exception as e:
            logger.error(f"Scan failed: {e}")
            scan.status = "failed"
            scan.errors.append(str(e))
            scan.end_time = TimeAuthority.now_dt()
            await self.repository.save_scan(scan)


    async def get_scan_status(self, scan_id: str) -> Optional[WorkspaceScan]:
        return await self.repository.get_scan(scan_id)

    async def get_latest_scan(self, workspace_id: str) -> Optional[WorkspaceScan]:
        scans = await self.repository.list_scans(workspace_id)
        if not scans:
            return None
        return scans[0] # List is sorted desc

    async def query_symbols(self, query: str, workspace_id: str, limit: int = 10) -> List[SymbolRecord]:
        return await self.repository.search_symbols(query, limit)

    async def get_file_record(self, file_path: str, workspace_id: str) -> Optional[FileRecord]:
        return await self.repository.get_file_record(file_path)

    async def get_recent_commits(self, limit: int = 10) -> List[CommitRecord]:
        """Return the most recent commits."""
        return await self.repository.get_commits(limit)

    async def get_file_lineage(self, file_path: str, workspace_id: str, limit: int = 10) -> List[CommitRecord]:
        """
        Return commits that touched this file.
        In-efficient linear search over commits in repository.
        """
        # Fetch recent commits (up to reasonable limit for perf)
        commits = await self.repository.get_commits(limit=1000)
        
        matching_commits = []
        for commit in commits:
            if any(f.endswith(file_path) or file_path.endswith(f) for f in commit.changed_files):
                matching_commits.append(commit)
        
        # Sort by time desc
        matching_commits.sort(key=lambda c: c.timestamp, reverse=True)
        return matching_commits[:limit]

    async def build_context(self, files: List[str], workspace_id: str, max_history: int = 5) -> ContextPackage:
        """
        Builds a ContextPackage for the given files.
        Aggregates FileRecords, Symbols, and Lineage.
        """
        file_records = []
        all_symbols = []
        all_commits = []
        seen_commits = set()
        
        start_time = TimeAuthority.now_dt()
        
        for file_path in files:
            # Get File Record
            record = await self.get_file_record(file_path, workspace_id)
            if record:
                file_records.append(record)
                # Collect Symbols
                all_symbols.extend(record.symbols)
            
            # Get Lineage
            commits = await self.get_file_lineage(file_path, workspace_id, limit=max_history)
            for commit in commits:
                if commit.sha not in seen_commits:
                    all_commits.append(commit)
                    seen_commits.add(commit.sha)
        
        # Sort commits by time desc
        all_commits.sort(key=lambda c: c.timestamp, reverse=True)
        
        pkg = ContextPackage(
            workspace_id=workspace_id,
            generated_at=start_time,
            target_files=files,
            file_records=file_records,
            related_symbols=all_symbols,
            relevant_commits=all_commits
        )
        
        duration = (TimeAuthority.now_dt() - start_time).total_seconds() * 1000
        # Approximate size of JSON payload
        size_bytes = len(pkg.model_dump_json())
        RepoMetrics.context_built(duration, workspace_id, len(files), size_bytes)
        
        return pkg

    async def get_top_contributors(self, workspace_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Identify top contributors based on mined commit history.
        """
        from collections import Counter
        
        commits = await self.repository.get_commits(limit=1000)
        if not commits:
            return []
            
        stats = Counter()
        for commit in commits:
            # Use email as primary key, fallback to name
            key = commit.author_email or commit.author_name
            stats[key] += 1
            
        # Format results
        result = []
        for author, count in stats.most_common(limit):
            # Find a commit example to get the name
            example = next((c for c in commits if (c.author_email == author or c.author_name == author)), None)
            name = example.author_name if example else "Unknown"
            
            result.append({
                "name": name,
                "email": author,
                "commits": count
            })
            
        return result

    async def _emit_event(self, event_type: str, workspace_id: str, data: Dict[str, Any], correlation_id: str):
        """Helper to emit events with consistent metadata."""
        event = Event(
            event_type=event_type,
            workspace_id=workspace_id,
            data=data,
            metadata=EventMetadata(
                actor_id="system",
                correlation_id=correlation_id
            )
        )
        await self.event_store.append(event)

    async def detect_branch_drift(self, workspace_id: str, base_branch: str = "main", head_branch: str = "HEAD") -> Dict[str, Any]:
        """
        Detects drift (file changes) between two branches.
        Used by GovernanceConflictService to identify high-risk changes.
        """
        if not self._git_miner:
            return {"error": "Git miner not available"}
            
        changes = self._git_miner.get_branch_diff(base_branch, head_branch)
        
        # Calculate stats
        stats = {
            "total_files_changed": len(changes),
            "added": len([c for c in changes if c['change_type'] == 'A']),
            "modified": len([c for c in changes if c['change_type'] == 'M']),
            "deleted": len([c for c in changes if c['change_type'] == 'D']),
            "renamed": len([c for c in changes if c['change_type'] == 'R']),
        }
        
        return {
            "workspace_id": workspace_id,
            "base_branch": base_branch,
            "head_branch": head_branch,
            "stats": stats,
            "changes": changes,
            "timestamp": TimeAuthority.now_iso()
        }

# Singleton
_repo_service: Optional[RepoIntelligenceService] = None

def get_repo_service(event_store: Optional[EventStoreAdapter] = None, repository: Optional[RepoIntelligenceRepository] = None, root_path: str = ".") -> RepoIntelligenceService:
    global _repo_service
    if _repo_service is None:
        if event_store is None:
            event_store = InMemoryEventStore()
        # Fallback to file-based repo if none provided
        if repository is None:
            from .repository import FileRepoIntelligenceRepository
            import tempfile, os
            data_dir = os.path.join(tempfile.gettempdir(), ".aegion", "intelligence")
            repository = FileRepoIntelligenceRepository(data_dir)
            
        _repo_service = RepoIntelligenceService(event_store, repository, root_path)
    return _repo_service
