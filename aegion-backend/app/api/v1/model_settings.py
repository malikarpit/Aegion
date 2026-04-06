"""Model Settings API — Phase 84: 5 endpoints for workspace model configuration."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from ...core.security import get_current_user
from ...services.model_settings import model_settings

router = APIRouter(prefix="/model-settings", tags=["Model Settings"])


class PresetRequest(BaseModel):
    preset: str  # cost_saver | balanced | quality_first | no_limits | privacy_first


class UpdateSettingRequest(BaseModel):
    path: str   # Dot-notation, e.g. "council.default_size"
    value: Any  # The new value


def _workspace_id(user: dict) -> str:
    wid = user.get("workspace_id") or user.get("id")
    if not wid:
        raise HTTPException(status_code=400, detail="No workspace_id in token")
    return wid


@router.get("/")
async def get_settings(user: dict = Depends(get_current_user)):
    """Return current model settings for the authenticated workspace."""
    return await model_settings.get_settings(_workspace_id(user))


@router.get("/presets")
async def list_presets():
    """Return all available preset profiles (public, no auth required)."""
    return model_settings.list_presets()


@router.post("/preset")
async def apply_preset(req: PresetRequest, user: dict = Depends(get_current_user)):
    """Apply a preset profile to the workspace."""
    try:
        return await model_settings.apply_preset(_workspace_id(user), req.preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/setting")
async def update_setting(req: UpdateSettingRequest, user: dict = Depends(get_current_user)):
    """Update a single setting via dot-notation path."""
    return await model_settings.update_setting(_workspace_id(user), req.path, req.value)


@router.get("/budget")
async def check_budget(user: dict = Depends(get_current_user)):
    """Return daily/monthly spend vs budget limits."""
    return await model_settings.check_budget(_workspace_id(user))
