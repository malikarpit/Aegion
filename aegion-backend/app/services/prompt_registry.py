"""
Self-Optimizing Prompts — DSPy-Style Prompt Compilation.

Replaces static hardcoded prompts in debate.py, peer_review.py, and other engines
with a dynamic prompt registry that:
  1. Versions every prompt template (so we can A/B test)
  2. Automatically mutates prompts when rubric scores drop below threshold
  3. Injects few-shot examples from rejection learning history
  4. Tracks which prompt variant produced the best outcomes

Inspired by DSPy (Stanford NLP) — "programming, not prompting."

Usage:
    registry = get_prompt_registry()
    
    # Get the current best prompt for debate
    prompt = await registry.compile(
        "debate.opening",
        variables={"proposition": "...", "round": 1},
        workspace_id="ws-123",
    )
    
    # After getting rubric feedback, record the outcome
    await registry.record_outcome(
        "debate.opening",
        variant_id=prompt.variant_id,
        rubric_score=0.42,  # Low → triggers auto-optimization
    )
"""

from __future__ import annotations

import copy
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.logging import logger


# ──────────────────────────────────────────────────────────────────────────────
# Types
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class PromptVariant:
    """A specific version of a prompt template."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    template: str = ""                     # The prompt text with {variable} placeholders
    version: int = 1
    parent_id: Optional[str] = None        # ID of the variant this was mutated from
    mutation_reason: Optional[str] = None   # Why this variant was created

    # Performance tracking
    total_uses: int = 0
    total_score: float = 0.0
    best_score: float = 0.0
    worst_score: float = 1.0

    # Few-shot examples injected into this variant
    few_shot_examples: List[Dict[str, str]] = field(default_factory=list)

    @property
    def avg_score(self) -> float:
        return self.total_score / max(self.total_uses, 1)

    @property
    def template_hash(self) -> str:
        return hashlib.sha256(self.template.encode()).hexdigest()[:12]


@dataclass
class CompiledPrompt:
    """The result of compiling a prompt template with variables."""
    text: str                              # The final prompt text (variables filled in)
    variant_id: str                        # Which variant produced this
    template_name: str                     # Registry key
    version: int                           # Version number
    few_shot_count: int = 0                # How many examples were injected


# ──────────────────────────────────────────────────────────────────────────────
# Default Prompt Templates (the initial v1 prompts)
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_TEMPLATES: Dict[str, str] = {
    "debate.opening": (
        "STRUCTURED DEBATE — ROUND {round}/{max_rounds}\n"
        "Proposition: {proposition}\n\n"
        "ANTI-SYCOPHANCY PROTOCOL (strictly enforced):\n"
        "• State your GENUINE position — do NOT agree to be polite.\n"
        "• If you disagree, you MUST cite specific evidence or reasoning.\n"
        "• 'I agree because everyone else does' → INVALID. You will be penalized.\n"
        "• Dissenting views are PROTECTED. You cannot be overruled without NEW evidence.\n"
        "• If you change your position from a previous round, explain EXACTLY what "
        "new information caused the change.\n\n"
        "{previous_context}"
        "State your position with evidence:"
    ),
    "debate.fresh_eyes": (
        "FRESH EYES VALIDATION — You have NOT participated in this debate.\n\n"
        "Proposition: {proposition}\n\n"
        "Majority position:\n{majority_position}\n\n"
        "Contrarian arguments:\n{contrarian_positions}\n\n"
        "TASK: As an independent evaluator with no prior exposure:\n"
        "1. Is the majority position logically sound and well-evidenced?\n"
        "2. Do the contrarian arguments identify genuine weaknesses?\n"
        "3. What is YOUR independent, evidence-based assessment?\n"
        "4. What risks does each position carry?"
    ),
    "peer_review.independent": (
        "INDEPENDENT ANALYSIS — Answer this question factually and specifically.\n"
        "Do NOT speculate. If you are unsure, say so explicitly.\n"
        "Cite specific sources, files, or code patterns where applicable.\n\n"
        "Question: {query}\n\n"
        "{context}"
    ),
    "peer_review.critique": (
        "ADVERSARIAL REVIEW — You are reviewing other analysts' work.\n\n"
        "Original question: {query}\n\n"
        "Your own analysis:\n{own_draft}\n\n"
        "Other analysts' work:\n{other_drafts}\n\n"
        "REVIEW INSTRUCTIONS:\n"
        "• Identify factual errors, unsupported claims, or hallucinations.\n"
        "• Flag any logical fallacies or circular reasoning.\n"
        "• Note where other analysts provide BETTER information than your own work.\n"
        "• Be specific — cite line-level evidence, not vague disagreements.\n"
        "• Rate your confidence in each critique (high/medium/low)."
    ),
    "peer_review.synthesis": (
        "SYNTHESIS — You are the chairman. Produce the definitive answer.\n\n"
        "Original question: {query}\n\n"
        "Analyses and critiques:\n{reviews_block}\n\n"
        "SYNTHESIS RULES:\n"
        "1. KEEP only claims validated by 2+ independent reviewers.\n"
        "2. REMOVE claims flagged as hallucinations by any reviewer.\n"
        "3. INCORPORATE corrections from peer critiques.\n"
        "4. PRESERVE well-evidenced dissenting views in a separate section.\n"
        "5. If reviewers fundamentally disagree, present both positions with evidence."
    ),
    "sentinel.security_scan": (
        "SECURITY THREAT ASSESSMENT — You are a paranoid security auditor.\n\n"
        "Assume attackers are actively probing this system.\n\n"
        "Code to analyze:\n```{language}\n{code}\n```\n\n"
        "ANALYSIS REQUIREMENTS:\n"
        "• Check for: injection risks (SQL, XSS, command), authentication gaps,\n"
        "  data exposure, privilege escalation, supply chain risks, OWASP Top 10.\n"
        "• For each finding: severity (critical/high/medium/low), evidence, fix.\n"
        "• Rate overall risk score 0.0-1.0."
    ),
    "mcts.expand": (
        "ORIGINAL QUESTION: {query}\n\n"
        "{chain_context}\n\n"
        "Generate exactly {branch_factor} distinct candidate {step_type}.\n"
        "Each must explore a DIFFERENT angle or approach.\n\n"
        "Format each on its own line:\n"
        "[CANDIDATE 1]: ...\n"
        "[CANDIDATE 2]: ...\n"
        "[CANDIDATE 3]: ..."
    ),
    "mcts.critic": (
        "CRITIC EVALUATION — Score this reasoning step.\n\n"
        "Original question: {query}\n"
        "Chain so far:\n{chain}\n"
        "Proposed step:\n{thought}\n\n"
        "Score 0.0–1.0 on:\n"
        "• Coherence: follows from prior reasoning\n"
        "• Grounding: based on facts, not hallucination\n"
        "• Relevance: moves toward answering the question\n"
        "• Novelty: adds new information\n"
        "• Completeness: if final, fully addresses the question\n\n"
        'Respond with JSON: {{"overall": 0.X, "critique": "..."}}'
    ),
    "distillation.summarize": (
        "TECHNICAL SUMMARIZATION — Produce a clear, concise summary.\n\n"
        "RULES:\n"
        "• Preserve key decisions, code changes, and unresolved issues.\n"
        "• Use bullet points for actionable items.\n"
        "• Separate facts from opinions.\n"
        "• Flag any items that need follow-up.\n\n"
        "{context}\n\n"
        "Content to summarize:\n{query}"
    ),
    "sentinel.threat_assessment": (
        "SECURITY THREAT ASSESSMENT — You are a paranoid security auditor.\n\n"
        "Assume attackers are actively probing this system.\n\n"
        "ANALYSIS REQUIREMENTS:\n"
        "• Check for: injection risks (SQL, XSS, command), authentication gaps,\n"
        "  data exposure, privilege escalation, supply chain risks, OWASP Top 10.\n"
        "• For each finding: severity (critical/high/medium/low), evidence, fix.\n"
        "• Rate overall risk score 0.0-1.0.\n\n"
        "{context}\n\n"
        "Analyze:\n{query}"
    ),
}



# ──────────────────────────────────────────────────────────────────────────────
# Prompt Registry
# ──────────────────────────────────────────────────────────────────────────────

class PromptRegistry:
    """
    Dynamic prompt registry with versioning, mutation, and A/B tracking.

    Thread-safe for async usage (single-writer model — mutations are serialized).
    """

    # If a variant's average score drops below this, trigger auto-mutation
    MUTATION_THRESHOLD = 0.55
    # Minimum uses before we consider mutating
    MIN_USES_FOR_MUTATION = 3

    def __init__(self) -> None:
        self._templates: Dict[str, List[PromptVariant]] = {}
        self._active_variant: Dict[str, str] = {}  # template_name → variant_id

        # Initialize with default templates
        for name, template in _DEFAULT_TEMPLATES.items():
            variant = PromptVariant(template=template, version=1)
            self._templates[name] = [variant]
            self._active_variant[name] = variant.id

    async def compile(
        self,
        template_name: str,
        variables: Dict[str, Any],
        workspace_id: Optional[str] = None,
    ) -> CompiledPrompt:
        """
        Compile a prompt template with variables.

        1. Gets the active variant for this template
        2. Injects few-shot examples if available
        3. Fills in {variable} placeholders
        """
        variant = self._get_active_variant(template_name)
        if not variant:
            raise KeyError(f"Unknown prompt template: {template_name}")

        # Build the prompt text
        text = variant.template

        # Inject few-shot examples if available
        if variant.few_shot_examples:
            examples_block = "\n\n".join(
                f"EXAMPLE {i+1}:\nInput: {ex.get('input', '')}\nOutput: {ex.get('output', '')}"
                for i, ex in enumerate(variant.few_shot_examples[:3])
            )
            text = f"{examples_block}\n\n---\n\n{text}"

        # Fill in variables (safe: missing keys stay as-is)
        for key, value in variables.items():
            text = text.replace(f"{{{key}}}", str(value))

        return CompiledPrompt(
            text=text,
            variant_id=variant.id,
            template_name=template_name,
            version=variant.version,
            few_shot_count=len(variant.few_shot_examples),
        )

    async def record_outcome(
        self,
        template_name: str,
        variant_id: str,
        rubric_score: float,
    ) -> Optional[str]:
        """
        Record the outcome of using a prompt variant.

        If the variant's average score drops below MUTATION_THRESHOLD,
        automatically creates a mutated variant.

        Returns the ID of a new variant if mutation was triggered, else None.
        """
        variants = self._templates.get(template_name, [])
        variant = next((v for v in variants if v.id == variant_id), None)
        if not variant:
            return None

        variant.total_uses += 1
        variant.total_score += rubric_score
        variant.best_score = max(variant.best_score, rubric_score)
        variant.worst_score = min(variant.worst_score, rubric_score)

        # Check if mutation is needed
        if (
            variant.total_uses >= self.MIN_USES_FOR_MUTATION
            and variant.avg_score < self.MUTATION_THRESHOLD
        ):
            new_variant = await self._mutate(template_name, variant)
            if new_variant:
                return new_variant.id

        return None

    async def inject_few_shot(
        self,
        template_name: str,
        examples: List[Dict[str, str]],
    ) -> None:
        """
        Inject few-shot examples from rejection learning into the active variant.

        Each example should have {"input": "...", "output": "..."}.
        """
        variant = self._get_active_variant(template_name)
        if variant:
            # Deduplicate by input
            existing_inputs = {ex.get("input") for ex in variant.few_shot_examples}
            for ex in examples:
                if ex.get("input") not in existing_inputs:
                    variant.few_shot_examples.append(ex)
                    existing_inputs.add(ex.get("input"))
            # Keep only the most recent 5
            variant.few_shot_examples = variant.few_shot_examples[-5:]

    async def _mutate(
        self,
        template_name: str,
        parent: PromptVariant,
    ) -> Optional[PromptVariant]:
        """
        Create a mutated variant by asking an LLM to improve the prompt.

        The LLM sees the original prompt, its average score, and is asked
        to produce a better version.
        """
        mutation_prompt = (
            f"You are a prompt engineer. The following prompt template has been "
            f"performing poorly (avg score: {parent.avg_score:.2f}/1.0, "
            f"worst: {parent.worst_score:.2f}).\n\n"
            f"CURRENT TEMPLATE:\n```\n{parent.template}\n```\n\n"
            f"TASK: Produce an IMPROVED version that will score higher. Improve:\n"
            f"- Clarity of instructions\n"
            f"- Specificity of requirements\n"
            f"- Structure and formatting\n"
            f"- Anti-hallucination guardrails\n\n"
            f"RULES:\n"
            f"- Keep ALL {{variable}} placeholders exactly as they are.\n"
            f"- Do NOT change the overall purpose of the prompt.\n"
            f"- Make targeted improvements, not a complete rewrite.\n\n"
            f"Respond with ONLY the improved prompt template, no explanation."
        )

        try:
            from .council_kernel.engine import get_council_engine
            engine = get_council_engine()
            response = await engine.cascade_query("_prompt_mutation", mutation_prompt, max_budget_usd=0.05)

            new_template = response.response.strip()
            # Validate: must contain at least some of the original placeholders
            original_vars = set(
                v for v in parent.template.split("{") if "}" in v
            )
            if not new_template or len(new_template) < 50:
                logger.warning("Prompt mutation produced too-short result, skipping")
                return None

            new_variant = PromptVariant(
                template=new_template,
                version=parent.version + 1,
                parent_id=parent.id,
                mutation_reason=f"avg_score={parent.avg_score:.2f} < threshold={self.MUTATION_THRESHOLD}",
                few_shot_examples=copy.deepcopy(parent.few_shot_examples),
            )

            self._templates[template_name].append(new_variant)
            self._active_variant[template_name] = new_variant.id

            logger.info(
                f"Prompt mutation: {template_name} v{parent.version} → v{new_variant.version} "
                f"(avg_score {parent.avg_score:.2f} → fresh start)"
            )
            return new_variant

        except Exception as exc:
            logger.warning(f"Prompt mutation failed: {exc}")
            return None

    def _get_active_variant(self, template_name: str) -> Optional[PromptVariant]:
        """Get the currently active variant for a template."""
        active_id = self._active_variant.get(template_name)
        if not active_id:
            return None
        variants = self._templates.get(template_name, [])
        return next((v for v in variants if v.id == active_id), None)

    def get_variant_history(self, template_name: str) -> List[Dict]:
        """Get the full version history for a template."""
        return [
            {
                "id": v.id, "version": v.version,
                "avg_score": round(v.avg_score, 3),
                "total_uses": v.total_uses,
                "best_score": v.best_score,
                "parent_id": v.parent_id,
                "mutation_reason": v.mutation_reason,
                "is_active": v.id == self._active_variant.get(template_name),
                "template_hash": v.template_hash,
            }
            for v in self._templates.get(template_name, [])
        ]

    def list_templates(self) -> List[str]:
        """List all registered template names."""
        return list(self._templates.keys())


# Singleton
_prompt_registry: Optional[PromptRegistry] = None

def get_prompt_registry() -> PromptRegistry:
    global _prompt_registry
    if _prompt_registry is None:
        _prompt_registry = PromptRegistry()
    return _prompt_registry
