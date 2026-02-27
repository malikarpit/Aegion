"""
Aegion Praxis Staleness Detection - Production Mode.

Phase 5: File Watchers, Git Hooks, and CI/CD Integration.
Monitors file system and VCS for changes that affect evidence validity.
"""

from typing import List, Dict, Any, Optional, Set, Callable
from datetime import timezone, datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import asyncio
import hashlib

from ...core.logging import logger


class ChangeSource(str, Enum):
    """Source of the detected change."""
    FILE_WATCHER = "file_watcher"
    GIT_HOOK = "git_hook"
    CI_CD_WEBHOOK = "ci_cd_webhook"
    MANUAL = "manual"


class ChangeType(str, Enum):
    """Type of file change."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class FileChange:
    """Detected file change."""
    path: str
    change_type: ChangeType
    source: ChangeSource
    timestamp: datetime
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StalenessAlert:
    """Alert for stale evidence/decisions."""
    alert_id: str
    triggered_at: datetime
    source: ChangeSource
    affected_files: List[str]
    affected_decision_ids: List[str]
    affected_evidence_ids: List[str]
    severity: str  # low, medium, high, critical
    message: str
    auto_resolved: bool = False


class FileWatcher:
    """
    Watches file system for changes.
    
    Uses polling strategy for cross-platform compatibility.
    Can be extended with inotify/FSEvents for better performance.
    """
    
    def __init__(
        self,
        watch_paths: List[str],
        poll_interval: float = 1.0,
        ignore_patterns: Optional[List[str]] = None
    ):
        self.watch_paths = [Path(p) for p in watch_paths]
        self.poll_interval = poll_interval
        self.ignore_patterns = ignore_patterns or [
            "*.pyc", "__pycache__", ".git", "node_modules",
            "*.log", "*.tmp", ".DS_Store"
        ]
        
        self._file_hashes: Dict[str, str] = {}
        self._running = False
        self._callbacks: List[Callable[[FileChange], None]] = []
    
    def on_change(self, callback: Callable[[FileChange], None]):
        """Register callback for file changes."""
        self._callbacks.append(callback)
    
    async def start(self):
        """Start watching files."""
        self._running = True
        
        # Initial scan
        await self._scan_all()
        
        # Start polling loop
        while self._running:
            await asyncio.sleep(self.poll_interval)
            await self._check_changes()
    
    async def stop(self):
        """Stop watching files."""
        self._running = False
    
    async def _scan_all(self):
        """Initial scan of all watched paths."""
        for watch_path in self.watch_paths:
            if not watch_path.exists():
                continue
            
            for path in watch_path.rglob("*"):
                if path.is_file() and not self._should_ignore(path):
                    try:
                        self._file_hashes[str(path)] = await self._hash_file(path)
                    except Exception as e:
                        logger.warning(f"Failed to hash {path}: {e}")
    
    async def _check_changes(self):
        """Check for file changes."""
        current_files: Set[str] = set()
        
        for watch_path in self.watch_paths:
            if not watch_path.exists():
                continue
            
            for path in watch_path.rglob("*"):
                if path.is_file() and not self._should_ignore(path):
                    str_path = str(path)
                    current_files.add(str_path)
                    
                    try:
                        new_hash = await self._hash_file(path)
                        old_hash = self._file_hashes.get(str_path)
                        
                        if old_hash is None:
                            # New file
                            change = FileChange(
                                path=str_path,
                                change_type=ChangeType.CREATED,
                                source=ChangeSource.FILE_WATCHER,
                                timestamp=datetime.now(timezone.utc),
                                new_hash=new_hash
                            )
                            self._file_hashes[str_path] = new_hash
                            await self._notify(change)
                            
                        elif new_hash != old_hash:
                            # Modified file
                            change = FileChange(
                                path=str_path,
                                change_type=ChangeType.MODIFIED,
                                source=ChangeSource.FILE_WATCHER,
                                timestamp=datetime.now(timezone.utc),
                                old_hash=old_hash,
                                new_hash=new_hash
                            )
                            self._file_hashes[str_path] = new_hash
                            await self._notify(change)
                            
                    except Exception as e:
                        logger.warning(f"Error checking {path}: {e}")
        
        # Check for deleted files
        deleted = set(self._file_hashes.keys()) - current_files
        for path in deleted:
            change = FileChange(
                path=path,
                change_type=ChangeType.DELETED,
                source=ChangeSource.FILE_WATCHER,
                timestamp=datetime.now(timezone.utc),
                old_hash=self._file_hashes.get(path)
            )
            del self._file_hashes[path]
            await self._notify(change)
    
    async def _hash_file(self, path: Path) -> str:
        """Calculate SHA256 hash of file."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _should_ignore(self, path: Path) -> bool:
        """Check if path matches ignore patterns."""
        str_path = str(path)
        for pattern in self.ignore_patterns:
            if pattern.startswith("*"):
                if str_path.endswith(pattern[1:]):
                    return True
            elif pattern in str_path:
                return True
        return False
    
    async def _notify(self, change: FileChange):
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(change)
                else:
                    callback(change)
            except Exception as e:
                logger.error(f"Callback error: {e}")


