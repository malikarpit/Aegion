"""
Aegion Council Postgres Store — Phase 90.

Persistent storage for council sessions and events, replacing
the in-memory event store that loses all data on restart.

Used by TEAM mode and all production council operations.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import json
import logging

logger = logging.getLogger(__name__)


class PostgresCouncilStore:
    """
    Durable council session and event store backed by PostgreSQL.

    Replaces the in-memory event store that previously caused
    complete data loss on service restart in TEAM mode.
    """

    def __init__(self, pool):
        self._pool = pool

    async def save_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Persist a council session (upsert on id)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO council_sessions
                    (id, workspace_id, session_type, state, tier,
                     model_config, created_at, updated_at)
                VALUES ($1, $2::uuid, $3, $4::jsonb, $5, $6::jsonb, $7, $7)
                ON CONFLICT (id) DO UPDATE SET
                    state = $4::jsonb,
                    tier = $5,
                    updated_at = $7
                RETURNING *
            """,
                session_data["id"],
                session_data.get("workspace_id"),
                session_data.get("session_type", "child"),
                json.dumps(session_data.get("state", {})),
                session_data.get("tier", "T1"),
                json.dumps(session_data.get("model_config", {})),
                datetime.now(timezone.utc),
            )
            return dict(row) if row else session_data

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load a single council session by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM council_sessions WHERE id = $1",
                session_id,
            )
            if not row:
                return None
            data = dict(row)
            # Deserialize JSONB fields
            if isinstance(data.get("state"), str):
                data["state"] = json.loads(data["state"])
            if isinstance(data.get("model_config"), str):
                data["model_config"] = json.loads(data["model_config"])
            return data

    async def list_sessions(
        self,
        workspace_id: str,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List council sessions for a workspace."""
        sql = "SELECT * FROM council_sessions WHERE workspace_id = $1::uuid"
        params: list = [workspace_id]
        idx = 2

        if status:
            sql += f" AND state->>'status' = ${idx}"
            params.append(status)
            idx += 1

        sql += f" ORDER BY created_at DESC LIMIT ${idx}"
        params.append(limit)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            return [dict(r) for r in rows]

    # ── Events ──

    async def save_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Persist a single council event (append-only)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO council_events
                    (session_id, event_type, agent_name, agent_role,
                     payload, confidence, cost_usd, created_at)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)
                RETURNING *
            """,
                event_data["session_id"],
                event_data["event_type"],
                event_data.get("agent_name"),
                event_data.get("agent_role"),
                json.dumps(event_data.get("payload", {})),
                event_data.get("confidence"),
                event_data.get("cost_usd", 0.0),
                event_data.get("created_at", datetime.now(timezone.utc)),
            )
            return dict(row) if row else event_data

    async def list_events(
        self,
        session_id: str,
        after_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List events for a council session, optionally after a cursor."""
        if after_id is not None:
            sql = """
                SELECT * FROM council_events
                WHERE session_id = $1 AND id > $2
                ORDER BY id ASC
            """
            params = [session_id, after_id]
        else:
            sql = """
                SELECT * FROM council_events
                WHERE session_id = $1
                ORDER BY id ASC
            """
            params = [session_id]

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            return [dict(r) for r in rows]

    async def get_latest_event(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent event for a session."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM council_events
                WHERE session_id = $1
                ORDER BY id DESC
                LIMIT 1
            """, session_id)
            return dict(row) if row else None

    # ── Analytics ──

    async def count_events_by_type(
        self, workspace_id: str, days: int = 30
    ) -> Dict[str, int]:
        """Count events by type for analytics."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT ce.event_type, COUNT(*) as cnt
                FROM council_events ce
                JOIN council_sessions cs ON ce.session_id = cs.id
                WHERE cs.workspace_id = $1::uuid
                  AND ce.created_at > NOW() - make_interval(days => $2)
                GROUP BY ce.event_type
            """, workspace_id, days)
            return {row["event_type"]: row["cnt"] for row in rows}

    async def get_cost_summary(
        self, workspace_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Get council cost summary for a workspace."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(DISTINCT ce.session_id) as session_count,
                    COUNT(*) as event_count,
                    COALESCE(SUM(ce.cost_usd), 0.0) as total_cost_usd,
                    COALESCE(AVG(ce.confidence), 0.0) as avg_confidence
                FROM council_events ce
                JOIN council_sessions cs ON ce.session_id = cs.id
                WHERE cs.workspace_id = $1::uuid
                  AND ce.created_at > NOW() - make_interval(days => $2)
            """, workspace_id, days)
            return dict(row) if row else {
                "session_count": 0, "event_count": 0,
                "total_cost_usd": 0.0, "avg_confidence": 0.0,
            }


# ──────────────────────────────────────────────────────────────────────────────
# ACK Council Result Store (Supabase-backed)
# ──────────────────────────────────────────────────────────────────────────────

class CouncilResultStore:
    """
    Persists ACK CouncilResult objects to Supabase for audit trail.

    Works with both the `council_results` table and the existing
    `cost_tracking` table for financial analytics.
    """

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            try:
                from ...db.supabase_client import get_supabase_client
                self._client = get_supabase_client()
            except Exception:
                return None
        return self._client

    async def save_result(
        self, workspace_id: str, result_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Persist an ACK CouncilResult to the council_results table.

        Args:
            workspace_id: Workspace owning this result.
            result_data: Serialized CouncilResult (from .model_dump()).

        Returns:
            The stored record, or None on failure.
        """
        client = self._get_client()
        if not client:
            logger.warning("CouncilResultStore: Supabase client unavailable")
            return None

        try:
            import uuid as _uuid
            record = {
                "id": str(_uuid.uuid4()),
                "workspace_id": workspace_id,
                "council_type": result_data.get("council_type", "child"),
                "profile": result_data.get("profile", "simple"),
                "query": (result_data.get("query", ""))[:2000],
                "synthesis": (result_data.get("synthesis", ""))[:10000],
                "consensus_score": result_data.get("consensus_score", 0.0),
                "total_cost_usd": result_data.get("total_cost_usd", 0.0),
                "total_tokens": result_data.get("total_tokens", 0),
                "total_latency_ms": result_data.get("total_latency_ms", 0),
                "cache_hit": result_data.get("cache_hit", False),
                "models_used": result_data.get("models_used", []),
                "individual_responses": json.dumps(
                    result_data.get("individual_responses", []),
                    default=str,
                ),
                "dissenting_views": json.dumps(
                    result_data.get("dissenting_views", []),
                    default=str,
                ),
                "rubric_scores": json.dumps(
                    result_data.get("rubric_scores"),
                    default=str,
                ) if result_data.get("rubric_scores") else None,
            }
            resp = client.table("council_results").insert(record).execute()
            return resp.data[0] if resp.data else record
        except Exception as exc:
            logger.warning(f"CouncilResultStore: save failed (non-fatal): {exc}")
            return None

    async def get_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Load a single council result by ID."""
        client = self._get_client()
        if not client:
            return None
        try:
            resp = (
                client.table("council_results")
                .select("*")
                .eq("id", result_id)
                .maybe_single()
                .execute()
            )
            return resp.data
        except Exception as exc:
            logger.warning(f"CouncilResultStore: get failed: {exc}")
            return None

    async def list_results(
        self, workspace_id: str, limit: int = 50, offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List council results for a workspace, newest first."""
        client = self._get_client()
        if not client:
            return []
        try:
            resp = (
                client.table("council_results")
                .select("*")
                .eq("workspace_id", workspace_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return resp.data or []
        except Exception as exc:
            logger.warning(f"CouncilResultStore: list failed: {exc}")
            return []


# Singleton
_result_store: Optional[CouncilResultStore] = None


def get_council_result_store() -> CouncilResultStore:
    """Get the application-wide CouncilResultStore singleton."""
    global _result_store
    if _result_store is None:
        _result_store = CouncilResultStore()
    return _result_store

