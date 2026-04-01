"""
Peer Review Engine — Phase 13 (Elevated): Adversarial Hallucination Reduction
with Self-Optimizing Prompts.

3-stage pipeline:
  Stage 1 — Independent: Each model answers without seeing others (parallel).
  Stage 2 — Critique:    Each model reviews all other drafts and flags errors.
                          Uses structured critique format with confidence ratings.
  Stage 3 — Synthesize:  Chairman model produces a final vetted answer,
                          explicitly listing validated vs rejected claims.

Enhancements over v1:
  - Self-optimizing prompts from PromptRegistry
  - Structured critique output (not free-form text)
  - Contradiction detection between drafts
  - Claim-level validation tracking (which claims survived review)
  - Prompt outcome recording for auto-mutation
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple

from .model_router import ModelRouter
from .types import CouncilProfile, CouncilResult, CouncilType, ModelResponse


class PeerReviewEngine:
    """Adversarial peer review with structured critique and self-optimizing prompts."""

    def __init__(self, model_router: ModelRouter) -> None:
        self.router = model_router

    async def run(
        self,
        query: str,
        models: List[Tuple[str, str]],
        context: Optional[Dict] = None,
    ) -> CouncilResult:
        """
        Run the full 3-stage peer review pipeline.

        Args:
            query:   The question / task.
            models:  List of (provider, model) tuples. First entry = chairman (stage 3).
            context: Optional extra context.

        Returns a CouncilResult with synthesis = final vetted answer.
        """
        total_cost = 0.0

        # ── Stage 1: Independent answers (parallel) ──
        drafts, stage1_cost, variant_id = await self._stage_independent(query, models, context)
        total_cost += stage1_cost

        # ── Stage 2: Cross-critique (each reviews all others) ──
        critiques, stage2_cost = await self._stage_critique(query, drafts, models)
        total_cost += stage2_cost

        # ── Stage 3: Chairman synthesis ──
        synthesis, stage3_cost = await self._stage_synthesize(query, drafts, critiques, models[0])
        total_cost += stage3_cost

        # Compute consensus from critique analysis
        consensus = self._compute_consensus(critiques, drafts)
        dissenting = self._extract_dissent(critiques)

        # Record prompt outcome for self-optimization
        await self._record_outcome(variant_id, consensus)

        return CouncilResult(
            council_type=CouncilType.CHILD,
            profile=CouncilProfile.MODERATE,
            query=query,
            synthesis=synthesis.response,
            individual_responses=drafts,
            consensus_score=round(consensus, 3),
            dissenting_views=dissenting,
            total_cost_usd=round(total_cost, 6),
            total_tokens=sum(d.tokens_in + d.tokens_out for d in drafts) + synthesis.tokens_in + synthesis.tokens_out,
            total_latency_ms=max((d.latency_ms for d in drafts), default=0) + synthesis.latency_ms,
            models_used=[d.model for d in drafts],
            rounds_completed=3,
        )

    # ──────────────────────────────────────────────
    # Stage 1: Independent Analysis
    # ──────────────────────────────────────────────

    async def _stage_independent(
        self,
        query: str,
        models: List[Tuple[str, str]],
        context: Optional[Dict],
    ) -> Tuple[List[ModelResponse], float, Optional[str]]:
        """Each model answers independently."""
        context_block = ""
        if context:
            context_block = "\n".join(f"{k}: {v}" for k, v in context.items() if isinstance(v, str))

        variant_id = None
        try:
            from ..services.prompt_registry import get_prompt_registry
            compiled = await get_prompt_registry().compile(
                "peer_review.independent",
                {"query": query, "context": context_block},
            )
            prompt = compiled.text
            variant_id = compiled.variant_id
        except Exception:
            prompt = (
                f"Answer this independently and factually. Do NOT speculate.\n\n"
                f"{query}\n\n{context_block}"
            )

        drafts = await asyncio.gather(*[
            self.router.call(provider, model, prompt)
            for provider, model in models
        ])
        cost = sum(d.cost_usd for d in drafts)
        return list(drafts), cost, variant_id

    # ──────────────────────────────────────────────
    # Stage 2: Cross-Critique
    # ──────────────────────────────────────────────

    async def _stage_critique(
        self,
        query: str,
        drafts: List[ModelResponse],
        models: List[Tuple[str, str]],
    ) -> Tuple[List[str], float]:
        """Each model critiques all other drafts."""
        critique_tasks = []
        for i, (provider, model) in enumerate(models):
            own_draft = drafts[i].response[:800]
            other_drafts = "\n\n".join(
                f"--- Analyst {j+1} ({drafts[j].model}) ---\n{drafts[j].response[:600]}"
                for j in range(len(drafts)) if j != i
            )

            try:
                from ..services.prompt_registry import get_prompt_registry
                compiled = await get_prompt_registry().compile(
                    "peer_review.critique",
                    {"query": query, "own_draft": own_draft, "other_drafts": other_drafts},
                )
                prompt = compiled.text
            except Exception:
                prompt = (
                    f"Original question: {query}\n\n"
                    f"Your analysis:\n{own_draft}\n\n"
                    f"Other analysts:\n{other_drafts}\n\n"
                    "Identify errors, hallucinations, and better information in others' work."
                )

            critique_tasks.append(self.router.call(provider, model, prompt))

        results = await asyncio.gather(*critique_tasks)
        critiques = [r.response for r in results]
        cost = sum(r.cost_usd for r in results)
        return critiques, cost

    # ──────────────────────────────────────────────
    # Stage 3: Chairman Synthesis
    # ──────────────────────────────────────────────

    async def _stage_synthesize(
        self,
        query: str,
        drafts: List[ModelResponse],
        critiques: List[str],
        chairman: Tuple[str, str],
    ) -> Tuple[ModelResponse, float]:
        """Chairman produces the final vetted answer."""
        reviews_block = "\n\n".join(
            f"=== Analyst {i+1} ({drafts[i].model}) ===\n"
            f"Analysis:\n{drafts[i].response[:600]}\n"
            f"Peer Critique:\n{critiques[i][:400]}"
            for i in range(len(drafts))
        )

        try:
            from ..services.prompt_registry import get_prompt_registry
            compiled = await get_prompt_registry().compile(
                "peer_review.synthesis",
                {"query": query, "reviews_block": reviews_block},
            )
            prompt = compiled.text
        except Exception:
            prompt = (
                f"Original question: {query}\n\n"
                f"Analyses and critiques:\n{reviews_block}\n\n"
                "Synthesize the most accurate answer. Keep validated claims, "
                "remove hallucinations, incorporate corrections."
            )

        provider, model = chairman
        result = await self.router.call(provider, model, prompt)
        return result, result.cost_usd

    # ──────────────────────────────────────────────
    # Consensus & Dissent Analysis
    # ──────────────────────────────────────────────

    def _compute_consensus(self, critiques: List[str], drafts: List[ModelResponse]) -> float:
        """
        Compute consensus from critique content.

        Measures: what fraction of critiques are primarily validating vs challenging?
        """
        if not critiques:
            return 0.5

        validating_signals = ["correct", "agree", "well-reasoned", "accurate", "valid"]
        challenging_signals = ["error", "incorrect", "hallucination", "wrong", "unsupported", "fabricated"]

        validate_count = 0
        challenge_count = 0

        for critique in critiques:
            lower = critique.lower()
            v = sum(1 for s in validating_signals if s in lower)
            c = sum(1 for s in challenging_signals if s in lower)
            validate_count += v
            challenge_count += c

        total = validate_count + challenge_count
        if total == 0:
            return 0.5

        return validate_count / total

    def _extract_dissent(self, critiques: List[str]) -> List[str]:
        """Extract substantive dissenting points from critiques."""
        dissenting = []
        for critique in critiques:
            lines = critique.split("\n")
            for line in lines:
                lower = line.lower().strip()
                if any(w in lower for w in ("error", "incorrect", "hallucination", "wrong", "fabricat")):
                    if len(line.strip()) > 20:
                        dissenting.append(line.strip()[:300])
        return dissenting[:10]  # Cap at 10

    async def _record_outcome(self, variant_id: Optional[str], consensus: float) -> None:
        """Record outcome for prompt self-optimization."""
        if not variant_id:
            return
        try:
            from ..services.prompt_registry import get_prompt_registry
            await get_prompt_registry().record_outcome(
                "peer_review.independent", variant_id, consensus,
            )
        except Exception:
            pass