@dataclass
class GitHookPayload:
    """Payload from Git hook."""
    hook_type: str  # pre-commit, post-commit, post-merge, etc.
    branch: str
    commit_sha: Optional[str] = None
    author: Optional[str] = None
    message: Optional[str] = None
    files_changed: List[str] = field(default_factory=list)
    files_added: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)


class GitHookHandler:
    """
    Handles Git hook events for staleness detection.
    
    Install hooks with:
    ```
    #!/bin/bash
    curl -X POST http://localhost:8000/api/v1/staleness/git-hook \
      -H "Content-Type: application/json" \
      -d '{"hook_type":"post-commit","branch":"main",...}'
    ```
    """
    
    def __init__(self):
        self._callbacks: List[Callable[[List[FileChange]], None]] = []
    
    def on_changes(self, callback: Callable[[List[FileChange]], None]):
        """Register callback for git changes."""
        self._callbacks.append(callback)
    
    async def handle_hook(self, payload: GitHookPayload) -> List[FileChange]:
        """Process git hook payload."""
        changes = []
        now = datetime.now(timezone.utc)
        
        for path in payload.files_added:
            changes.append(FileChange(
                path=path,
                change_type=ChangeType.CREATED,
                source=ChangeSource.GIT_HOOK,
                timestamp=now,
                metadata={
                    "commit_sha": payload.commit_sha,
                    "author": payload.author,
                    "branch": payload.branch
                }
            ))
        
        for path in payload.files_changed:
            changes.append(FileChange(
                path=path,
                change_type=ChangeType.MODIFIED,
                source=ChangeSource.GIT_HOOK,
                timestamp=now,
                metadata={
                    "commit_sha": payload.commit_sha,
                    "author": payload.author,
                    "branch": payload.branch
                }
            ))
        
        for path in payload.files_deleted:
            changes.append(FileChange(
                path=path,
                change_type=ChangeType.DELETED,
                source=ChangeSource.GIT_HOOK,
                timestamp=now,
                metadata={
                    "commit_sha": payload.commit_sha,
                    "author": payload.author,
                    "branch": payload.branch
                }
            ))
        
        await self._notify(changes)
        return changes
    
    async def _notify(self, changes: List[FileChange]):
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(changes)
                else:
                    callback(changes)
            except Exception as e:
                logger.error(f"Git hook callback error: {e}")


@dataclass
class CICDWebhookPayload:
    """Payload from CI/CD webhook."""
    source: str  # github, gitlab, jenkins, etc.
    event_type: str  # push, pull_request, deployment, etc.
    repository: str
    branch: str
    commit_sha: Optional[str] = None
    build_status: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)


class CICDWebhookHandler:
    """Handles CI/CD webhook events."""
    
    def __init__(self):
        self._callbacks: List[Callable[[List[FileChange]], None]] = []
    
    def on_changes(self, callback: Callable[[List[FileChange]], None]):
        """Register callback for CI/CD changes."""
        self._callbacks.append(callback)
    
    async def handle_webhook(self, payload: CICDWebhookPayload) -> List[FileChange]:
        """Process CI/CD webhook payload."""
        changes = []
        now = datetime.now(timezone.utc)
        
        for path in payload.files_changed:
            changes.append(FileChange(
                path=path,
                change_type=ChangeType.MODIFIED,
                source=ChangeSource.CI_CD_WEBHOOK,
                timestamp=now,
                metadata={
                    "ci_source": payload.source,
                    "event_type": payload.event_type,
                    "commit_sha": payload.commit_sha,
                    "build_status": payload.build_status,
                    "repository": payload.repository,
                    "branch": payload.branch
                }
            ))
        
        await self._notify(changes)
        return changes
    
    async def _notify(self, changes: List[FileChange]):
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(changes)
                else:
                    callback(changes)
            except Exception as e:
                logger.error(f"CI/CD callback error: {e}")


