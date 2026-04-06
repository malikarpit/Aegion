"""
Aegion Model Registry — Phase 84 (Elevated): Persistent Workspace Settings.

Multi-model routing profiles with:
  - Supabase persistence — workspace→profile survives restarts
  - Custom provider profiles — users can register any OpenAI-compatible API
  - API key storage — per-workspace API keys stored in vault
  - Profile capabilities matching — select models by required capabilities
  - WorkspaceCouncilConfig — per-workspace ACK advanced feature toggles

Built-in profiles: fast (Gemini Flash), quality (Gemini Pro), code (Gemini Flash),
                   anthropic (Claude), openai (GPT-4o)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

from ..core.logging import logger


class CostTier(str, Enum):
    FREE = "free"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ModelProfile(BaseModel):
    """A model routing profile."""
    profile_id: str
    name: str
    provider: str  # google, openai, anthropic, local, custom
    model_id: str  # e.g. gemini-2.0-flash, gpt-4o
    display_name: str
    context_window: int
    cost_tier: CostTier
    capabilities: List[str]  # code, chat, reasoning, multimodal
    max_output_tokens: int = 8192
    description: str = ""
    api_base_url: Optional[str] = None  # For custom providers


class WorkspaceCouncilConfig(BaseModel):
    """
    Per-workspace ACK advanced pipeline configuration.

    All features default to OFF — opt-in through settings page.
    Every budget/limit is configurable, nothing is hardcoded.
    """

    # ── MCTS Reasoning (Phase 45 wiring) ──
    mcts_enabled: bool = False
    mcts_max_budget_usd: float = 0.10
    mcts_max_iterations: int = 4
    mcts_branch_factor: int = 2
    mcts_max_depth: int = 4
    mcts_exploration_c: float = 1.414  # UCB1 exploration constant

    # ── DAG Pipeline (Phase 44 wiring) ──
    dag_pipeline_enabled: bool = False  # False = legacy sequential, True = DAG executor
    dag_max_retries: int = 2
    dag_timeout_seconds: float = 120.0

    # ── Cognitive Reflector (Phase 47) ──
    reflector_enabled: bool = False
    reflector_groupthink_threshold: float = 0.90  # Consensus above this in round 1 = groupthink
    reflector_circular_window: int = 2  # Compare round N with N-2 for circular reasoning

    # ── Red Team (Phase 48) ──
    red_team_enabled: bool = False
    red_team_max_budget_usd: float = 0.02
    red_team_min_score: float = 0.5  # Below this = flag the result

    # ── Temporal Memory (Phase 49) ──
    temporal_memory_enabled: bool = False
    temporal_recall_top_k: int = 3
    temporal_outcome_window_days: int = 30

    # ── Cross-Council Orchestration (Phase 50) ──
    cross_council_enabled: bool = False
    cross_council_max_sub_councils: int = 3
    cross_council_sub_budget_usd: float = 0.05
    cross_council_total_budget_usd: float = 0.20

    # ── Constitutional AI (Phase 46 wiring) ──
    constitution_enforcement: bool = True  # ON by default — safety critical
    constitution_block_on_violation: bool = True

    # ── Synthesis Mode ──
    weighted_synthesis_enabled: bool = False  # False = pick best response, True = LLM merge
    synthesis_merge_budget_usd: float = 0.03

    # ── Cost Optimization — Phase 76 / 77 ──
    gateway_enabled: bool = True           # Phase 76: Prompt Gateway pre-processing
    adaptive_council_enabled: bool = True  # Phase 77: Dynamic model count sizing

    # ── Cost Optimization — Phase 78 ──
    token_budget_enabled: bool = True      # Phase 78: Dynamic max_tokens per call
    token_budget_override: Optional[int] = None  # User-set max_tokens cap (None = auto)

    # ── Cost Optimization — Phase 79 ──
    context_pruning_enabled: bool = True   # Phase 79: Compress old conversation turns
    context_keep_recent: int = 3           # How many recent turns to keep verbatim

    # ── Cost Optimization — Phase 80 ──
    early_consensus_enabled: bool = True   # Phase 80: Exit debate early on consensus

    # ── Cost Optimization — Phase 81 ──
    speculative_enabled: bool = False      # Phase 81: Draft-verify pattern (opt-in)

    # ── Cost Optimization — Phase 83 ──
    rag_enabled: bool = True               # Phase 83: Inject workspace knowledge pre-query
    rag_max_context_tokens: int = 500      # Max tokens of RAG context to prepend

# Default config (all features off except constitution)
_DEFAULT_COUNCIL_CONFIG = WorkspaceCouncilConfig()


# ========== Built-in Profiles ==========

DEFAULT_PROFILES: Dict[str, ModelProfile] = {
    "fast": ModelProfile(
        profile_id="fast",
        name="fast",
        provider="google",
        model_id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        context_window=1_000_000,
        cost_tier=CostTier.LOW,
        capabilities=["code", "chat", "reasoning"],
        max_output_tokens=8192,
        description="Fast, cost-effective model for quick operations",
    ),
    "quality": ModelProfile(
        profile_id="quality",
        name="quality",
        provider="google",
        model_id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        context_window=1_000_000,
        cost_tier=CostTier.HIGH,
        capabilities=["code", "chat", "reasoning", "multimodal"],
        max_output_tokens=65536,
        description="Highest quality model for complex reasoning and code",
    ),
    "code": ModelProfile(
        profile_id="code",
        name="code",
        provider="google",
        model_id="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        context_window=1_000_000,
        cost_tier=CostTier.MEDIUM,
        capabilities=["code", "reasoning"],
        max_output_tokens=65536,
        description="Balanced model optimized for code tasks",
    ),
    "anthropic": ModelProfile(
        profile_id="anthropic",
        name="anthropic",
        provider="anthropic",
        model_id="claude-sonnet-4-20250514",
        display_name="Claude Sonnet 4",
        context_window=200_000,
        cost_tier=CostTier.HIGH,
        capabilities=["code", "chat", "reasoning"],
        max_output_tokens=8192,
        description="Anthropic Claude for complex reasoning tasks",
    ),
    "openai": ModelProfile(
        profile_id="openai",
        name="openai",
        provider="openai",
        model_id="gpt-4o",
        display_name="GPT-4o",
        context_window=128_000,
        cost_tier=CostTier.HIGH,
        capabilities=["code", "chat", "reasoning", "multimodal"],
        max_output_tokens=16384,
        description="OpenAI GPT-4o for general-purpose tasks",
    ),
}

# In-memory stores (loaded from DB on init)
_custom_profiles: Dict[str, ModelProfile] = {}
_workspace_profiles: Dict[str, str] = {}
_workspace_api_keys: Dict[str, Dict[str, str]] = {}  # workspace_id → {provider: key}
_workspace_council_configs: Dict[str, WorkspaceCouncilConfig] = {}  # workspace_id → config


class ModelRegistry:
    """
    Selects and manages model profiles with Supabase persistence.
    """

    def __init__(self) -> None:
        self._loaded = False

    async def initialize(self) -> None:
        """Load workspace settings from Supabase on startup."""
        if self._loaded:
            return
        try:
            from ..db.supabase_client import get_supabase_client
            client = get_supabase_client()

            # Load workspace→profile mappings
            result = client.table("workspace_model_settings").select(
                "workspace_id,active_profile,council_config"
            ).execute()
            for row in (result.data or []):
                _workspace_profiles[row["workspace_id"]] = row["active_profile"]
                if row.get("council_config"):
                    try:
                        _workspace_council_configs[row["workspace_id"]] = WorkspaceCouncilConfig(
                            **row["council_config"]
                        )
                    except Exception:
                        pass

            # Load custom profiles
            result = client.table("custom_model_profiles").select("*").execute()
            for row in (result.data or []):
                try:
                    profile = ModelProfile(**row["profile_data"])
                    _custom_profiles[profile.name] = profile
                except Exception:
                    pass

            self._loaded = True
            logger.info(
                f"Model registry loaded: {len(_workspace_profiles)} workspace settings, "
                f"{len(_custom_profiles)} custom profiles, "
                f"{len(_workspace_council_configs)} council configs"
            )
        except Exception as exc:
            logger.warning(f"Model registry DB init failed (using defaults): {exc}")
            self._loaded = True

    def get_profile(self, name: str) -> Optional[ModelProfile]:
        return _custom_profiles.get(name) or DEFAULT_PROFILES.get(name)

    def list_profiles(self) -> List[ModelProfile]:
        all_profiles = {**DEFAULT_PROFILES, **_custom_profiles}
        return list(all_profiles.values())

    def select_model(
        self,
        task_type: str = "general",
        preference: str = "quality",
        required_capabilities: Optional[List[str]] = None,
    ) -> ModelProfile:
        """
        Select the best model for a task.

        Priority: direct preference → capability match → task heuristics
        """
        # Direct preference match
        profile = self.get_profile(preference)
        if profile:
            if required_capabilities:
                if all(cap in profile.capabilities for cap in required_capabilities):
                    return profile
            else:
                return profile

        # Capability-based selection
        if required_capabilities:
            for p in self.list_profiles():
                if all(cap in p.capabilities for cap in required_capabilities):
                    return p

        # Task-type heuristics
        type_map = {
            "code": "code", "coding": "code", "debug": "code", "transform": "code",
            "chat": "fast", "question": "fast",
            "analysis": "quality", "reasoning": "quality", "architecture": "quality",
            "security": "anthropic",  # Claude is good at security analysis
        }
        preferred = type_map.get(task_type, "quality")
        return self.get_profile(preferred) or DEFAULT_PROFILES["quality"]

    def register_custom(
        self,
        profile: ModelProfile,
        persist: bool = True,
    ) -> ModelProfile:
        """Register a custom model profile."""
        _custom_profiles[profile.name] = profile
        logger.info(f"Custom model profile registered: {profile.name} ({profile.model_id})")

        if persist:
            self._persist_profile(profile)
        return profile

    def set_active(
        self,
        workspace_id: str,
        profile_name: str,
        persist: bool = True,
    ) -> bool:
        """Set the active model profile for a workspace."""
        if not self.get_profile(profile_name):
            return False
        _workspace_profiles[workspace_id] = profile_name

        if persist:
            self._persist_workspace_setting(workspace_id, profile_name)
        return True

    def get_active(self, workspace_id: str) -> ModelProfile:
        name = _workspace_profiles.get(workspace_id, "quality")
        return self.get_profile(name) or DEFAULT_PROFILES["quality"]

    def store_api_key(
        self,
        workspace_id: str,
        provider: str,
        api_key: str,
    ) -> bool:
        """Store a provider API key for a workspace (uses vault for encryption)."""
        try:
            from .vault import get_vault
            vault = get_vault()
            vault_key = f"api_key:{workspace_id}:{provider}"
            vault.store_secret(
                vault_key, api_key,
                workspace_id=workspace_id,
                actor_id="model_registry",
            )
            if workspace_id not in _workspace_api_keys:
                _workspace_api_keys[workspace_id] = {}
            _workspace_api_keys[workspace_id][provider] = vault_key
            return True
        except Exception as exc:
            logger.warning(f"API key storage failed: {exc}")
            return False

    def get_api_key(self, workspace_id: str, provider: str) -> Optional[str]:
        """Retrieve a provider API key for a workspace."""
        try:
            from .vault import get_vault
            vault = get_vault()
            vault_key = f"api_key:{workspace_id}:{provider}"
            return vault.get_secret(vault_key, actor_id="model_registry")
        except Exception:
            return None

    def delete_custom(self, profile_name: str) -> bool:
        """Delete a custom profile. Cannot delete built-in profiles."""
        if profile_name in DEFAULT_PROFILES:
            return False
        if profile_name in _custom_profiles:
            del _custom_profiles[profile_name]
            self._delete_persisted_profile(profile_name)
            return True
        return False

    # ──────────────────────────────────────────────
    # Council Config (ACK advanced feature toggles)
    # ──────────────────────────────────────────────

    def get_council_config(self, workspace_id: str) -> WorkspaceCouncilConfig:
        """Get the ACK advanced pipeline config for a workspace."""
        return _workspace_council_configs.get(workspace_id, _DEFAULT_COUNCIL_CONFIG)

    def set_council_config(
        self,
        workspace_id: str,
        config: WorkspaceCouncilConfig,
        persist: bool = True,
    ) -> WorkspaceCouncilConfig:
        """Set and persist the ACK advanced pipeline config for a workspace."""
        _workspace_council_configs[workspace_id] = config
        if persist:
            self._persist_council_config(workspace_id, config)
        logger.info(f"Council config updated for {workspace_id}")
        return config

    def update_council_config(
        self,
        workspace_id: str,
        updates: Dict[str, Any],
        persist: bool = True,
    ) -> WorkspaceCouncilConfig:
        """
        Partially update council config — only change specified fields.

        Usage:
            registry.update_council_config("ws-123", {
                "mcts_enabled": True,
                "mcts_max_budget_usd": 0.25,
            })
        """
        current = self.get_council_config(workspace_id)
        updated_data = current.model_dump()
        updated_data.update(updates)
        new_config = WorkspaceCouncilConfig(**updated_data)
        return self.set_council_config(workspace_id, new_config, persist=persist)

    def _persist_council_config(self, workspace_id: str, config: WorkspaceCouncilConfig) -> None:
        try:
            from ..db.supabase_client import get_supabase_client
            get_supabase_client().table("workspace_model_settings").upsert({
                "workspace_id": workspace_id,
                "active_profile": _workspace_profiles.get(workspace_id, "quality"),
                "council_config": config.model_dump(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="workspace_id").execute()
        except Exception as exc:
            logger.warning(f"Council config persist failed: {exc}")

    # ──────────────────────────────────────────────
    # Persistence helpers
    # ──────────────────────────────────────────────

    def _persist_profile(self, profile: ModelProfile) -> None:
        try:
            from ..db.supabase_client import get_supabase_client
            get_supabase_client().table("custom_model_profiles").upsert({
                "name": profile.name,
                "profile_data": profile.model_dump(),
            }, on_conflict="name").execute()
        except Exception as exc:
            logger.warning(f"Profile persist failed: {exc}")

    def _delete_persisted_profile(self, name: str) -> None:
        try:
            from ..db.supabase_client import get_supabase_client
            get_supabase_client().table("custom_model_profiles").delete().eq("name", name).execute()
        except Exception:
            pass

    def _persist_workspace_setting(self, workspace_id: str, profile_name: str) -> None:
        try:
            from ..db.supabase_client import get_supabase_client
            get_supabase_client().table("workspace_model_settings").upsert({
                "workspace_id": workspace_id,
                "active_profile": profile_name,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="workspace_id").execute()
        except Exception as exc:
            logger.warning(f"Workspace setting persist failed: {exc}")


# Singleton
_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
