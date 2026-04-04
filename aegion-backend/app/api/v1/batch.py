"""Batch Processing API — Phase 82: Enqueue and manage deferred council queries."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ...core.security import get_current_user
from ...services.batch_processor import batch_processor

router = APIRouter(prefix="/batch", tags=["Batch Processing"])


class EnqueueRequest(BaseModel):
    query: str
    priority: str = "deferred"  # immediate | soon | deferred | batch
    metadata: Optional[dict] = None


@router.post("/enqueue")
async def enqueue_job(req: EnqueueRequest, user = Depends(get_current_user)):
    """Add a non-urgent query to the processing queue."""
    workspace_id = getattr(user, "workspace_id", None) or getattr(user, "user_id", "default")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace_id in token")
    return await batch_processor.enqueue(workspace_id, req.query, req.priority, req.metadata)


@router.get("/status")
async def get_job_status(user = Depends(get_current_user)):
    """List all batch jobs for the authenticated workspace."""
    workspace_id = getattr(user, "workspace_id", None) or getattr(user, "user_id", "default")
    return await batch_processor.get_status(workspace_id)


@router.post("/process")
async def trigger_processing(user = Depends(get_current_user)):
    """Manually trigger processing of ready jobs (for cron or admin use)."""
    results = await batch_processor.process_ready()
    return {"processed": len(results), "results": results}
