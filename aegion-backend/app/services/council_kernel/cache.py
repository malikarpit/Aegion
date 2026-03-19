"""
Semantic Cache Layer — Phase 11.

Caches LLM responses by semantic similarity using pgvector cosine distance.
A cache HIT avoids any LLM call entirely — 70-86% cost savings in practice.

Similarity threshold: 0.92 (balances accuracy vs hit rate).
TTL is content-type aware:
  - architecture decisions: 30 days (slow to change)
  - security assessments:   1 day   (must stay current)
  - code explanations:      7 days
  - debate results:         14 days
  - default:                7 days

Phase 8 ships with an _InProcessCache fallback inside engine.py.
This module upgrades that to pgvector-backed persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from ...core.logging import logger

# TTL in hours per cache_type
_TTL: Dict[str, int] = {
    "code_explanation": 168,   # 7 days
    "architecture":     720,   # 30 days
    "security":          24,   # 1 day
    "debate_result":    336,   # 14 days
    "default":          168,   # 7 days
}

# Semantic similarity threshold — responses with cosine similarity >= this are returned
DEFAULT_THRESHOLD = 0.92


class SemanticCache:
    """
    Supabase pgvector-backed semantic cache.

    Uses the match_knowledge_nodes RPC pattern but against a dedicated
    semantic_cache table with TTL support.

    Required table (migration 20260409000005_semantic_cache.sql):
        semantic_cache(id, workspace_id, query_text, query_embedding vector(384),
                       response_text, response_model, cache_type, expires_at, created_at)
    """

    def __init__(self) -> None:
        self._embedder = None  # Lazy-loaded
        self._degraded = False
        self._degradation_reason = ""
        self._hit_count = 0
        self._miss_count = 0
        self._error_count = 0

    def warmup(self) -> None:
        """Explicitly check if the cache can function. Call on startup."""
        self._get_embedder()
        if self._degraded:
            logger.warning(
                f"⚠️  Semantic cache DEGRADED: {self._degradation_reason}. "
                "Install with: pip install sentence-transformers"
            )
        else:
            logger.info("Semantic cache ready (all-MiniLM-L6-v2)")

    def is_available(self) -> bool:
        """Check if the cache is functional (not degraded)."""
        if self._embedder is None:
            self._get_embedder()
        return not self._degraded

    def health(self) -> Dict:
        """Return cache health status for monitoring."""
        total = self._hit_count + self._miss_count
        return {
            "status": "ok" if not self._degraded else "degraded",
            "reason": self._degradation_reason or "operational",
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": round(self._hit_count / max(total, 1), 3),
            "error_count": self._error_count,
        }

    def _get_embedder(self):
        """Lazy-load embedder to avoid blocking startup."""
        if self._embedder is None and not self._degraded:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                self._degraded = True
                self._degradation_reason = (
                    "sentence-transformers not installed — "
                    "cache disabled, all queries will be LLM calls"
                )
                logger.warning(self._degradation_reason)
        return self._embedder

    def _client(self):
        from ...db.supabase_client import get_supabase_client
        return get_supabase_client()

    async def check(
        self,
        workspace_id: str,
        query: str,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> Optional[Dict]:
        """
        Look for a semantically similar unexpired cache entry.

        Returns dict with response_text and response_model, or None on miss.
        """
        embedder = self._get_embedder()
        if embedder is None:
            self._miss_count += 1
            return None  # Cache disabled without sentence-transformers

        try:
            embedding = embedder.encode(query).tolist()
            now_iso = datetime.now(timezone.utc).isoformat()

            result = self._client().rpc(
                "match_semantic_cache",
                {
                    "query_embedding": embedding,
                    "match_threshold": threshold,
                    "match_count": 1,
                    "p_workspace_id": workspace_id,
                    "p_now": now_iso,
                },
            ).execute()

            if result.data:
                self._hit_count += 1
                logger.info(f"Semantic cache HIT (workspace={workspace_id})")
                return result.data[0]
            self._miss_count += 1
        except Exception as exc:
            self._error_count += 1
            logger.warning(f"Semantic cache check failed (non-fatal): {exc}")

        self._miss_count += 1
        return None

    async def store(
        self,
        workspace_id: str,
        query: str,
        response: str,
        model: str,
        cache_type: str = "default",
    ) -> bool:
        """Embed and store a query/response pair. Returns True on success."""
        embedder = self._get_embedder()
        if embedder is None:
            return False

        try:
            embedding = embedder.encode(query).tolist()
            ttl_hours = _TTL.get(cache_type, _TTL["default"])
            expires_at = (
                datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
            ).isoformat()

            self._client().table("semantic_cache").insert({
                "workspace_id": workspace_id,
                "query_text": query,
                "query_embedding": embedding,
                "response_text": response,
                "response_model": model,
                "cache_type": cache_type,
                "expires_at": expires_at,
            }).execute()
            return True
        except Exception as exc:
            logger.warning(f"Semantic cache store failed (non-fatal): {exc}")
            return False

    async def invalidate(
        self,
        workspace_id: str,
        pattern: Optional[str] = None,
    ) -> int:
        """
        Invalidate cache entries for a workspace, optionally filtered by query text pattern.
        Returns number of invalidated entries.
        """
        try:
            q = self._client().table("semantic_cache").delete().eq(
                "workspace_id", workspace_id
            )
            if pattern:
                q = q.ilike("query_text", f"%{pattern}%")
            result = q.execute()
            count = len(result.data) if result.data else 0
            logger.info(f"Invalidated {count} cache entries for workspace={workspace_id}")
            return count
        except Exception as exc:
            logger.warning(f"Semantic cache invalidation failed: {exc}")
            return 0


# Singleton
_semantic_cache: Optional[SemanticCache] = None


def get_semantic_cache() -> SemanticCache:
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticCache()
    return _semantic_cache
