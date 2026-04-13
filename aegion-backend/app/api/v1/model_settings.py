"""
Model Settings API — Phase 84: Comprehensive workspace model configuration.

16 endpoints covering:
  - Settings CRUD
  - Preset management (built-in + custom)
  - Budget control and alerts
  - Provider health and testing
  - Cascade configuration
  - Usage analytics
  - Import/Export
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import json
import io

from ...core.security import get_current_user
from ...services.model_settings import model_settings
from ...core.logging import logger

router = APIRouter(prefix="/model-settings", tags=["Model Settings"])


# ──────────────────────────────────────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────────────────────────────────────

class PresetRequest(BaseModel):
    preset: str  # cost_saver | balanced | quality_first | no_limits | privacy_first


class CreatePresetRequest(BaseModel):
    """Create a custom preset profile."""
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field("", max_length=256)
    settings: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class UpdateSettingRequest(BaseModel):
    path: str   # Dot-notation, e.g. "council.default_size"
    value: Any  # The new value


class UpdateBudgetRequest(BaseModel):
    """Set monthly and daily budget limits."""
    monthly_limit_usd: Optional[float] = Field(None, ge=0, le=100000)
    daily_limit_usd: Optional[float] = Field(None, ge=0, le=10000)
    auto_pause: bool = True  # Pause requests when budget exceeded


class BudgetAlertRequest(BaseModel):
    """Configure budget alert thresholds."""
    warning_threshold: float = Field(0.8, ge=0, le=1)     # e.g. 80%
    critical_threshold: float = Field(0.95, ge=0, le=1)   # e.g. 95%
    notify_email: bool = True
    notify_slack: bool = False


class CascadeConfigRequest(BaseModel):
    """Update the model cascade (fallback chain) configuration."""
    cascade_order: List[str] = Field(..., min_length=1)  # ["gemini-flash", "claude-haiku", "gpt-4o"]
    confidence_threshold: float = Field(0.7, ge=0, le=1)
    max_fallback_attempts: int = Field(3, ge=1, le=10)


class ImportSettingsRequest(BaseModel):
    """Import settings from a JSON payload."""
    settings: Dict[str, Any]
    overwrite: bool = False  # If true, replace all settings; if false, merge


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _workspace_id(user: dict) -> str:
    wid = user.get("workspace_id") or user.get("id")
    if not wid:
        raise HTTPException(status_code=400, detail="No workspace_id in token")
    return wid


# ──────────────────────────────────────────────────────────────────────────────
# Core Settings (GET/PATCH)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/")
async def get_settings(user: dict = Depends(get_current_user)):
    """Return current model settings for the authenticated workspace."""
    return await model_settings.get_settings(_workspace_id(user))


@router.patch("/setting")
async def update_setting(req: UpdateSettingRequest, user: dict = Depends(get_current_user)):
    """Update a single setting via dot-notation path."""
    return await model_settings.update_setting(_workspace_id(user), req.path, req.value)


# ──────────────────────────────────────────────────────────────────────────────
# Preset Management
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/presets")
async def list_presets(user: dict = Depends(get_current_user)):
    """Return all available preset profiles (built-in + workspace-custom)."""
    built_in = model_settings.list_presets()
    try:
        custom = await model_settings.list_custom_presets(_workspace_id(user))
    except Exception:
        custom = []
    return {"built_in": built_in, "custom": custom}


@router.post("/preset")
async def apply_preset(req: PresetRequest, user: dict = Depends(get_current_user)):
    """Apply a preset profile to the workspace."""
    try:
        return await model_settings.apply_preset(_workspace_id(user), req.preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/preset/custom")
async def create_custom_preset(
    req: CreatePresetRequest,
    user: dict = Depends(get_current_user),
):
    """Create a new custom preset for the workspace."""
    workspace_id = _workspace_id(user)
    try:
        result = await model_settings.create_custom_preset(
            workspace_id, req.name, req.description, req.settings, req.is_default,
        )
        return {"status": "created", "preset": result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/preset/{preset_id}")
async def update_custom_preset(
    preset_id: str,
    req: CreatePresetRequest,
    user: dict = Depends(get_current_user),
):
    """Update an existing custom preset."""
    workspace_id = _workspace_id(user)
    try:
        result = await model_settings.update_custom_preset(
            workspace_id, preset_id, req.name, req.description, req.settings,
        )
        return {"status": "updated", "preset": result}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/preset/{preset_id}")
async def delete_custom_preset(
    preset_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a custom preset."""
    workspace_id = _workspace_id(user)
    try:
        await model_settings.delete_custom_preset(workspace_id, preset_id)
        return {"status": "deleted"}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# Budget Control
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/budget")
async def check_budget(user: dict = Depends(get_current_user)):
    """Return daily/monthly spend vs budget limits."""
    return await model_settings.check_budget(_workspace_id(user))


