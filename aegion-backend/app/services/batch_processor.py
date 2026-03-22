"""
Batch Processor — Phase 82: Queue non-urgent council queries for deferred processing.

Non-urgent queries (nightly code reviews, doc audits, weekly ADR analysis) can be
queued with a priority level and processed off-peak via a scheduled cron trigger or
manual API call. This reduces peak API overhead and enables rate-limit-aware scheduling.

Priority levels:
    immediate  → process now (user-facing, real-time)
    soon       → within 5 minutes
    deferred   → within 1 hour
    batch      → daily overnight window
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from ..core.logging import logger


PRIORITY_DELAYS: Dict[str, int] = {
    "immediate": 0,
    "soon":      300,    # 5 minutes
    "deferred":  3600,   # 1 hour
    "batch":     86400,  # 24 hours
}


class BatchProcessor:
    """
    Enqueue and process non-urgent council queries.

    Usage:
        # Enqueue from anywhere:
        job = await batch_processor.enqueue(
            workspace_id, query, priority="batch",
            metadata={"source": "nightly_review"}
        )

        # Process ready jobs (called by cron / admin endpoint):
        results = await batch_processor.process_ready()
    """

    async def enqueue(
        self,
        workspace_id: str,
        query: str,
        priority: str = "deferred",
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """
        Add a query to the processing queue.

        Returns:
            The inserted job record dict.
        """
        delay_seconds = PRIORITY_DELAYS.get(priority, PRIORITY_DELAYS["deferred"])
        scheduled_after = (
            datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        ).isoformat()

        job = {
            "workspace_id":  workspace_id,
            "query":         query,
            "priority":      priority,
            "status":        "queued",
            "metadata":      metadata or {},
            "scheduled_after": scheduled_after,
            "created_at":    datetime.now(timezone.utc).isoformat(),
        }

        try:
            from ..db.supabase_client import get_supabase_client
            result = get_supabase_client().table("batch_queue").insert(job).execute()
            return result.data[0] if result.data else job
        except Exception as exc:
            logger.warning(f"Batch enqueue DB write failed (returning in-memory job): {exc}")
            return job

    async def process_ready(self, limit: int = 20) -> List[Dict]:
        """
        Process all queued jobs whose scheduled_after time has passed.

        Args:
            limit: Max jobs to process in one call (prevents runaway).

        Returns:
            List of {job_id, status, error?} dicts.
        """
        from .council_kernel.engine import get_council_engine
        from .council_kernel.types import CouncilType

        results: List[Dict] = []
        now = datetime.now(timezone.utc).isoformat()

        try:
            from ..db.supabase_client import get_supabase_client
            client = get_supabase_client()

            ready = (
                client.table("batch_queue")
                .select("*")
                .eq("status", "queued")
                .lte("scheduled_after", now)
                .order("created_at")
                .limit(limit)
                .execute()
            )

            for job in (ready.data or []):
                job_id = job.get("id", "unknown")
                try:
                    # Mark as processing
                    client.table("batch_queue").update(
                        {"status": "processing"}
                    ).eq("id", job_id).execute()

                    engine = get_council_engine()
                    result = await engine.consult(
                        workspace_id=job["workspace_id"],
                        query=job["query"],
                        council_type=CouncilType.CHILD,
                        context={"skip_gateway": True},  # Already queued — skip gateway
                    )

                    client.table("batch_queue").update({
                        "status":       "completed",
                        "result":       result.model_dump(),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", job_id).execute()

                    results.append({"job_id": job_id, "status": "completed"})
                    logger.info(f"Batch job {job_id} completed")

                except Exception as exc:
                    try:
                        client.table("batch_queue").update({
                            "status": "failed",
                            "error":  str(exc)[:500],
                        }).eq("id", job_id).execute()
                    except Exception:
                        pass
                    results.append({"job_id": job_id, "status": "failed", "error": str(exc)})
                    logger.warning(f"Batch job {job_id} failed: {exc}")

        except Exception as exc:
            logger.error(f"Batch processor setup failed: {exc}")

        return results

    async def get_status(self, workspace_id: str) -> List[Dict]:
        """List all batch jobs for a workspace."""
        try:
            from ...db.supabase_client import get_supabase_client
            result = (
                get_supabase_client()
                .table("batch_queue")
                .select("id,query,priority,status,scheduled_after,created_at,completed_at,error")
                .eq("workspace_id", workspace_id)
                .order("created_at", desc=True)
                .limit(50)
                .execute()
            )
            return result.data or []
        except Exception:
            return []


# Module-level singleton
batch_processor = BatchProcessor()


# ---------------------------------------------------------------------------
# SQL migration (run once in Supabase):
# ---------------------------------------------------------------------------
BATCH_QUEUE_SQL = """
CREATE TABLE IF NOT EXISTS batch_queue (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    query            TEXT NOT NULL,
    priority         TEXT NOT NULL DEFAULT 'deferred',
    status           TEXT NOT NULL DEFAULT 'queued',  -- queued | processing | completed | failed
    metadata         JSONB DEFAULT '{}',
    result           JSONB,
    error            TEXT,
    scheduled_after  TIMESTAMPTZ NOT NULL,
    created_at       TIMESTAMPTZ DEFAULT now(),
    completed_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_batch_queue_ready
    ON batch_queue(status, scheduled_after)
    WHERE status = 'queued';
"""
