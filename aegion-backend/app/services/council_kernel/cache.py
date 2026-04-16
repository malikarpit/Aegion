"""
Semantic Cache Layer — Phase 11 (Phase 95: CodeBERT upgrade).

Caches LLM responses by semantic similarity using pgvector cosine distance.
A cache HIT avoids any LLM call entirely — 70-86% cost savings in practice.

Similarity threshold: 0.92 (balances accuracy vs hit rate).
TTL is content-type aware:
  - architecture decisions: 30 days (slow to change)
  - security assessments:   1 day   (must stay current)
  - code explanations:      7 days
  - debate results:         14 days
  - default:                7 days

Embedding Model (Phase 95):
  Default: microsoft/codebert-base (768-dim, code-aware embeddings)
  Fallback: all-MiniLM-L6-v2 (384-dim, general NLP)
  Override: AEGION_EMBEDDING_MODEL environment variable

Migration note: If upgrading from MiniLM (384-dim) to CodeBERT (768-dim),
run: ALTER TABLE semantic_cache ALTER COLUMN query_embedding TYPE vector(768);
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import os

from ...core.logging import logger

# Phase 95: Configurable embedding model
_DEFAULT_MODEL = "microsoft/codebert-base"
_FALLBACK_MODEL = "all-MiniLM-L6-v2"
_EMBEDDING_MODEL = os.getenv("AEGION_EMBEDDING_MODEL", _DEFAULT_MODEL)

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

    Features:
        - Content-aware TTL (architecture 30d, security 1d, code 7d)
        - LRU-based eviction when cache exceeds max_entries
        - Cache statistics for monitoring (hit rate, eviction count)
        - Graceful degradation when sentence-transformers unavailable

    Required table (migration 20260409000005_semantic_cache.sql):
        semantic_cache(id, workspace_id, query_text, query_embedding vector(384),
                       response_text, response_model, cache_type, expires_at,
                       last_accessed_at, access_count, created_at)
    """

    # Maximum entries per workspace before LRU eviction kicks in
    DEFAULT_MAX_ENTRIES = 10_000

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._embedder = None  # Lazy-loaded
        self._degraded = False
        self._degradation_reason = ""
        self._hit_count = 0
        self._miss_count = 0
        self._error_count = 0
        self._eviction_count = 0
        self._max_entries = max_entries

    def warmup(self) -> None:
        """Explicitly check if the cache can function. Call on startup."""
        self._get_embedder()
        if self._degraded:
            logger.warning(
                f"⚠️  Semantic cache DEGRADED: {self._degradation_reason}. "
                "Install with: pip install sentence-transformers"
            )
        else:
            logger.info(f"Semantic cache warmed up ({_EMBEDDING_MODEL})")

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
            "eviction_count": self._eviction_count,
            "max_entries": self._max_entries,
        }

    def stats(self) -> Dict:
        """
        Extended cache statistics for the monitoring dashboard.

        Returns all health metrics plus computed analytics:
            - total_queries: total check() calls
            - effectiveness: weighted score (high hit rate + low errors)
        """
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / max(total, 1)
        error_rate = self._error_count / max(total, 1)
        # Effectiveness = hit_rate penalized by error_rate
        effectiveness = max(0.0, hit_rate - error_rate * 0.5)

        return {
            **self.health(),
            "total_queries": total,
            "effectiveness": round(effectiveness, 3),
        }

    def _get_embedder(self):
        """Lazy-load embedder. Tries CodeBERT first, falls back to MiniLM."""
        if self._embedder is None and not self._degraded:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                try:
                    self._embedder = SentenceTransformer(_EMBEDDING_MODEL)
                    # Detect vector dimensions
                    test_vec = self._embedder.encode("test")
                    self._vector_dim = len(test_vec)
                    logger.info(
                        f"Semantic cache ready ({_EMBEDDING_MODEL}, {self._vector_dim}-dim)"
                    )
                except Exception as model_err:
                    # CodeBERT may fail to download — fall back to MiniLM
                    logger.warning(
                        f"Failed to load {_EMBEDDING_MODEL}: {model_err}. "
                        f"Falling back to {_FALLBACK_MODEL}"
                    )
                    self._embedder = SentenceTransformer(_FALLBACK_MODEL)
                    test_vec = self._embedder.encode("test")
                    self._vector_dim = len(test_vec)
                    logger.info(
                        f"Semantic cache ready (fallback: {_FALLBACK_MODEL}, {self._vector_dim}-dim)"
                    )
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
        On hit, updates last_accessed_at and access_count for LRU tracking.
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

                # Update access tracking for LRU (best-effort)
                try:
                    entry_id = result.data[0].get("id")
                    if entry_id:
                        self._client().table("semantic_cache").update({
                            "last_accessed_at": now_iso,
                            "access_count": result.data[0].get("access_count", 0) + 1,
                        }).eq("id", entry_id).execute()
                except Exception:
                    pass  # Non-critical — don't fail the cache hit

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
            now_iso = datetime.now(timezone.utc).isoformat()

            self._client().table("semantic_cache").insert({
                "workspace_id": workspace_id,
                "query_text": query,
                "query_embedding": embedding,
                "response_text": response,
                "response_model": model,
                "cache_type": cache_type,
                "expires_at": expires_at,
                "last_accessed_at": now_iso,
                "access_count": 1,
            }).execute()

            # Proactive LRU eviction — runs after insert to bound cache size
            await self._evict_lru(workspace_id)

            return True
        except Exception as exc:
            logger.warning(f"Semantic cache store failed (non-fatal): {exc}")
            return False

    async def _evict_lru(self, workspace_id: str) -> int:
        """
        Evict least-recently-used entries when cache exceeds max_entries.

        LRU policy: Delete entries with oldest last_accessed_at first.
        Only evicts expired entries first, then LRU if still over limit.

        Returns number of entries evicted.
        """
        try:
            # Step 1: Count entries for this workspace
            count_result = self._client().table("semantic_cache").select(
                "id", count="exact"
            ).eq("workspace_id", workspace_id).execute()

            total = count_result.count if hasattr(count_result, "count") and count_result.count else 0
            if total <= self._max_entries:
                return 0

            excess = total - self._max_entries

            # Step 2: Delete expired entries first
            now_iso = datetime.now(timezone.utc).isoformat()
            expired_result = self._client().table("semantic_cache").delete().eq(
                "workspace_id", workspace_id
            ).lt("expires_at", now_iso).execute()
            expired_deleted = len(expired_result.data) if expired_result.data else 0

            excess -= expired_deleted
            self._eviction_count += expired_deleted

            if excess <= 0:
                return expired_deleted

            # Step 3: Delete LRU entries (oldest last_accessed_at)
            lru_result = self._client().table("semantic_cache").select("id").eq(
                "workspace_id", workspace_id
            ).order("last_accessed_at").limit(excess).execute()

            if lru_result.data:
                ids_to_delete = [r["id"] for r in lru_result.data]
                self._client().table("semantic_cache").delete().in_(
                    "id", ids_to_delete
                ).execute()
                self._eviction_count += len(ids_to_delete)
                return expired_deleted + len(ids_to_delete)

            return expired_deleted
        except Exception as exc:
            logger.debug(f"Cache eviction skipped: {exc}")
            return 0

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

    def reset_stats(self) -> None:
        """Reset all statistics counters. Useful for testing."""
        self._hit_count = 0
        self._miss_count = 0
        self._error_count = 0
        self._eviction_count = 0


# Singleton
_semantic_cache: Optional[SemanticCache] = None


def get_semantic_cache() -> SemanticCache:
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticCache()
    return _semantic_cache
