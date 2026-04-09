"""
Aegion API - In-Memory Stores for Drafts & Sessions.

AG-005: Replaces hardcoded Firestore adapters with testable,
in-memory stores that work without cloud credentials.

For production, swap these with Firestore-backed implementations.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import os

from ...models.draft import SessionDraft
from ...models.session import Session
from ...core.logging import logger
from ...services.durable_store import JsonFileStore


class InMemoryDraftStore:
    """
    In-memory draft store matching FirestoreDraftRepository interface.
    Backed by dict — survives for process lifetime (no Firestore needed).
    """

    def __init__(self):
        self._store: Dict[str, SessionDraft] = {}

    async def save(self, draft: SessionDraft) -> SessionDraft:
        draft.updated_at = datetime.now(timezone.utc)
        self._store[draft.draft_id] = draft
        logger.debug(f"Draft saved: {draft.draft_id}")
        return draft

    async def get(self, draft_id: str) -> Optional[SessionDraft]:
        return self._store.get(draft_id)

    async def list_for_user(self, user_id: str) -> List[SessionDraft]:
        return sorted(
            [d for d in self._store.values() if d.user_id == user_id],
            key=lambda d: d.updated_at,
            reverse=True
        )

    async def delete(self, draft_id: str) -> bool:
        if draft_id in self._store:
            del self._store[draft_id]
            return True
        return False


class InMemorySessionStore:
    """
    In-memory session store matching FirestoreSessionRepository interface.
    Provides get_by_id, update, and list_active_stale.
    """

    def __init__(self):
        self._store: Dict[str, Session] = {}

    async def create(self, session: Session) -> Session:
        self._store[session.session_id] = session
        return session

    async def get_by_id(self, session_id: str) -> Optional[Session]:
        return self._store.get(session_id)

    async def update(self, session_id: str, data: Dict[str, Any]) -> Optional[Session]:
        session = self._store.get(session_id)
        if not session:
            return None
        # Apply partial update
        for key, value in data.items():
            if hasattr(session, key):
                setattr(session, key, value)
        self._store[session_id] = session
        return session

    async def list_active_stale(self, threshold_iso: str) -> List[Session]:
        """List active sessions with last_activity_at < threshold."""
        result = []
        for s in self._store.values():
            if s.status == "active" or (hasattr(s.status, 'value') and s.status.value == "active"):
                activity = s.last_activity_at.isoformat() if isinstance(s.last_activity_at, datetime) else str(s.last_activity_at)
                if activity < threshold_iso:
                    result.append(s)
        return result


# ── Singletons ──

_draft_store: Any = None
_session_store: Any = None


def get_draft_store():
    """Get the draft store singleton."""
    global _draft_store
    if _draft_store is None:
        backend = os.getenv("AEGION_STORE_BACKEND", "file")
        if backend == "file":
             # Use the new durable store
             _draft_store = JsonFileStore(
                 file_path="data/drafts.json",
                 model_class=SessionDraft,
                 key_field="draft_id"
             )
             # Add adapter methods for list_for_user which JsonFileStore doesn't natively have
             # Monkey-patching for now to match interface
             async def list_for_user(self, user_id: str) -> List[SessionDraft]:
                 all_items = await self.list_all()
                 return sorted(
                    [d for d in all_items if d.user_id == user_id],
                    key=lambda d: d.updated_at,
                    reverse=True
                 )
             _draft_store.list_for_user = list_for_user.__get__(_draft_store)

             logger.info("Initialized FileDraftStore (durable)")
        else:
            _draft_store = InMemoryDraftStore()
            logger.info("Initialized InMemoryDraftStore")
            
    return _draft_store


def get_session_store():
    """Get the session store singleton."""
    global _session_store
    if _session_store is None:
        backend = os.getenv("AEGION_STORE_BACKEND", "file")
        if backend == "file":
             _session_store = JsonFileStore(
                 file_path="data/sessions.json",
                 model_class=Session,
                 key_field="session_id"
             )
             
             # Adapter for create
             async def create(self, session: Session) -> Session:
                 return await self.save(session)
             _session_store.create = create.__get__(_session_store)

             # Adapter for get_by_id
             async def get_by_id(self, session_id: str) -> Optional[Session]:
                 return await self.get(session_id)
             _session_store.get_by_id = get_by_id.__get__(_session_store)
             
             # Adapter for update
             async def update(self, session_id: str, data: Dict[str, Any]) -> Optional[Session]:
                 session = await self.get(session_id)
                 if not session: return None
                 for k, v in data.items():
                     if hasattr(session, k): setattr(session, k, v)
                 return await self.save(session)
             _session_store.update = update.__get__(_session_store)
             
             # Adapter for list_active_stale
             async def list_active_stale(self, threshold_iso: str) -> List[Session]:
                all_items = await self.list_all()
                result = []
                for s in all_items:
                    status_val = s.status.value if hasattr(s.status, 'value') else s.status
                    if status_val == "active":
                        activity = s.last_activity_at.isoformat() if isinstance(s.last_activity_at, datetime) else str(s.last_activity_at)
                        if activity < threshold_iso:
                            result.append(s)
                return result
             _session_store.list_active_stale = list_active_stale.__get__(_session_store)
             
             logger.info("Initialized FileSessionStore (durable)")
        else:
            _session_store = InMemorySessionStore()
            logger.info("Initialized InMemorySessionStore")

    return _session_store
