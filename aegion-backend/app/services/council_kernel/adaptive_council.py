"""
Adaptive Council — Phase 77: Right-size the council based on query complexity.

Maps Gateway-classified complexity → model count + council strategy.
Replaces the flat "run all providers" approach with a cost-proportional selection:

  simple   → 1 model  (cascade, cheapest first)
  medium   → 2 models (peer review, cheap pair)
  complex  → 3 models (full parent debate)
  critical → 4 models (full parent + red team)

Expected savings: 40–60% on an average query mix.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .model_router import MODEL_CATALOG, ModelRouter
from .types import CouncilProfile

# ---------------------------------------------------------------------------
# Policy map: complexity string → council configuration
# ---------------------------------------------------------------------------

SIZE_POLICIES: Dict[str, Dict] = {
    "simple": {
        "model_count": 1,
        "council_type": "child",
        "strategy": "cascade",        # Single cheapest model via FrugalGPT cascade
        "max_rounds": 1,
        "prefer_cheap": True,
        "description": "Single model, direct answer",
    },
    "medium": {
        "model_count": 2,
        "council_type": "child",
        "strategy": "peer_review",    # Two cheapest models cross-check each other
        "max_rounds": 1,
        "prefer_cheap": True,
        "description": "Two models with peer review",
    },
    "complex": {
        "model_count": 3,
        "council_type": "parent",
        "strategy": "full_debate",    # Debate + personas + evidence
        "max_rounds": 3,
        "prefer_cheap": False,        # Quality matters here
        "description": "Full council with structured debate",
    },
    "critical": {
        "model_count": 4,
        "council_type": "parent",
        "strategy": "full_debate_with_red_team",  # Full council + red team
        "max_rounds": 3,
        "prefer_cheap": False,
        "description": "Full council + adversarial red team validation",
    },
}

# Priority order for cheap selection (cheapest first)
_CHEAP_PRIORITY = ["deepseek", "google", "ollama", "mistral", "xai", "cohere", "openai", "anthropic"]

# Priority order for quality selection (best first)
_QUALITY_PRIORITY = ["anthropic", "openai", "google", "xai", "mistral", "deepseek", "cohere", "ollama"]


# ---------------------------------------------------------------------------
# Profile → complexity string mapping (bridge to existing CouncilProfile enum)
# ---------------------------------------------------------------------------

PROFILE_TO_COMPLEXITY: Dict[str, str] = {
    "trivial":  "simple",
    "simple":   "simple",
    "moderate": "medium",
    "complex":  "complex",
    "critical": "critical",
}


class AdaptiveCouncil:
    """
    Adaptive council sizer.

    Usage in engine.py:
        policy = adaptive_council.get_council_config(
            complexity=context.get("_gateway_complexity", "medium"),
            user_override={"model_count": 2},  # optional override from Model Settings
        )
        model_slots = adaptive_council.select_models(
            self.model_router, count=policy["model_count"],
            prefer_cheap=policy["prefer_cheap"],
        )
    """

    def get_council_config(
        self,
        complexity: str,
        user_override: Optional[Dict] = None,
    ) -> Dict:
        """
        Return council configuration for the given complexity.

        Args:
            complexity: "simple" | "medium" | "complex" | "critical"
            user_override: Any field from SIZE_POLICIES can be overridden.

        Returns:
            dict with model_count, council_type, strategy, max_rounds, etc.
        """
        # Normalise complexity; fall back to "medium"
        normalised = complexity.lower().strip() if complexity else "medium"
        # Accept CouncilProfile.value strings (e.g. "moderate" → "medium")
        normalised = PROFILE_TO_COMPLEXITY.get(normalised, normalised)
        config = SIZE_POLICIES.get(normalised, SIZE_POLICIES["medium"]).copy()

        # Apply user overrides (from Model Settings page)
        if user_override:
            config.update({k: v for k, v in user_override.items() if v is not None})

        return config

    def select_models(
        self,
        model_router: ModelRouter,
        count: int,
        prefer_cheap: bool = True,
    ) -> List[Tuple[str, str]]:
        """
        Select `count` (provider, model_id) pairs from registered providers.

        Args:
            model_router: Live ModelRouter with registered providers.
            count: How many models to pick.
            prefer_cheap: True → cheapest first, False → quality first.

        Returns:
            List of (provider_name, model_id) tuples, length ≤ count.
        """
        if not model_router.providers:
            return []

        priority = _CHEAP_PRIORITY if prefer_cheap else _QUALITY_PRIORITY
        available = set(model_router.providers.keys())

        selected: List[Tuple[str, str]] = []
        for provider_name in priority:
            if len(selected) >= count:
                break
            if provider_name not in available:
                continue

            provider = model_router.providers[provider_name]
            models = list(provider.models.keys()) if provider.models else []
            if not models:
                continue

            # Pick cheapest or best model in this provider
            if prefer_cheap:
                best_model = min(
                    models,
                    key=lambda m: MODEL_CATALOG.get(m).input_price_per_m
                    if MODEL_CATALOG.get(m) else 9999,
                )
            else:
                best_model = max(
                    models,
                    key=lambda m: MODEL_CATALOG.get(m).tier
                    if MODEL_CATALOG.get(m) else 0,
                )

            selected.append((provider_name, best_model))

        return selected

    def profile_to_complexity(self, profile: CouncilProfile) -> str:
        """Convert CouncilProfile enum to a complexity string."""
        return PROFILE_TO_COMPLEXITY.get(profile.value, "medium")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

adaptive_council = AdaptiveCouncil()