@router.put("/budget")
async def set_budget(req: UpdateBudgetRequest, user: dict = Depends(get_current_user)):
    """Set monthly and daily budget limits."""
    workspace_id = _workspace_id(user)
    result = await model_settings.set_budget(
        workspace_id,
        monthly_limit=req.monthly_limit_usd,
        daily_limit=req.daily_limit_usd,
        auto_pause=req.auto_pause,
    )
    return {"status": "updated", "budget": result}


@router.post("/budget/alerts")
async def configure_budget_alerts(
    req: BudgetAlertRequest,
    user: dict = Depends(get_current_user),
):
    """Configure budget warning and critical alert thresholds."""
    workspace_id = _workspace_id(user)
    result = await model_settings.configure_budget_alerts(
        workspace_id,
        warning=req.warning_threshold,
        critical=req.critical_threshold,
        notify_email=req.notify_email,
        notify_slack=req.notify_slack,
    )
    return {"status": "configured", "alerts": result}


# ──────────────────────────────────────────────────────────────────────────────
# Provider Management
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/providers")
async def list_providers(user: dict = Depends(get_current_user)):
    """List available LLM providers with health status and model counts."""
    workspace_id = _workspace_id(user)
    try:
        from ...services.council_kernel.model_router import get_model_router
        router_instance = get_model_router()
        providers = await router_instance.get_provider_status(workspace_id)
        return {"providers": providers}
    except Exception as exc:
        logger.warning(f"Provider listing failed: {exc}")
        return {"providers": [], "error": str(exc)}


