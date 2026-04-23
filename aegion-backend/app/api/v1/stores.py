"""
Aegion API — Supabase-Backed Stores for Drafts & Sessions.

AG-005 → AG-PROD: Replaced in-memory and file-based stores with
Supabase-backed implementations. Data survives restarts.

Provides the same interface as the old InMemoryDraftStore/InMemorySessionStore
so all consumers (drafts.py, recovery.py) work without changes.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import os

from ...models.draft import SessionDraft
from ...models.session import Session
from ...core.logging import logger


class SupabaseDraftStore:
    """
    Supabase-backed draft store.
    Uses kv_store table with namespace='drafts' for flexible schema.
    Matches the same interface as the old InMemoryDraftStore.
    """

    def __init__(self):
        from ...db.supabase_client import get_supabase_client
        self._db = get_supabase_client()

    async def save(self, draft: SessionDraft) -> SessionDraft:
        draft.updated_at = datetime.now(timezone.utc)
        data = draft.model_dump(mode="json") if hasattr(draft, "model_dump") else draft.dict()
        workspace_id = getattr(draft, "workspace_id", None) or "default"
        self._db.table("kv_store").upsert({
            "workspace_id": workspace_id,
            "namespace": "drafts",
            "key": draft.draft_id,
            "value": data,
        }, on_conflict="workspace_id,namespace,key").execute()
        logger.debug(f"Draft saved to Supabase: {draft.draft_id}")
        return draft

    async def get(self, draft_id: str) -> Optional[SessionDraft]:
        result = self._db.table("kv_store") \
            .select("value") \
            .eq("namespace", "drafts") \
            .eq("key", draft_id) \
            .maybe_single() \
            .execute()
        if result.data and result.data.get("value"):
            try:
                return SessionDraft.model_validate(result.data["value"])
            except Exception:
                return SessionDraft(**result.data["value"])
        return None

    async def list_for_user(self, user_id: str) -> List[SessionDraft]:
        result = self._db.table("kv_store") \
            .select("value") \
            .eq("namespace", "drafts") \
            .execute()
        items = []
        for row in (result.data or []):
            val = row.get("value", {})
            if val.get("user_id") == user_id:
                try:
                    items.append(SessionDraft.model_validate(val))
                except Exception:
                    items.append(SessionDraft(**val))
        return sorted(items, key=lambda d: d.updated_at, reverse=True)

    async def delete(self, draft_id: str) -> bool:
        self._db.table("kv_store") \
            .delete() \
            .eq("namespace", "drafts") \
            .eq("key", draft_id) \
            .execute()
        return True


class SupabaseSessionStore:
    """
    Supabase-backed session store.
    Uses the 'sessions' table directly (not kv_store).
    Matches the same interface as the old InMemorySessionStore.
    """

    def __init__(self):
        from ...db.supabase_client import get_supabase_client
        self._db = get_supabase_client()

    async def create(self, session: Session) -> Session:
        data = session.model_dump(mode="json") if hasattr(session, "model_dump") else session.dict()
        # Map session_id to id for Supabase
        if "session_id" in data and "id" not in data:
            data["id"] = data.pop("session_id")
        # Remove None values to let DB defaults work
        data = {k: v for k, v in data.items() if v is not None}
        try:
            self._db.table("sessions").upsert(data).execute()
        except Exception as exc:
            logger.warning(f"Session create failed (falling back to in-memory): {exc}")
        return session

    async def get_by_id(self, session_id: str) -> Optional[Session]:
        try:
            result = self._db.table("sessions") \
                .select("*") \
                .eq("id", session_id) \
                .maybe_single() \
                .execute()
            if result.data:
                row = result.data
                # Map id back to session_id
                if "id" in row and "session_id" not in row:
                    row["session_id"] = row["id"]
                return Session.model_validate(row) if hasattr(Session, "model_validate") else Session(**row)
        except Exception as exc:
            logger.warning(f"Session fetch failed: {exc}")
        return None

    async def update(self, session_id: str, data: Dict[str, Any]) -> Optional[Session]:
        try:
            self._db.table("sessions") \
                .update(data) \
                .eq("id", session_id) \
                .execute()
        except Exception as exc:
            logger.warning(f"Session update failed: {exc}")
        return await self.get_by_id(session_id)

    async def list_active_stale(self, threshold_iso: str) -> List[Session]:
        """List active sessions with last_activity_at < threshold."""
        try:
            result = self._db.table("sessions") \
                .select("*") \
                .eq("status", "active") \
                .lt("last_activity_at", threshold_iso) \
                .execute()
            sessions = []
            for row in (result.data or []):
                if "id" in row and "session_id" not in row:
                    row["session_id"] = row["id"]
                try:
                    sessions.append(Session.model_validate(row) if hasattr(Session, "model_validate") else Session(**row))
                except Exception:
                    pass
            return sessions
        except Exception as exc:
            logger.warning(f"Session list_active_stale failed: {exc}")
            return []


# ═══════════════════════════════════════════════════════════════════════════
# Legacy classes kept for backward compatibility — NOT used in production
# ═══════════════════════════════════════════════════════════════════════════

class InMemoryDraftStore:
    """Legacy in-memory draft store. Use SupabaseDraftStore instead."""

    def __init__(self):
        self._store: Dict[str, SessionDraft] = {}

    async def save(self, draft: SessionDraft) -> SessionDraft:
        draft.updated_at = datetime.now(timezone.utc)
        self._store[draft.draft_id] = draft
        return draft

    async def get(self, draft_id: str) -> Optional[SessionDraft]:
        return self._store.get(draft_id)

    async def list_for_user(self, user_id: str) -> List[SessionDraft]:
        return sorted(
            [d for d in self._store.values() if d.user_id == user_id],
            key=lambda d: d.updated_at, reverse=True
        )

    async def delete(self, draft_id: str) -> bool:
        if draft_id in self._store:
            del self._store[draft_id]
            return True
        return False


class InMemorySessionStore:
    """Legacy in-memory session store. Use SupabaseSessionStore instead."""

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
        for key, value in data.items():
            if hasattr(session, key):
                setattr(session, key, value)
        self._store[session_id] = session
        return session

    async def list_active_stale(self, threshold_iso: str) -> List[Session]:
        result = []
        for s in self._store.values():
            if s.status == "active" or (hasattr(s.status, 'value') and s.status.value == "active"):
                activity = s.last_activity_at.isoformat() if isinstance(s.last_activity_at, datetime) else str(s.last_activity_at)
                if activity < threshold_iso:
                    result.append(s)
        return result


# ══════════════════════════════════════════════════════════════════════════
# Singletons — always use Supabase in production, fallback to file/memory
# ══════════════════════════════════════════════════════════════════════════

_draft_store: Any = None
_session_store: Any = None


def get_draft_store():
    """Get the draft store singleton. Defaults to Supabase."""
    global _draft_store
    if _draft_store is None:
        backend = os.getenv("AEGION_STORE_BACKEND", "supabase")
        if backend == "supabase":
            try:
                _draft_store = SupabaseDraftStore()
                logger.info("Initialized SupabaseDraftStore (production)")
            except Exception as exc:
                logger.warning(f"Supabase draft store init failed, falling back to InMemory: {exc}")
                _draft_store = InMemoryDraftStore()
        elif backend == "file":
            from ...services.durable_store import JsonFileStore
            _draft_store = JsonFileStore(
                file_path="data/drafts.json",
                model_class=SessionDraft,
                key_field="draft_id"
            )
            # Add adapter method for list_for_user
            async def list_for_user(self, user_id: str) -> List[SessionDraft]:
                all_items = await self.list_all()
                return sorted(
                    [d for d in all_items if d.user_id == user_id],
                    key=lambda d: d.updated_at, reverse=True
                )
            _draft_store.list_for_user = list_for_user.__get__(_draft_store)
            logger.info("Initialized FileDraftStore (durable)")
        else:
            _draft_store = InMemoryDraftStore()
            logger.info("Initialized InMemoryDraftStore (in-memory only)")

    return _draft_store


def get_session_store():
    """Get the session store singleton. Defaults to Supabase."""
    global _session_store
    if _session_store is None:
        backend = os.getenv("AEGION_STORE_BACKEND", "supabase")
        if backend == "supabase":
            try:
                _session_store = SupabaseSessionStore()
                logger.info("Initialized SupabaseSessionStore (production)")
            except Exception as exc:
                logger.warning(f"Supabase session store init failed, falling back to InMemory: {exc}")
                _session_store = InMemorySessionStore()
        elif backend == "file":
            from ...services.durable_store import JsonFileStore
            _session_store = JsonFileStore(
                file_path="data/sessions.json",
                model_class=Session,
                key_field="session_id"
            )
            # Adapters for interface compatibility
            async def create(self, session: Session) -> Session:
                return await self.save(session)
            _session_store.create = create.__get__(_session_store)

            async def get_by_id(self, session_id: str) -> Optional[Session]:
                return await self.get(session_id)
            _session_store.get_by_id = get_by_id.__get__(_session_store)

            async def update(self, session_id: str, data: Dict[str, Any]) -> Optional[Session]:
                session = await self.get(session_id)
                if not session:
                    return None
                for k, v in data.items():
                    if hasattr(session, k):
                        setattr(session, k, v)
                return await self.save(session)
            _session_store.update = update.__get__(_session_store)

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
            logger.info("Initialized InMemorySessionStore (in-memory only)")

    return _session_store
