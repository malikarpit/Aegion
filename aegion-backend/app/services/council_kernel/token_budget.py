"""
Token Budget Manager — Phase 78: Dynamic output token limits.

Maps (intent, complexity) → max_tokens + temperature to avoid over-generating.
Output tokens cost 2–3× more than input tokens; capping them here is one of the
highest-leverage cost improvements after adaptive council sizing (Phase 77).

Integration point in engine.py consult() — between Step 2 (classify) and Step 3 (route).
Budget is stored in context["_token_budget"] and picked up by _run_parallel().
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from .model_router import MODEL_CATALOG

# ---------------------------------------------------------------------------
# (intent, complexity) → {max_tokens, temperature}
# ---------------------------------------------------------------------------
# Intentionally conservative: users can raise limits via Model Settings (Phase 84).
# Format: (intent_str, complexity_str) → budget dict
# ---------------------------------------------------------------------------

BUDGETS: Dict[Tuple[str, str], Dict] = {
    # Debug / fix
    ("debug",        "simple"):   {"max_tokens": 300,  "temperature": 0.3},
    ("debug",        "medium"):   {"max_tokens": 800,  "temperature": 0.3},
    ("debug",        "complex"):  {"max_tokens": 1500, "temperature": 0.4},
    ("debug",        "critical"): {"max_tokens": 2500, "temperature": 0.4},
    # Explain / educate
    ("explain",      "simple"):   {"max_tokens": 500,  "temperature": 0.5},
    ("explain",      "medium"):   {"max_tokens": 1000, "temperature": 0.5},
    ("explain",      "complex"):  {"max_tokens": 2000, "temperature": 0.5},
    ("explain",      "critical"): {"max_tokens": 3000, "temperature": 0.5},
    # Generate (code, prose)
    ("generate",     "simple"):   {"max_tokens": 500,  "temperature": 0.7},
    ("generate",     "medium"):   {"max_tokens": 1500, "temperature": 0.7},
    ("generate",     "complex"):  {"max_tokens": 3000, "temperature": 0.7},
    ("generate",     "critical"): {"max_tokens": 6000, "temperature": 0.7},
    # Code review
    ("code_review",  "simple"):   {"max_tokens": 400,  "temperature": 0.2},
    ("code_review",  "medium"):   {"max_tokens": 1000, "temperature": 0.2},
    ("code_review",  "complex"):  {"max_tokens": 2000, "temperature": 0.3},
    ("code_review",  "critical"): {"max_tokens": 3500, "temperature": 0.3},
    # Architecture
    ("architecture", "simple"):   {"max_tokens": 800,  "temperature": 0.5},
    ("architecture", "medium"):   {"max_tokens": 2000, "temperature": 0.5},
    ("architecture", "complex"):  {"max_tokens": 4000, "temperature": 0.5},
    ("architecture", "critical"): {"max_tokens": 6000, "temperature": 0.5},
    # Security
    ("security",     "simple"):   {"max_tokens": 500,  "temperature": 0.2},
    ("security",     "medium"):   {"max_tokens": 1200, "temperature": 0.2},
    ("security",     "complex"):  {"max_tokens": 2500, "temperature": 0.3},
    ("security",     "critical"): {"max_tokens": 4000, "temperature": 0.3},
    # General / fallback
    ("general",      "simple"):   {"max_tokens": 600,  "temperature": 0.5},
    ("general",      "medium"):   {"max_tokens": 1200, "temperature": 0.5},
    ("general",      "complex"):  {"max_tokens": 2500, "temperature": 0.5},
    ("general",      "critical"): {"max_tokens": 4000, "temperature": 0.5},
}

# Absolute fallback when neither intent nor complexity is known
DEFAULT_BUDGET: Dict = {"max_tokens": 1000, "temperature": 0.5}


class TokenBudgetManager:
    """
    Provides dynamic max_tokens + temperature budgets per query.

    Usage:
        budget = token_budget.get_budget(
            intent=context.get("_gateway_intent", "general"),
            complexity=context.get("_gateway_complexity", "medium"),
            user_override=config.token_budget_override,
        )
        # Then pass to model_router.call(..., max_tokens=budget["max_tokens"], ...)
    """

    def get_budget(
        self,
        intent: str,
        complexity: str,
        user_override: Optional[int] = None,
    ) -> Dict:
        """
        Return token budget dict for the given (intent, complexity) pair.

        Args:
            intent:        Gateway-classified intent (e.g. "debug", "architecture").
            complexity:    Gateway-classified complexity ("simple"/"medium"/"complex"/"critical").
            user_override: If set, overrides max_tokens (from Model Settings page).

        Returns:
            dict with "max_tokens" and "temperature".
        """
        key = (intent.lower().strip(), complexity.lower().strip())
        budget = BUDGETS.get(key, DEFAULT_BUDGET).copy()

        if user_override and isinstance(user_override, int) and user_override > 0:
            budget["max_tokens"] = user_override

        return budget

    def estimate_output_cost(
        self,
        budget: Dict,
        model_id: str,
    ) -> float:
        """
        Estimate the cost ceiling for one LLM call given a budget.

        Uses live MODEL_CATALOG pricing so the estimate stays current.

        Args:
            budget:   Budget dict from get_budget().
            model_id: Model identifier (e.g. "gemini-2.0-flash").

        Returns:
            Estimated cost in USD at max_tokens output.
        """
        spec = MODEL_CATALOG.get(model_id)
        if not spec:
            return 0.0
        return (budget["max_tokens"] * spec.output_price_per_m) / 1_000_000

    def savings_estimate(
        self,
        budget: Dict,
        model_id: str,
        uncapped_default: int = 4096,
    ) -> float:
        """
        Estimate savings vs running with uncapped defaults.

        Args:
            budget:           Budget from get_budget().
            model_id:         Model ID.
            uncapped_default: Assumed uncapped token count (default 4096).

        Returns:
            Estimated USD savings.
        """
        spec = MODEL_CATALOG.get(model_id)
        if not spec:
            return 0.0
        saved_tokens = max(0, uncapped_default - budget["max_tokens"])
        return (saved_tokens * spec.output_price_per_m) / 1_000_000


# Module-level singleton
token_budget = TokenBudgetManager()
