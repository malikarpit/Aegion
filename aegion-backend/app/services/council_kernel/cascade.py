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

            # ── Reflexion Self-Reflection ──────────────────────────────
            # If confidence is below threshold, attempt ONE self-critique
            # using the same tier (cost-controlled) before escalating.
            #
            # Based on: Shinn et al. "Reflexion: Language Agents with
            # Verbal Reinforcement Learning" (NeurIPS 2023).
            #
            # The model critiques its own response, identifies weaknesses,
            # and re-generates with the critique as additional context.
            # This often recovers quality without escalating to a more
            # expensive tier.
            # ──────────────────────────────────────────────────────────

            if max_budget_usd is not None and cumulative_cost >= max_budget_usd:
                break  # No budget for reflection

            reflection = await self._self_reflect(
                tier, prompt, response.response, system_prompt,
            )
            if reflection is not None:
                reflection_conf = self._score_confidence(
                    reflection.response, reflection,
                )
                reflection = reflection.model_copy(
                    update={"confidence": reflection_conf},
                )
                cumulative_cost += reflection.cost_usd

                if reflection_conf >= tier.confidence_threshold:
                    return reflection  # Reflection recovered quality

                # Reflection was better but still below threshold —
                # keep the better response as fallback
                if reflection_conf > confidence:
                    last_response = reflection

        if last_response is not None:
            return last_response

        raise RuntimeError("LLM cascade exhausted — no providers available or all failed.")

    # ──────────────────────────────────────────────────────────────
    # Reflexion: Self-Reflection Loop
    # ──────────────────────────────────────────────────────────────

    _CRITIQUE_PROMPT = (
        "You are a code review expert. Critically analyze this response to the "
        "user's question. Identify:\n"
        "1. Factual errors or unsupported claims\n"
        "2. Missing important details\n"
        "3. Logical inconsistencies\n"
        "4. Code quality issues (if applicable)\n"
        "5. Clarity and organization problems\n\n"
        "Then provide a SCORE from 1-10 on the line 'SCORE: N' where N is "
        "how much the response could be improved (10 = needs major rewrite, "
        "1 = nearly perfect).\n\n"
        "User question: {query}\n\n"
        "Response to critique:\n{response}"
    )

    _RETRY_PROMPT = (
        "You previously answered this question, but your response had issues. "
        "Here is the critique of your previous response:\n\n"
        "--- CRITIQUE ---\n{critique}\n--- END CRITIQUE ---\n\n"
        "Now provide an IMPROVED response to the original question. "
        "Address all the issues identified in the critique.\n\n"
        "Original question: {query}"
    )

    async def _self_reflect(
        self,
        tier: CascadeTier,
        original_query: str,
        original_response: str,
        system_prompt: Optional[str],
    ) -> Optional[ModelResponse]:
        """
        Reflexion self-reflection: critique the response and retry if needed.

        Steps:
            1. Ask the SAME tier's model to critique the response
            2. Parse the critique score (1-10)
            3. If score >= 5 (significant room for improvement), retry with
               the critique as additional context
            4. Return the improved response, or None if reflection not worthwhile

        Cost control: Uses the same tier (no escalation), max 2 extra calls.

        Returns:
            Improved ModelResponse if reflection helped, None otherwise.
        """
        try:
            # Step 1: Generate critique
            critique_prompt = self._CRITIQUE_PROMPT.format(
                query=original_query[:500],
                response=original_response[:2000],
            )
            critique_response = await self.router.call(
                tier.provider, tier.model, critique_prompt,
                system_prompt="You are a strict, objective code reviewer.",
            )

            # Step 2: Parse score
            score = self._parse_critique_score(critique_response.response)
            if score < 5:
                # Response is good enough — reflection wouldn't help much
                return None

            # Step 3: Retry with critique context
            retry_prompt = self._RETRY_PROMPT.format(
                critique=critique_response.response[:1500],
                query=original_query,
            )
            improved = await self.router.call(
                tier.provider, tier.model, retry_prompt,
                system_prompt=system_prompt,
            )
            return improved

        except Exception:
            # Reflection is best-effort — don't let it crash the cascade
            return None

    @staticmethod
    def _parse_critique_score(critique_text: str) -> int:
        """
        Extract the numeric SCORE from a critique response.

        Looks for patterns like "SCORE: 7" or "Score: 8/10".
        Returns 0 if no score found (conservative — don't retry).
        """
        import re
        # Primary pattern: SCORE: N
        match = re.search(r"SCORE:\s*(\d+)", critique_text, re.IGNORECASE)
        if match:
            return min(10, max(1, int(match.group(1))))

        # Fallback: N/10 pattern
        match = re.search(r"(\d+)\s*/\s*10", critique_text)
        if match:
            return min(10, max(1, int(match.group(1))))

        return 0

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
        Phase 93: Code-aware multi-signal confidence scoring.

        Seven signals weighted and combined (replaces Phase 10 phrase-only scorer):
          1. Uncertainty language   (weight: 0.15) — penalty for hedging phrases
          2. Response adequacy      (weight: 0.10) — length and substance check
          3. Structural quality     (weight: 0.15) — formatting, code blocks, lists
          4. Specificity            (weight: 0.15) — concrete details vs vagueness
          5. Refusal detection      (weight: 0.10) — model refusing to answer
          6. Code correctness       (weight: 0.20) — parseable code, valid diffs
          7. Explanation coherence  (weight: 0.15) — code refs match explanation

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
        code_blocks = re.findall(r"```(\w*)\n(.*?)```", text, re.DOTALL)
        if len(code_blocks) >= 1:
            structural_score += 0.15
        if re.search(r"^[\-\*\d]+\.", text, re.MULTILINE):
            structural_score += 0.10
        if re.search(r"^#+\s", text, re.MULTILINE):
            structural_score += 0.05
        if "|" in text and "-|-" in text.replace(" ", ""):
            structural_score += 0.10
        structural_score = min(1.0, structural_score)

        # Signal 4: Specificity (concrete details, reasoning markers)
        quality_count = sum(1 for m in self._QUALITY_MARKERS if m in lower)
        specificity_score = min(1.0, 0.50 + quality_count * 0.10)

        # Signal 5: Refusal detection
        refusal_count = sum(1 for r in self._REFUSAL_PHRASES if r in lower)
        refusal_score = max(0.0, 1.0 - (refusal_count * 0.40))

        # Signal 6: Code correctness (Phase 93 — code-aware)
        code_score = self._score_code_quality(text, code_blocks)

        # Signal 7: Explanation coherence
        coherence_score = self._score_explanation_coherence(text, code_blocks)

        # Weighted combination
        final = (
            uncertainty_score * 0.15
            + adequacy_score * 0.10
            + structural_score * 0.15
            + specificity_score * 0.15
            + refusal_score * 0.10
            + code_score * 0.20
            + coherence_score * 0.15
        )

        return round(max(0.0, min(1.0, final)), 3)

    def _score_code_quality(self, text: str, code_blocks: list) -> float:
        """
        Score code quality signals:
        - Parseable code blocks (balanced braces/parens)
        - Valid unified diffs
        - Named language tags on code fences
        """
        if not code_blocks:
            # No code at all — neutral score (response might be prose-only)
            return 0.65

        score = 0.50
        valid_blocks = 0

        for lang, content in code_blocks:
            # Language tag present = more intentional
            if lang.strip():
                score += 0.05

            # Check brace/paren balance (heuristic for parsability)
            opens = content.count("{") + content.count("(") + content.count("[")
            closes = content.count("}") + content.count(")") + content.count("]")
            if opens > 0 and abs(opens - closes) <= 1:
                valid_blocks += 1

            # Valid diff detection
            if lang.strip() == "diff" or (
                content.count("\n+") >= 1 and content.count("\n-") >= 1
            ):
                valid_blocks += 1
                score += 0.05

        # Ratio of valid blocks
        if code_blocks:
            score += 0.30 * (valid_blocks / len(code_blocks))

        return min(1.0, score)

    def _score_explanation_coherence(self, text: str, code_blocks: list) -> float:
        """
        Check if prose explanations reference the code being shown.
        A high-quality response explains its code rather than just dumping it.
        """
        if not code_blocks:
            return 0.70  # No code — coherence is about text quality only

        # Extract identifiers from code blocks
        all_code = " ".join(content for _, content in code_blocks)
        # Look for function/class/variable names in code
        identifiers = set(re.findall(r"\b([a-zA-Z_]\w{2,})\b", all_code))

        if not identifiers:
            return 0.60

        # Check how many code identifiers are mentioned in non-code prose
        prose_parts = re.split(r"```.*?```", text, flags=re.DOTALL)
        prose_text = " ".join(prose_parts).lower()

        mentioned = sum(1 for ident in identifiers if ident.lower() in prose_text)
        mention_ratio = mentioned / max(len(identifiers), 1)

        # Score: 0.5 base + up to 0.5 based on mention ratio
        return min(1.0, 0.50 + mention_ratio * 0.50)

    # ── Platt Scaling — Confidence Calibration ──────────────────────────

    @staticmethod
    def _calibrate_confidence(raw_confidence: float, A: float = -1.5, B: float = 0.5) -> float:
        """
        Platt scaling: sigmoid calibration of raw confidence scores.

        Reference: Platt, 1999 — "Probabilistic Outputs for Support Vector
                   Machines and Comparisons to Regularized Likelihood Methods"

        Maps model-reported confidence (often poorly calibrated) to a
        calibrated probability using:

            P(correct) = 1 / (1 + exp(A × raw + B))

        Default parameters A=-1.5, B=0.5 are tuned empirically for
        LLM self-reported confidence scores, which tend to be over-confident.

        Properties:
            - Monotonically increasing with raw_confidence
            - Compresses over-confident scores (>0.9) downward
            - Expands under-confident scores (<0.3) upward
            - Returns value in (0, 1)

        Args:
            raw_confidence: The raw confidence score from the model (0-1).
            A: Sigmoid slope parameter (default -1.5).
            B: Sigmoid bias parameter (default 0.5).

        Returns:
            Calibrated confidence in (0.0, 1.0).
        """
        import math
        return 1.0 / (1.0 + math.exp(A * raw_confidence + B))
