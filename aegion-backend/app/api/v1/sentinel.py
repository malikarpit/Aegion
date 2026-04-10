"""
Aegion API v1 — Sentinel Endpoints (Enhanced).

Combines existing drift detection with new ACK-powered security scanning,
risk analysis, and ADR drift detection.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from ...core.security import AuthorityContext, get_current_user
from ...services.sentinel.drift import get_drift_detector, DriftAlert

router = APIRouter(prefix="/sentinel", tags=["sentinel"])


# ── Existing: File drift detection ──

class DriftCheckRequest(BaseModel):
    active_files: List[str] = []

@router.post("/drift", response_model=List[DriftAlert])
async def check_drift(
    request: DriftCheckRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """Check for code drift (modifications outside active session)."""
    detector = get_drift_detector()
    alerts = detector.check_drift(request.active_files)
    return alerts


# ── Phase 21: Risk Analysis ──

class RiskAnalyzeRequest(BaseModel):
    content: str
    files: List[str] = []
    message: str = ""

@router.post("/risk/analyze", summary="Analyze code change for risk signals")
async def analyze_risk(
    req: RiskAnalyzeRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Pattern-based risk analysis with signal categorization and tier recommendation."""
    from ...services.sentinel.council_bridge import get_sentinel_bridge
    workspace_id = getattr(user, "workspace_id", "global")
    return await get_sentinel_bridge().analyze_change(
        workspace_id,
        {"content": req.content, "files": req.files, "message": req.message},
    )


# ── Phase 22: ADR Drift Detection ──

@router.get("/drift/adr", summary="Detect ADR compliance drift")
async def detect_adr_drift(
    user: AuthorityContext = Depends(get_current_user),
):
    """Compare recent changes against accepted Architecture Decision Records."""
    from ...services.sentinel.council_bridge import get_sentinel_bridge
    workspace_id = getattr(user, "workspace_id", "global")
    return await get_sentinel_bridge().detect_drift(workspace_id)


# ── Phase 23: AI Security Scan ──

class SecurityScanRequest(BaseModel):
    code: str
    language: str = "python"

@router.post("/security/scan", summary="AI-powered security audit")
async def security_scan(
    req: SecurityScanRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Deep security analysis via ACK SENTINEL council.

    Combines pattern-based detection with multi-model AI review.
    Returns both fast pattern signals and detailed AI security analysis.
    """
    from ...services.sentinel.council_bridge import get_sentinel_bridge
    workspace_id = getattr(user, "workspace_id", "global")
    return await get_sentinel_bridge().security_scan(
        workspace_id, req.code, req.language,
    )
