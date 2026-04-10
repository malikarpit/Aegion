"""
Aegion Draft & Recovery Repository Storage.

Repository-backed persistence for drafts and recovery points.
Replaces in-memory mock stores with durable storage.
"""

from typing import Optional, List, Dict, Any
from datetime import timezone, datetime, timedelta
from dataclasses import dataclass, field
import json
from pathlib import Path
import asyncio
import uuid

from ...core.logging import logger


@dataclass 
class Draft:
    """A saved draft proposal or decision."""
    draft_id: str
    session_id: str
    user_id: str
    draft_type: str  # proposal, decision, evidence
    content: Dict[str, Any]
    created_at: str
    updated_at: str
    auto_save: bool = False
    version: int = 1


@dataclass
class RecoveryPoint:
    """A recovery checkpoint for session state."""
    recovery_id: str
    session_id: str
    user_id: str
    state_snapshot: Dict[str, Any]
    created_at: str
    reason: str  # crash, manual, interval
    expires_at: str


class DraftRepository:
    """
    Repository-backed storage for drafts.
    
    Persists drafts to filesystem with automatic expiry.
    """
    
    def __init__(self, storage_path: str = ".aegion/drafts"):
        self._storage_path = Path(storage_path)
        self._retention_days = 30
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the draft repository."""
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info(f"Draft repository initialized at {self._storage_path}")
    
    def _ensure_initialized(self):
        if not self._initialized:
            raise RuntimeError("Repository not initialized. Call initialize() first.")
    
    def _get_draft_path(self, draft_id: str) -> Path:
        return self._storage_path / f"{draft_id}.json"
    
    async def save(
        self,
        session_id: str,
        user_id: str,
        draft_type: str,
        content: Dict[str, Any],
        draft_id: Optional[str] = None,
        auto_save: bool = False
    ) -> Draft:
        """Save a draft."""
        self._ensure_initialized()
        
        now = datetime.now(timezone.utc).isoformat() + "Z"
        
        if draft_id:
            # Update existing
            existing = await self.get(draft_id)
            if existing:
                draft = Draft(
                    draft_id=draft_id,
                    session_id=session_id,
                    user_id=user_id,
                    draft_type=draft_type,
                    content=content,
                    created_at=existing.created_at,
                    updated_at=now,
                    auto_save=auto_save,
                    version=existing.version + 1
                )
            else:
                draft = Draft(
                    draft_id=draft_id,
                    session_id=session_id,
                    user_id=user_id,
                    draft_type=draft_type,
                    content=content,
                    created_at=now,
                    updated_at=now,
                    auto_save=auto_save,
                    version=1
                )
        else:
            draft_id = str(uuid.uuid4())
            draft = Draft(
                draft_id=draft_id,
                session_id=session_id,
                user_id=user_id,
                draft_type=draft_type,
                content=content,
                created_at=now,
                updated_at=now,
                auto_save=auto_save,
                version=1
            )
        
        # Persist
        path = self._get_draft_path(draft.draft_id)
        data = {
            "draft_id": draft.draft_id,
            "session_id": draft.session_id,
            "user_id": draft.user_id,
            "draft_type": draft.draft_type,
            "content": draft.content,
            "created_at": draft.created_at,
            "updated_at": draft.updated_at,
            "auto_save": draft.auto_save,
            "version": draft.version
        }
        
        await asyncio.to_thread(
            path.write_text,
            json.dumps(data, indent=2, default=str)
        )
        
        logger.debug(f"Saved draft {draft.draft_id} v{draft.version}")
        return draft
    
    async def get(self, draft_id: str) -> Optional[Draft]:
        """Get a draft by ID."""
        self._ensure_initialized()
        
        path = self._get_draft_path(draft_id)
        if not path.exists():
            return None
        
        data = json.loads(await asyncio.to_thread(path.read_text))
        return Draft(**data)
    
    async def list_by_session(self, session_id: str) -> List[Draft]:
        """List drafts for a session."""
        self._ensure_initialized()
        
        drafts = []
        for path in self._storage_path.glob("*.json"):
            try:
                data = json.loads(await asyncio.to_thread(path.read_text))
                if data.get("session_id") == session_id:
                    drafts.append(Draft(**data))
            except Exception:
                continue
        
        return sorted(drafts, key=lambda d: d.updated_at, reverse=True)
    
    async def list_by_user(self, user_id: str) -> List[Draft]:
        """List drafts for a user."""
        self._ensure_initialized()
        
        drafts = []
        for path in self._storage_path.glob("*.json"):
            try:
                data = json.loads(await asyncio.to_thread(path.read_text))
                if data.get("user_id") == user_id:
                    drafts.append(Draft(**data))
            except Exception:
                continue
        
        return sorted(drafts, key=lambda d: d.updated_at, reverse=True)
    
    async def delete(self, draft_id: str) -> bool:
        """Delete a draft."""
        self._ensure_initialized()
        
        path = self._get_draft_path(draft_id)
        if path.exists():
            await asyncio.to_thread(path.unlink)
            return True
        return False
    
    async def cleanup_expired(self) -> int:
        """Remove expired drafts."""
        self._ensure_initialized()
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        removed = 0
        
        for path in self._storage_path.glob("*.json"):
            try:
                data = json.loads(await asyncio.to_thread(path.read_text))
                updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", ""))
                if updated_at < cutoff:
                    await asyncio.to_thread(path.unlink)
                    removed += 1
            except Exception:
                continue
        
        logger.info(f"Cleaned up {removed} expired drafts")
        return removed


class RecoveryRepository:
    """
    Repository-backed storage for recovery points.
    
    Stores session state snapshots for crash recovery.
    """
    
    def __init__(self, storage_path: str = ".aegion/recovery"):
        self._storage_path = Path(storage_path)
        self._retention_hours = 72  # Keep recovery points for 72 hours
        self._max_points_per_session = 10
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the recovery repository."""
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info(f"Recovery repository initialized at {self._storage_path}")
    
    def _ensure_initialized(self):
        if not self._initialized:
            raise RuntimeError("Repository not initialized. Call initialize() first.")
    
    def _get_session_dir(self, session_id: str) -> Path:
        return self._storage_path / session_id
    
    async def create_checkpoint(
        self,
        session_id: str,
        user_id: str,
        state_snapshot: Dict[str, Any],
        reason: str = "interval"
    ) -> RecoveryPoint:
        """Create a recovery checkpoint."""
        self._ensure_initialized()
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self._retention_hours)
        
        recovery = RecoveryPoint(
            recovery_id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            state_snapshot=state_snapshot,
            created_at=now.isoformat() + "Z",
            reason=reason,
            expires_at=expires_at.isoformat() + "Z"
        )
        
        # Persist
        session_dir = self._get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        recovery_path = session_dir / f"{recovery.recovery_id}.json"
        data = {
            "recovery_id": recovery.recovery_id,
            "session_id": recovery.session_id,
            "user_id": recovery.user_id,
            "state_snapshot": recovery.state_snapshot,
            "created_at": recovery.created_at,
            "reason": recovery.reason,
            "expires_at": recovery.expires_at
        }
        
        await asyncio.to_thread(
            recovery_path.write_text,
            json.dumps(data, indent=2, default=str)
        )
        
        # Enforce max points per session
        await self._prune_session(session_id)
        
        logger.debug(f"Created recovery point {recovery.recovery_id} for {session_id}")
        return recovery
    
    async def _prune_session(self, session_id: str) -> None:
        """Keep only the latest N recovery points per session."""
        session_dir = self._get_session_dir(session_id)
        if not session_dir.exists():
            return
        
        points = []
        for path in session_dir.glob("*.json"):
            try:
                data = json.loads(await asyncio.to_thread(path.read_text))
                points.append((path, data["created_at"]))
            except Exception:
                continue
        
        # Sort by created_at descending
        points.sort(key=lambda x: x[1], reverse=True)
        
        # Remove excess
        for path, _ in points[self._max_points_per_session:]:
            await asyncio.to_thread(path.unlink)
    
    async def get_latest(self, session_id: str) -> Optional[RecoveryPoint]:
        """Get the most recent recovery point for a session."""
        self._ensure_initialized()
        
        session_dir = self._get_session_dir(session_id)
        if not session_dir.exists():
            return None
        
        latest = None
        latest_time = None
        
        for path in session_dir.glob("*.json"):
            try:
                data = json.loads(await asyncio.to_thread(path.read_text))
                created = datetime.fromisoformat(data["created_at"].replace("Z", ""))
                if latest_time is None or created > latest_time:
                    latest_time = created
                    latest = RecoveryPoint(**data)
            except Exception:
                continue
        
        return latest
    
    async def list_for_session(self, session_id: str) -> List[RecoveryPoint]:
        """List all recovery points for a session."""
        self._ensure_initialized()
        
        session_dir = self._get_session_dir(session_id)
        if not session_dir.exists():
            return []
        
        points = []
        for path in session_dir.glob("*.json"):
            try:
                data = json.loads(await asyncio.to_thread(path.read_text))
                points.append(RecoveryPoint(**data))
            except Exception:
                continue
        
        return sorted(points, key=lambda p: p.created_at, reverse=True)
    
    async def recover(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Recover session state from latest checkpoint."""
        self._ensure_initialized()
        
        point = await self.get_latest(session_id)
        if point:
            logger.info(f"Recovering session {session_id} from {point.recovery_id}")
            return point.state_snapshot
        return None
    
    async def cleanup_expired(self) -> int:
        """Remove expired recovery points."""
        self._ensure_initialized()
        
        now = datetime.now(timezone.utc)
        removed = 0
        
        for session_dir in self._storage_path.iterdir():
            if not session_dir.is_dir():
                continue
            
            for path in session_dir.glob("*.json"):
                try:
                    data = json.loads(await asyncio.to_thread(path.read_text))
                    expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", ""))
                    if expires_at < now:
                        await asyncio.to_thread(path.unlink)
                        removed += 1
                except Exception:
                    continue
            
            # Remove empty session directories
            if not any(session_dir.iterdir()):
                await asyncio.to_thread(session_dir.rmdir)
        
        logger.info(f"Cleaned up {removed} expired recovery points")
        return removed


# Singletons
_draft_repo: Optional[DraftRepository] = None
_recovery_repo: Optional[RecoveryRepository] = None


def get_draft_repository() -> DraftRepository:
    """Get the draft repository singleton."""
    global _draft_repo
    if _draft_repo is None:
        _draft_repo = DraftRepository()
    return _draft_repo


def get_recovery_repository() -> RecoveryRepository:
    """Get the recovery repository singleton."""
    global _recovery_repo
    if _recovery_repo is None:
        _recovery_repo = RecoveryRepository()
    return _recovery_repo
