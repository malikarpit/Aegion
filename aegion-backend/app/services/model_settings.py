"""
Model Settings Engine — Phase 84: Full per-workspace model configuration.

Five preset profiles with one-click application, dot-notation partial overrides,
budget tracking, and full CRUD. Users can override any parameter while the engine
tracks which settings deviate from the preset baseline.

Presets: cost_saver | balanced | quality_first | no_limits | privacy_first
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..core.logging import logger


# ---------------------------------------------------------------------------
# Preset profiles
# ---------------------------------------------------------------------------

PRESET_PROFILES: Dict[str, Dict] = {
    "cost_saver": {
        "name": "Cost Saver", "icon": "🟢",
        "description": "Minimize cost, use cheapest models",
        "council": {"default_size": 1, "max_size": 2, "prefer_cheap": True},
        "cascade": {"enabled": True, "order": ["deepseek", "google", "ollama"],
                    "confidence_threshold": 0.75},
        "cache":   {"enabled": True, "similarity_threshold": 0.85},
        "compression": {"enabled": True, "min_words": 50, "target_ratio": 0.25},
        "gateway": {"enabled": True, "auto_optimize": True},
        "budget":  {"daily_limit_usd": 1.0, "monthly_limit_usd": 25.0},
        "models":  {"primary": ("deepseek", "deepseek-chat"),
                    "secondary": ("google", "gemini-2.0-flash"),
                    "fallback": ("ollama", "llama3")},
        "token_limits": {"simple": 300, "medium": 600, "complex": 1200},
        "temperature": {"default": 0.3, "creative": 0.6},
    },
    "balanced": {
        "name": "Balanced", "icon": "🔵",
        "description": "Good quality at reasonable cost (recommended)",
        "council": {"default_size": 2, "max_size": 3, "prefer_cheap": True},
        "cascade": {"enabled": True,
                    "order": ["google", "deepseek", "anthropic", "openai"],
                    "confidence_threshold": 0.85},
        "cache":   {"enabled": True, "similarity_threshold": 0.92},
        "compression": {"enabled": True, "min_words": 100, "target_ratio": 0.3},
        "gateway": {"enabled": True, "auto_optimize": True},
        "budget":  {"daily_limit_usd": 5.0, "monthly_limit_usd": 100.0},
        "models":  {"primary": ("google", "gemini-2.0-flash"),
                    "secondary": ("anthropic", "claude-haiku-3-5-20241022"),
                    "fallback": ("deepseek", "deepseek-chat")},
        "token_limits": {"simple": 500, "medium": 1000, "complex": 2000},
        "temperature": {"default": 0.5, "creative": 0.7},
    },
    "quality_first": {
        "name": "Quality First", "icon": "🟡",
        "description": "Best models, full council debates",
        "council": {"default_size": 3, "max_size": 4, "prefer_cheap": False},
        "cascade": {"enabled": True,
                    "order": ["anthropic", "openai", "google"],
                    "confidence_threshold": 0.92},
        "cache":   {"enabled": True, "similarity_threshold": 0.95},
        "compression": {"enabled": True, "min_words": 500, "target_ratio": 0.4},
        "gateway": {"enabled": True, "auto_optimize": False},
        "budget":  {"daily_limit_usd": 20.0, "monthly_limit_usd": 400.0},
        "models":  {"primary": ("anthropic", "claude-sonnet-4-20250514"),
                    "secondary": ("openai", "gpt-4.1"),
                    "fallback": ("google", "gemini-2.5-pro-preview-06-05")},
        "token_limits": {"simple": 1000, "medium": 2000, "complex": 4000},
        "temperature": {"default": 0.5, "creative": 0.8},
    },
    "no_limits": {
        "name": "No Limits", "icon": "🔴",
        "description": "Maximum quality, no restrictions",
        "council": {"default_size": 4, "max_size": 6, "prefer_cheap": False},
        "cascade": {"enabled": False, "order": [], "confidence_threshold": 0.0},
        "cache":   {"enabled": False, "similarity_threshold": 1.0},
        "compression": {"enabled": False, "min_words": 99999, "target_ratio": 1.0},
        "gateway": {"enabled": True, "auto_optimize": False},
        "budget":  {"daily_limit_usd": None, "monthly_limit_usd": None},
        "models":  {"primary": ("anthropic", "claude-sonnet-4-20250514"),
                    "secondary": ("openai", "gpt-4.1"),
                    "fallback": ("google", "gemini-2.5-pro-preview-06-05")},
        "token_limits": {"simple": 2000, "medium": 4000, "complex": 8000},
        "temperature": {"default": 0.5, "creative": 0.9},
    },
    "privacy_first": {
        "name": "Privacy First", "icon": "🟣",
        "description": "Local models only, no cloud API calls",
        "council": {"default_size": 1, "max_size": 3, "prefer_cheap": True},
        "cascade": {"enabled": True, "order": ["ollama"],
                    "confidence_threshold": 0.7},
        "cache":   {"enabled": True, "similarity_threshold": 0.88},
        "compression": {"enabled": True, "min_words": 50, "target_ratio": 0.3},
        "gateway": {"enabled": False, "auto_optimize": False},
        "budget":  {"daily_limit_usd": 0.0, "monthly_limit_usd": 0.0},
        "models":  {"primary": ("ollama", "llama3"),
                    "secondary": ("ollama", "codellama"),
                    "fallback": ("ollama", "mistral")},
        "token_limits": {"simple": 500, "medium": 1000, "complex": 2000},
        "temperature": {"default": 0.4, "creative": 0.7},
    },
}


class ModelSettingsEngine:
    """Per-workspace model configuration with preset profiles and custom overrides."""

    async def get_settings(self, workspace_id: str) -> Dict:
        """Return current settings, defaulting to 'balanced' if none saved."""
        try:
            from ..db.supabase_client import get_supabase_client
            result = (
                get_supabase_client()
                .table("model_settings")
                .select("*")
                .eq("workspace_id", workspace_id)
                .maybe_single()
                .execute()
            )
            if result.data:
                return result.data
        except Exception as exc:
            logger.warning(f"Could not fetch model settings from DB: {exc}")

        # Return in-memory balanced default
        return self._make_settings_record(workspace_id, "balanced")

    async def apply_preset(self, workspace_id: str, preset_name: str) -> Dict:
        """Apply a named preset profile to the workspace."""
        if preset_name not in PRESET_PROFILES:
            raise ValueError(f"Unknown preset: {preset_name!r}")

        record = self._make_settings_record(workspace_id, preset_name)

        try:
            from ..db.supabase_client import get_supabase_client
            get_supabase_client().table("model_settings").upsert(
                record, on_conflict="workspace_id"
            ).execute()
        except Exception as exc:
            logger.warning(f"Could not persist preset to DB (returning in-memory): {exc}")

        return record

    async def update_setting(self, workspace_id: str, path: str, value: Any) -> Dict:
        """
        Update a specific setting via dot-notation path (e.g. 'council.default_size').
        """
        current = await self.get_settings(workspace_id)
        settings = copy.deepcopy(current.get("settings", {}))
        overrides = copy.deepcopy(current.get("custom_overrides", {}))

        # Navigate and set
        keys = path.split(".")
        target = settings
        for key in keys[:-1]:
            target = target.setdefault(key, {})
        target[keys[-1]] = value
        overrides[path] = value

        try:
            from ...db.supabase_client import get_supabase_client
            get_supabase_client().table("model_settings").update({
                "settings": settings,
                "custom_overrides": overrides,
                "active_preset": "custom",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("workspace_id", workspace_id).execute()
        except Exception as exc:
            logger.warning(f"Could not persist setting update: {exc}")

        return await self.get_settings(workspace_id)

    async def check_budget(self, workspace_id: str) -> Dict:
        """Return budget status: daily/monthly spend vs limits."""
        settings = await self.get_settings(workspace_id)
        budget = settings.get("settings", {}).get("budget", {})
        daily_limit = budget.get("daily_limit_usd")
        monthly_limit = budget.get("monthly_limit_usd")

        daily_spend, monthly_spend = 0.0, 0.0
        try:
            from ...db.supabase_client import get_supabase_client
            client = get_supabase_client()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            this_month = datetime.now(timezone.utc).strftime("%Y-%m")

            daily = (
                client.table("cost_tracking").select("cost_usd")
                .eq("workspace_id", workspace_id)
                .gte("created_at", today)
                .execute()
            )
            daily_spend = sum(r.get("cost_usd", 0.0) for r in (daily.data or []))

            monthly = (
                client.table("cost_tracking").select("cost_usd")
                .eq("workspace_id", workspace_id)
                .gte("created_at", this_month)
                .execute()
            )
            monthly_spend = sum(r.get("cost_usd", 0.0) for r in (monthly.data or []))
        except Exception:
            pass  # Non-fatal; return zeros if DB unavailable

        return {
            "daily_spend":      round(daily_spend, 4),
            "daily_limit":      daily_limit,
            "daily_remaining":  round(daily_limit - daily_spend, 4) if daily_limit is not None else None,
            "budget_exceeded":  daily_limit is not None and daily_spend >= daily_limit,
            "monthly_spend":    round(monthly_spend, 4),
            "monthly_limit":    monthly_limit,
            "monthly_remaining": round(monthly_limit - monthly_spend, 4) if monthly_limit is not None else None,
        }

    def list_presets(self) -> List[Dict]:
        """Return all preset definitions for the UI."""
        return [
            {
                "key":         k,
                "name":        v["name"],
                "icon":        v["icon"],
                "description": v["description"],
                "budget":      v.get("budget", {}),
                "council":     v.get("council", {}),
            }
            for k, v in PRESET_PROFILES.items()
        ]

    # ──────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────

    def _make_settings_record(self, workspace_id: str, preset_name: str) -> Dict:
        return {
            "workspace_id":    workspace_id,
            "active_preset":   preset_name,
            "settings":        copy.deepcopy(PRESET_PROFILES[preset_name]),
            "custom_overrides": {},
            "updated_at":      datetime.now(timezone.utc).isoformat(),
        }


# Module-level singleton
model_settings = ModelSettingsEngine()


# ---------------------------------------------------------------------------
# SQL migration (run once in Supabase):
# ---------------------------------------------------------------------------
MODEL_SETTINGS_SQL = """
CREATE TABLE IF NOT EXISTS model_settings (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     UUID NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
    active_preset    TEXT NOT NULL DEFAULT 'balanced',
    settings         JSONB NOT NULL DEFAULT '{}',
    custom_overrides JSONB DEFAULT '{}',
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);
"""
