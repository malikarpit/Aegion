"""
FrugalGPT-style LLM Cascade — Phase 10 (Enhanced): Multi-Tier Cost Optimization.

Strategy: Start with the cheapest available provider, evaluate response quality
via multi-signal confidence scoring, only escalate to more expensive tiers
when confidence is below threshold.

Enhancement over basic cascade:
  - Confidence scoring uses 5 signals (not just uncertainty phrases)
  - Multi-provider tier system (8 tiers across all providers)
  - Budget-aware mode: can hard-cap maximum spend per query
  - Tracks cumulative cost across cascade attempts
  - Smart tier skipping: if a tier provider isn't registered, skip to next

Tiers (cheapest → most expensive per request):
  0. Ollama              — $0.00          — threshold 0.90 (local, free)
  1. Gemini 2.0 Flash    — ~$0.05/1M avg  — threshold 0.85
  2. DeepSeek V3         — ~$0.69/1M avg  — threshold 0.82
  3. Mistral Small       — ~$0.20/1M avg  — threshold 0.80
  4. GPT-4.1 Mini        — ~$1.00/1M avg  — threshold 0.78
  5. Grok 3 Mini         — ~$0.40/1M avg  — threshold 0.75
  6. Claude Haiku 3.5    — ~$2.40/1M avg  — threshold 0.72
  7. GPT-4.1             — ~$5.00/1M avg  — final fallback (no threshold)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from .model_router import ModelRouter, MODEL_CATALOG
from .types import ModelResponse


@dataclass(frozen=True)
class CascadeTier:
    provider: str
    model: str
    avg_cost_per_1m: float       # Approximate average (input+output) per 1M tokens
    confidence_threshold: float  # Escalate if response confidence < this
    level: int                   # 0 = cheapest


class LLMCascade:
    """
    FrugalGPT cascade: start cheap → escalate on low confidence.

    The cascade evaluates response confidence using 5 signals:
      1. Uncertainty language detection
      2. Response length adequacy
      3. Structural quality (code blocks, lists, formatting)
      4. Specificity analysis (concrete details vs vague generalities)
      5. Self-referential uncertainty (model admitting it doesn't know)

    Falls back gracefully if a tier's provider is not registered.
    """

    DEFAULT_TIERS: List[CascadeTier] = [
        CascadeTier("ollama",   "llama3.1:8b",                       0.00,   0.90, 0),
        CascadeTier("google",   "gemini-2.0-flash",                  0.25,   0.85, 1),
        CascadeTier("deepseek", "deepseek-chat",                     0.69,   0.82, 2),
        CascadeTier("mistral",  "mistral-small-latest",              0.20,   0.80, 3),
        CascadeTier("openai",   "gpt-4.1-mini",                     1.00,   0.78, 4),
        CascadeTier("xai",      "grok-3-mini",                      0.40,   0.75, 5),
        CascadeTier("anthropic","claude-haiku-3-5-20241022",         2.40,   0.72, 6),
        CascadeTier("openai",   "gpt-4.1",                          5.00,   0.00, 7),  # Final fallback
    ]

    def __init__(self, model_router: ModelRouter) -> None:
        self.router = model_router
        self.tiers = self.DEFAULT_TIERS

    async def query(
        self,
        prompt: str,
        context: Optional[Dict] = None,
        max_budget_usd: Optional[float] = None,
        system_prompt: Optional[str] = None,
    ) -> ModelResponse:
        """
        Run the cascade: try tiers in order, escalate if confidence is too low.

        Args:
            prompt:          The user query.
            context:         Optional context dict.
            max_budget_usd:  If set, hard-stops when cumulative cost exceeds this.
            system_prompt:   Optional system prompt injected into each tier call.

        Returns the first response whose confidence meets or exceeds its tier threshold.
        Falls back to the last available tier's response regardless of confidence.
        """
        available = set(self.router.providers.keys())
        last_response: Optional[ModelResponse] = None
        cumulative_cost = 0.0

        for tier in self.tiers:
            if tier.provider not in available:
                continue

            # Budget guard
            if max_budget_usd is not None and cumulative_cost >= max_budget_usd:
                break

            try:
                response = await self.router.call(
                    tier.provider, tier.model, prompt,
                    system_prompt=system_prompt,
                )
            except Exception:
                # Provider errored — skip to next tier
                continue

            confidence = self._score_confidence(response.response, response)
            response = response.model_copy(update={"confidence": confidence})
            last_response = response
            cumulative_cost += response.cost_usd

            if confidence >= tier.confidence_threshold:
                return response  # Good enough — stop here

        if last_response is not None:
            return last_response

        raise RuntimeError("LLM cascade exhausted — no providers available or all failed.")

    # ──────────────────────────────────────────────────────────────
    # Multi-Signal Confidence Scoring
    # ──────────────────────────────────────────────────────────────

    # Phrases that indicate the model is uncertain or hedging
    _UNCERTAINTY_PHRASES = [
        "i'm not sure", "i think", "it might", "possibly", "perhaps",
        "i don't know", "unclear", "it depends", "hard to say",
        "i cannot", "i am unable", "not certain", "may or may not",
        "i'm not confident", "it's difficult to determine",
        "this is speculative", "take this with a grain of salt",
        "i could be wrong", "i'm guessing",
    ]

    # Phrases that indicate the model is refusing to answer
    _REFUSAL_PHRASES = [
        "i can't help with", "i cannot provide", "as an ai",
        "i'm sorry, but", "i apologize, but", "i don't have access",
        "outside my capabilities", "i cannot assist",
    ]

    # Phrases that indicate high-quality reasoning
    _QUALITY_MARKERS = [
        "because", "therefore", "evidence suggests", "according to",
        "step 1", "first,", "specifically", "for example",
        "in conclusion", "the key insight",
    ]

    def _score_confidence(self, text: str, response: ModelResponse) -> float:
        """
        Multi-signal confidence scoring.

        Five signals weighted and combined:
          1. Uncertainty language   (weight: 0.25) — penalty for hedging phrases
          2. Response adequacy      (weight: 0.20) — length and substance check
          3. Structural quality     (weight: 0.20) — formatting, code blocks, lists
          4. Specificity            (weight: 0.20) — concrete details vs vagueness
          5. Refusal detection      (weight: 0.15) — model refusing to answer

        Returns a score in [0.0, 1.0].
        """
        lower = text.lower()

        # Signal 1: Uncertainty (1.0 = confident, 0.0 = very uncertain)
        uncertainty_count = sum(1 for p in self._UNCERTAINTY_PHRASES if p in lower)
        uncertainty_score = max(0.0, 1.0 - (uncertainty_count * 0.15))

        # Signal 2: Response adequacy (short = low confidence)
        word_count = len(text.split())
        if word_count < 20:
            adequacy_score = 0.30
        elif word_count < 50:
            adequacy_score = 0.60
        elif word_count < 200:
            adequacy_score = 0.80
        else:
            adequacy_score = 0.95

        # Signal 3: Structural quality (code blocks, lists, headers = higher quality)
        structural_score = 0.60
        if len(re.findall(r"```", text)) >= 2:
            structural_score += 0.15  # Has complete code blocks
        if re.search(r"^[\-\*\d]+\.", text, re.MULTILINE):
            structural_score += 0.10  # Has lists
        if re.search(r"^#+\s", text, re.MULTILINE):
            structural_score += 0.05  # Has headers
        if "|" in text and "-|-" in text.replace(" ", ""):
            structural_score += 0.10  # Has tables
        structural_score = min(1.0, structural_score)

        # Signal 4: Specificity (concrete details, reasoning markers)
        quality_count = sum(1 for m in self._QUALITY_MARKERS if m in lower)
        specificity_score = min(1.0, 0.50 + quality_count * 0.10)

        # Signal 5: Refusal detection (model refusing to answer = very low confidence)
        refusal_count = sum(1 for r in self._REFUSAL_PHRASES if r in lower)
        refusal_score = max(0.0, 1.0 - (refusal_count * 0.40))

        # Weighted combination
        final = (
            uncertainty_score * 0.25
            + adequacy_score * 0.20
            + structural_score * 0.20
            + specificity_score * 0.20
            + refusal_score * 0.15
        )

        return round(max(0.0, min(1.0, final)), 3)
