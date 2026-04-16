"""
Constitutional AI Policy Loader — Phase 102.

Loads governance rules from constitution.yaml and exposes them
as typed Python objects for the council engine and sentinel.

Supports workspace-level overrides: if `.aegion/constitution.yaml`
exists in the workspace root, it merges with the system default.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...core.logging import logger

# Try to import yaml, fall back gracefully
try:
    import yaml  # type: ignore
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


_DEFAULT_PATH = Path(__file__).parent / "constitution.yaml"


class ConstitutionPolicy:
    """Parsed constitutional AI policy."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data

    @property
    def decision_tiers(self) -> Dict[str, Dict[str, Any]]:
        return self._data.get("decision_tiers", {})

    @property
    def sentinel_hard_blocks(self) -> List[Dict[str, Any]]:
        return self._data.get("sentinel", {}).get("hard_blocks", [])

    @property
    def sentinel_warnings(self) -> List[Dict[str, Any]]:
        return self._data.get("sentinel", {}).get("warnings", [])

    @property
    def daily_budget_usd(self) -> float:
        return self._data.get("cost", {}).get("daily_budget_usd", 10.0)

    @property
    def per_request_caps(self) -> Dict[str, float]:
        return self._data.get("cost", {}).get("per_request_caps", {})

    @property
    def cascade_confidence_threshold(self) -> float:
        return self._data.get("cost", {}).get("cascade", {}).get("confidence_threshold", 0.75)

    @property
    def council_quorum(self) -> int:
        return self._data.get("council", {}).get("quorum", 2)

    @property
    def consensus_threshold(self) -> float:
        return self._data.get("council", {}).get("consensus_threshold", 0.7)

    @property
    def default_roles(self) -> List[Dict[str, Any]]:
        return self._data.get("council", {}).get("default_roles", [])

    def get_tier_config(self, tier: str) -> Dict[str, Any]:
        """Get configuration for a specific tier (T0, T1, T2, T3)."""
        return self.decision_tiers.get(tier, {})

    def tier_requires_human(self, tier: str) -> bool:
        """Check if a tier requires human approval."""
        return self.get_tier_config(tier).get("requires_human", True)

    def tier_debate_rounds(self, tier: str) -> int:
        """Get the number of debate rounds for a tier."""
        return self.get_tier_config(tier).get("debate_rounds", 1)

    def to_dict(self) -> Dict[str, Any]:
        """Export the full policy as a dict (for API responses)."""
        return self._data


def load_constitution(workspace_path: Optional[str] = None) -> ConstitutionPolicy:
    """
    Load the constitutional AI policy.

    Priority:
      1. Workspace override: {workspace_path}/.aegion/constitution.yaml
      2. System default: app/services/council/constitution.yaml

    Workspace overrides are MERGED (deep update) with the system default,
    so workspace policies can selectively override specific sections.
    """
    if not _YAML_AVAILABLE:
        logger.warning("PyYAML not installed — using empty constitution policy")
        return ConstitutionPolicy({})

    # Load system default
    base_data: Dict[str, Any] = {}
    if _DEFAULT_PATH.exists():
        with open(_DEFAULT_PATH) as f:
            base_data = yaml.safe_load(f) or {}

    # Merge workspace override if available
    if workspace_path:
        ws_path = Path(workspace_path) / ".aegion" / "constitution.yaml"
        if ws_path.exists():
            with open(ws_path) as f:
                ws_data = yaml.safe_load(f) or {}
            base_data = _deep_merge(base_data, ws_data)
            logger.info(f"Constitution: merged workspace override from {ws_path}")

    return ConstitutionPolicy(base_data)


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Recursively merge override dict into base dict."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# Singleton
_constitution: Optional[ConstitutionPolicy] = None


def get_constitution(workspace_path: Optional[str] = None) -> ConstitutionPolicy:
    """Get the cached constitution policy."""
    global _constitution
    if _constitution is None:
        _constitution = load_constitution(workspace_path)
    return _constitution
