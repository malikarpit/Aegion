"""
Feature Flag Service for Aegion.

Manages the availability of features based on maturity tier (Stable/Beta/Experimental)
and user roles.
"""

import json
import os
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel

from .logging import logger

class FeatureTier(str, Enum):
    STABLE = "stable"
    BETA = "beta"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"

class FeatureFlag(BaseModel):
    name: str
    description: str
    tier: FeatureTier
    enabled: bool
    default_on: bool
    allowed_users: List[str] = []  # Empty = all allowed if enabled
    allowed_workspaces: List[str] = [] # Empty = all allowed

class FeatureFlagService:
    _instance = None
    _flags: Dict[str, FeatureFlag] = {}
    _config_path: str = "config/features.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FeatureFlagService, cls).__new__(cls)
            cls._instance._load_flags()
        return cls._instance

    def _load_flags(self):
        """Load flags from config file or defaults."""
        self._flags = {}
        
        # 1. Define Defaults (Code-as-Configuration)
        defaults = [
            FeatureFlag(
                name="ghost_text",
                description="AI Ghost Text completion in editor",
                tier=FeatureTier.BETA,
                enabled=True,
                default_on=True
            ),
            FeatureFlag(
                name="war_room",
                description="Real-time multi-user conflict resolution",
                tier=FeatureTier.EXPERIMENTAL,
                enabled=False, # Off by default
                default_on=False
            ),
            FeatureFlag(
                name="generate_adr",
                description="Generate Architectural Decision Records",
                tier=FeatureTier.BETA,
                enabled=True,
                default_on=True
            ),
             FeatureFlag(
                name="game_snake",
                description="Easter egg game",
                tier=FeatureTier.EXPERIMENTAL,
                enabled=False,
                default_on=False
            ),
            FeatureFlag(
                name="cloud_delegate",
                description="Delegate tasks to cloud workers",
                tier=FeatureTier.EXPERIMENTAL,
                enabled=False,
                default_on=False
            )
        ]
        
        for f in defaults:
            self._flags[f.name] = f
            
        # 2. Override from Config File
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r') as f:
                    config = json.load(f)
                    for name, settings in config.items():
                        if name in self._flags:
                            # Merge settings
                            current = self._flags[name]
                            if "enabled" in settings:
                                current.enabled = settings["enabled"]
            except Exception as e:
                logger.error(f"Failed to load feature flags from {self._config_path}: {e}")

    def is_enabled(self, feature_name: str, user_id: Optional[str] = None) -> bool:
        """Check if a feature is enabled."""
        flag = self._flags.get(feature_name)
        if not flag:
            return False
            
        if not flag.enabled:
            return False
            
        if user_id and flag.allowed_users:
            return user_id in flag.allowed_users
            
        return True

    def get_all_flags(self) -> Dict[str, bool]:
        """Get simple map of feature -> enabled status."""
        return {name: f.enabled for name, f in self._flags.items()}

    def get_full_manifest(self) -> List[FeatureFlag]:
        """Get full flag details."""
        return list(self._flags.values())

# Singleton accessor
def get_feature_flags() -> FeatureFlagService:
    return FeatureFlagService()
