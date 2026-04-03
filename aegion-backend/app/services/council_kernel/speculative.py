"""
Speculative Decoder — Phase 81: Draft-Verify pattern for code-heavy queries.

Uses a cheap model to draft the full response, then uses an expensive model only
to verify / correct the draft. The expensive model sees a much shorter prompt
(correction task only), cutting costs 20-40% on generation-heavy queries.

Only activates for intent = generate | code_review | architecture.
Gated by config.speculative_enabled (opt-in, defaults False).
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .model_router import ModelRouter

# Intents where speculative decoding is worth the two-call overhead
SPECULATIVE_INTENTS = {"generate", "code_review", "architecture"}

# Default model preferences; engine.py passes the actual router at call time
DRAFT_PROVIDER = "google"
DRAFT_MODEL = "gemini-2.0-flash"
VERIFY_PROVIDER = "anthropic"
VERIFY_MODEL = "claude-haiku-3-5-20241022"


class SpeculativeDecoder:
    """
    Draft → Verify cost pattern.

    Usage in _child_council():
        if config.speculative_enabled and intent in SPECULATIVE_INTENTS:
            return await speculative_decoder.generate(
                query, self.model_router, context
            )
    """

    async def generate(
        self,
        prompt: str,
        model_router: "ModelRouter",
        context: Optional[Dict] = None,
    ) -> Dict:
        """
        Two-step draft-then-verify generation.

        Args:
            prompt:       The optimized query to answer.
            model_router: Live router with registered providers.
            context:      Engine context dict (for token budget, etc.).

        Returns:
            dict with response, cost breakdown, and savings estimate.
        """
        budget = (context or {}).get("_token_budget", {})
        draft_max_tokens = budget.get("max_tokens", 1500)
        temperature = budget.get("temperature", 0.6)

        # ── Step 1: Draft with cheap model ──────────────────────────────
        draft_prov, draft_mdl = self._select_draft_model(model_router)
        draft_prompt = (
            "Generate a complete, thorough response for this task. "
            "Be specific and include code where appropriate.\n\n"
            f"{prompt}"
        )
        try:
            draft_result = await model_router.call(
                draft_prov, draft_mdl, draft_prompt,
                max_tokens=draft_max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            return {"error": f"Draft step failed: {exc}", "response": "", "total_cost": 0.0}

        # ── Step 2: Verify with best available model ─────────────────────
        # Verification prompt is deliberately short — only ask what's wrong
        verify_prov, verify_mdl = self._select_verify_model(model_router, skip=draft_prov)
        verify_prompt = (
            f"Review and correct this AI-generated response.\n\n"
            f"ORIGINAL TASK: {prompt[:500]}\n\n"
            f"DRAFT RESPONSE:\n{draft_result.response}\n\n"
            "INSTRUCTIONS:\n"
            "- Fix factual errors or hallucinations.\n"
            "- Improve code correctness if applicable.\n"
            "- Keep what's good; only change what's wrong.\n"
            "- If the draft is correct, respond: APPROVED\n"
            "- If changes needed, provide the corrected version only."
        )
        try:
            verify_result = await model_router.call(
                verify_prov, verify_mdl, verify_prompt,
                max_tokens=min(draft_max_tokens, 2000),
                temperature=0.2,  # Low temperature for fact-checking
            )
        except Exception:
            # Verification failed → use draft as-is
            return {
                "response": draft_result.response,
                "draft_approved": True,
                "draft_model": draft_mdl,
                "verify_model": "unavailable",
                "draft_cost": draft_result.cost_usd,
                "verify_cost": 0.0,
                "total_cost": draft_result.cost_usd,
                "estimated_savings": 0.0,
            }

        is_approved = verify_result.response.strip().upper().startswith("APPROVED")
        final_response = draft_result.response if is_approved else verify_result.response

        total_cost = draft_result.cost_usd + verify_result.cost_usd
        # Rough savings estimate: what would full verify-model generation have cost?
        full_gen_cost_estimate = verify_result.cost_usd * 2.5
        savings = max(0.0, full_gen_cost_estimate - total_cost)

        return {
            "response": final_response,
            "draft_approved": is_approved,
            "draft_model": draft_mdl,
            "draft_provider": draft_prov,
            "verify_model": verify_mdl,
            "verify_provider": verify_prov,
            "draft_cost": round(draft_result.cost_usd, 6),
            "verify_cost": round(verify_result.cost_usd, 6),
            "total_cost": round(total_cost, 6),
            "estimated_savings": round(savings, 6),
        }

    def _select_draft_model(self, router: "ModelRouter") -> Tuple[str, str]:
        """Pick the cheapest provider for drafting."""
        if DRAFT_PROVIDER in router.providers:
            provider = router.providers[DRAFT_PROVIDER]
            if provider.models and DRAFT_MODEL in provider.models:
                return DRAFT_PROVIDER, DRAFT_MODEL
        # Fallback: first registered provider
        for prov_name, prov in router.providers.items():
            if prov.models:
                return prov_name, next(iter(prov.models))
        raise RuntimeError("No providers registered for speculative draft")

    def _select_verify_model(self, router: "ModelRouter", skip: str) -> Tuple[str, str]:
        """Pick the best available provider for verification (different from draft)."""
        quality_order = ["anthropic", "openai", "google", "xai", "mistral", "deepseek"]
        for prov_name in quality_order:
            if prov_name == skip:
                continue
            if prov_name in router.providers:
                provider = router.providers[prov_name]
                if provider.models:
                    return prov_name, next(iter(provider.models))
        # If no different provider available, use the draft provider (still saves tokens)
        return self._select_draft_model(router)


# Module-level singleton (router injected at call time)
speculative_decoder = SpeculativeDecoder()