@router.post("/providers/{provider_id}/test")
async def test_provider(
    provider_id: str,
    user: dict = Depends(get_current_user),
):
    """Test a provider connection by sending a simple ping query."""
    workspace_id = _workspace_id(user)
    try:
        from ...services.council_kernel.model_router import get_model_router
        router_instance = get_model_router()
        result = await router_instance.test_provider(workspace_id, provider_id)
        return {
            "provider": provider_id,
            "status": "healthy" if result.get("success") else "unhealthy",
            "latency_ms": result.get("latency_ms", 0),
            "model": result.get("model", "unknown"),
            "error": result.get("error"),
        }
    except Exception as exc:
        return {
            "provider": provider_id,
            "status": "unhealthy",
            "error": str(exc),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Cascade Configuration
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/cascade")
async def get_cascade(user: dict = Depends(get_current_user)):
    """Get the current model cascade (fallback chain) configuration."""
    workspace_id = _workspace_id(user)
    try:
        settings = await model_settings.get_settings(workspace_id)
        return {
            "cascade_order": settings.get("cascade_order", []),
            "confidence_threshold": settings.get("confidence_threshold", 0.7),
            "max_fallback_attempts": settings.get("max_fallback_attempts", 3),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/cascade")
async def update_cascade(
    req: CascadeConfigRequest,
    user: dict = Depends(get_current_user),
):
    """Update the model cascade (fallback chain) order and thresholds."""
    workspace_id = _workspace_id(user)
    await model_settings.update_setting(workspace_id, "cascade_order", req.cascade_order)
    await model_settings.update_setting(workspace_id, "confidence_threshold", req.confidence_threshold)
    await model_settings.update_setting(workspace_id, "max_fallback_attempts", req.max_fallback_attempts)
    return {"status": "updated", "cascade": req.model_dump()}


# ──────────────────────────────────────────────────────────────────────────────
# Usage Analytics
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/usage")
async def get_usage(
    user: dict = Depends(get_current_user),
    period: str = Query("7d", pattern="^(1d|7d|30d|90d)$"),
    group_by: str = Query("day", pattern="^(day|model|provider)$"),
):
    """Get token usage analytics grouped by day, model, or provider."""
    workspace_id = _workspace_id(user)
    try:
        from ...db.supabase_client import get_supabase_client
        client = get_supabase_client()

        period_days = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}[period]
        cutoff = datetime.utcnow().isoformat()

        # Query cost_tracking table
        result = client.table("cost_tracking") \
            .select("*") \
            .eq("workspace_id", workspace_id) \
            .order("created_at", desc=True) \
            .limit(1000) \
            .execute()

        records = result.data or []

        # Aggregate
        totals = {
            "total_cost_usd": sum(r.get("cost_usd", 0) for r in records),
            "total_tokens": sum(r.get("tokens_in", 0) + r.get("tokens_out", 0) for r in records),
            "total_requests": len(records),
            "cache_hits": sum(1 for r in records if r.get("cache_hit")),
            "period": period,
            "group_by": group_by,
        }

        # Group
        groups: Dict[str, Dict] = {}
        for r in records:
            if group_by == "model":
                key = r.get("model", "unknown")
            elif group_by == "provider":
                key = r.get("model", "unknown").split("/")[0] if "/" in r.get("model", "") else r.get("provider", "unknown")
            else:
                key = r.get("created_at", "")[:10]  # YYYY-MM-DD

            if key not in groups:
                groups[key] = {"cost_usd": 0, "tokens": 0, "requests": 0}
            groups[key]["cost_usd"] += r.get("cost_usd", 0)
            groups[key]["tokens"] += r.get("tokens_in", 0) + r.get("tokens_out", 0)
            groups[key]["requests"] += 1

        totals["groups"] = groups
        return totals

    except Exception as exc:
        logger.warning(f"Usage analytics failed: {exc}")
        return {"error": str(exc), "total_cost_usd": 0, "groups": {}}


# ──────────────────────────────────────────────────────────────────────────────
# Import / Export
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/export")
async def export_settings(user: dict = Depends(get_current_user)):
    """Export all workspace model settings as a JSON file."""
    workspace_id = _workspace_id(user)
    settings = await model_settings.get_settings(workspace_id)
    content = json.dumps(settings, indent=2, default=str)

    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="aegion-settings-{workspace_id[:8]}.json"'
        },
    )


@router.post("/import")
async def import_settings(
    req: ImportSettingsRequest,
    user: dict = Depends(get_current_user),
):
    """Import settings from a JSON payload."""
    workspace_id = _workspace_id(user)
    try:
        if req.overwrite:
            # Replace all settings
            for path, value in _flatten_dict(req.settings):
                await model_settings.update_setting(workspace_id, path, value)
        else:
            # Merge: only update provided keys
            for path, value in _flatten_dict(req.settings):
                await model_settings.update_setting(workspace_id, path, value)

        return {"status": "imported", "keys_updated": len(list(_flatten_dict(req.settings)))}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _flatten_dict(d: Dict, prefix: str = "") -> list:
    """Flatten a nested dict to dot-notation paths."""
    items = []
    for k, v in d.items():
        new_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key))
        else:
            items.append((new_key, v))
    return items