class ProductionStalenessDetector:
    """
    Production staleness detection service.
    
    Integrates file watcher, git hooks, and CI/CD webhooks
    to detect when evidence becomes stale.
    """
    
    def __init__(
        self,
        evidence_path_resolver: Optional[Callable[[str], List[str]]] = None,
        decision_resolver: Optional[Callable[[str], List[str]]] = None
    ):
        self.file_watcher: Optional[FileWatcher] = None
        self.git_handler = GitHookHandler()
        self.cicd_handler = CICDWebhookHandler()
        
        # Resolvers for mapping files to evidence/decisions
        self._evidence_resolver = evidence_path_resolver
        self._decision_resolver = decision_resolver
        
        self._alerts: List[StalenessAlert] = []
        self._alert_callbacks: List[Callable[[StalenessAlert], None]] = []
        
        # Wire up handlers
        self.git_handler.on_changes(self._on_changes)
        self.cicd_handler.on_changes(self._on_changes)
    
    def on_alert(self, callback: Callable[[StalenessAlert], None]):
        """Register callback for staleness alerts."""
        self._alert_callbacks.append(callback)
    
    async def start_file_watcher(self, watch_paths: List[str], poll_interval: float = 1.0):
        """Start file system watcher."""
        self.file_watcher = FileWatcher(watch_paths, poll_interval)
        self.file_watcher.on_change(lambda c: asyncio.create_task(self._on_changes([c])))
        await self.file_watcher.start()
    
    async def stop_file_watcher(self):
        """Stop file system watcher."""
        if self.file_watcher:
            await self.file_watcher.stop()
    
    async def handle_git_hook(self, payload: Dict[str, Any]) -> StalenessAlert:
        """Handle incoming git hook."""
        git_payload = GitHookPayload(**payload)
        changes = await self.git_handler.handle_hook(git_payload)
        return await self._create_alert(changes, ChangeSource.GIT_HOOK)
    
    async def handle_cicd_webhook(self, payload: Dict[str, Any]) -> StalenessAlert:
        """Handle incoming CI/CD webhook."""
        cicd_payload = CICDWebhookPayload(**payload)
        changes = await self.cicd_handler.handle_webhook(cicd_payload)
        return await self._create_alert(changes, ChangeSource.CI_CD_WEBHOOK)
    
    async def _on_changes(self, changes: List[FileChange]):
        """Handle detected changes."""
        if changes:
            source = changes[0].source if changes else ChangeSource.MANUAL
            alert = await self._create_alert(changes, source)
            await self._notify_alert(alert)
    
    async def _create_alert(self, changes: List[FileChange], source: ChangeSource) -> StalenessAlert:
        """Create staleness alert from changes."""
        affected_files = [c.path for c in changes]
        
        # Resolve affected evidence and decisions
        affected_evidence = []
        affected_decisions = []
        
        for path in affected_files:
            if self._evidence_resolver:
                affected_evidence.extend(self._evidence_resolver(path))
            if self._decision_resolver:
                affected_decisions.extend(self._decision_resolver(path))
        
        # Determine severity
        severity = "low"
        if len(affected_decisions) > 5:
            severity = "critical"
        elif len(affected_decisions) > 2:
            severity = "high"
        elif len(affected_decisions) > 0:
            severity = "medium"
        
        alert = StalenessAlert(
            alert_id=f"stale-{datetime.now(timezone.utc).timestamp():.0f}",
            triggered_at=datetime.now(timezone.utc),
            source=source,
            affected_files=affected_files,
            affected_decision_ids=list(set(affected_decisions)),
            affected_evidence_ids=list(set(affected_evidence)),
            severity=severity,
            message=f"{len(changes)} file(s) changed, affecting {len(set(affected_decisions))} decision(s)"
        )
        
        self._alerts.append(alert)
        return alert
    
    async def _notify_alert(self, alert: StalenessAlert):
        """Notify all alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
    
    def get_recent_alerts(self, hours: int = 24) -> List[StalenessAlert]:
        """Get alerts from the last N hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [a for a in self._alerts if a.triggered_at > cutoff]


# Singleton accessor
_staleness_detector: Optional[ProductionStalenessDetector] = None

def get_staleness_detector() -> ProductionStalenessDetector:
    """Get singleton staleness detector instance."""
    global _staleness_detector
    if _staleness_detector is None:
        _staleness_detector = ProductionStalenessDetector()
    return _staleness_detector
