"""
Rubric Evaluation Engine — Phase 15 (Elevated): Custom Workspace Rubrics.

Scores LLM responses against structured rubrics.

3 scoring modes:
  Mode 1: LLM-based scoring (accurate, costs ~$0.002 per eval)
  Mode 2: Heuristic scoring (free, good for pre-filtering)
  Mode 3: Hybrid (heuristic first, LLM for borderline cases)

Built-in rubrics:
  - code_review   — correctness, security, maintainability, performance, tests
  - architecture  — scalability, governance, simplicity, security, reversibility
  - general       — accuracy, completeness, clarity, evidence
  - security      — owasp_top10, authz_model, data_exposure, supply_chain, secrets_mgmt
  - cost          — budget_adherence, optimization, roi, waste_detection

NEW: Custom workspace rubrics — define domain-specific rubrics via API,
     persisted to Supabase for cross-session use.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .model_router import LLMProvider
from ...core.logging import logger

# Registry of built-in rubrics
RUBRICS: Dict[str, Dict[str, Dict]] = {
    "code_review": {
        "correctness":     {"weight": 0.30, "description": "Code works as intended, handles edge cases"},
        "security":        {"weight": 0.25, "description": "No vulnerabilities, injection risks, or unsafe patterns"},
        "maintainability": {"weight": 0.20, "description": "Clean, readable, well-documented, follows conventions"},
        "performance":     {"weight": 0.15, "description": "Efficient implementation, no O(n²) where O(n) suffices"},
        "test_coverage":   {"weight": 0.10, "description": "Adequate test coverage for critical paths"},
    },
    "architecture": {
        "scalability":          {"weight": 0.25, "description": "Handles 10x growth without redesign"},
        "governance_compliance":{"weight": 0.25, "description": "Follows AEGION governance tier system"},
        "simplicity":           {"weight": 0.20, "description": "Not over-engineered, YAGNI respected"},
        "security":             {"weight": 0.20, "description": "Security by design, defense in depth"},
        "reversibility":        {"weight": 0.10, "description": "Decision can be unmade if wrong"},
    },
    "general": {
        "accuracy":     {"weight": 0.35, "description": "Factually correct, no hallucinations"},
        "completeness": {"weight": 0.25, "description": "Covers all required aspects"},
        "clarity":      {"weight": 0.20, "description": "Clear, unambiguous, well-structured"},
        "evidence":     {"weight": 0.20, "description": "Claims backed by evidence or reasoning"},
    },
    "security": {
        "owasp_top10":     {"weight": 0.30, "description": "No OWASP Top 10 vulnerabilities"},
        "authz_model":     {"weight": 0.20, "description": "Authorization model is correct and complete"},
        "data_exposure":   {"weight": 0.20, "description": "No PII or secrets in responses/logs"},
        "supply_chain":    {"weight": 0.15, "description": "Dependencies are vetted and pinned"},
        "secrets_mgmt":    {"weight": 0.15, "description": "Secrets in vault, not env vars or code"},
    },
    "cost": {
        "budget_adherence":  {"weight": 0.30, "description": "Stays within cost constraints"},
        "optimization":      {"weight": 0.25, "description": "Uses cheapest model that meets quality bar"},
        "roi":               {"weight": 0.20, "description": "Cost justified by value delivered"},
        "waste_detection":   {"weight": 0.15, "description": "No unnecessary LLM calls or oversized models"},
        "cache_utilization": {"weight": 0.10, "description": "Semantic cache used effectively"},
    },
}

# Custom rubrics (loaded from DB + in-memory additions)
_custom_rubrics: Dict[str, Dict[str, Dict]] = {}


class RubricEngine:
    """
    Score a response against a named rubric.

    Supports built-in and custom workspace rubrics.

    Usage:
        engine = RubricEngine()
        result = await engine.score(response_text, rubric_name="code_review")
        print(result["weighted_total"])  # 0.0 – 1.0

        # Custom rubric
        engine.register_rubric("my_domain", {
            "domain_accuracy": {"weight": 0.5, "description": "Domain-specific correctness"},
            "compliance":      {"weight": 0.5, "description": "Regulatory compliance"},
        })
    """

    def __init__(self) -> None:
        self._custom_loaded = False

    async def score(
        self,
        response: str,
        rubric_name: str = "general",
        evaluator: Optional[LLMProvider] = None,
        evaluator_model: str = "gpt-4o-mini",
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Score a response.

        Args:
            response:        The text to score.
            rubric_name:     Which rubric to use (built-in or custom name).
            evaluator:       Optional LLM provider for AI-based scoring.
            evaluator_model: Which model to use for the evaluator.
            context:         Optional context about what the response was answering.

        Returns dict with 'scores', 'weighted_total', 'rubric', 'is_custom'.
        """
        rubric = self.get_rubric(rubric_name)
        if rubric is None:
            rubric = RUBRICS["general"]
            rubric_name = "general"

        is_custom = rubric_name in _custom_rubrics

        if evaluator is not None:
            scores = await self._llm_score(response, rubric, evaluator, evaluator_model, context)
        else:
            scores = self._heuristic_score(response, rubric)

        # Clamp all scores to [0, 1]
        scores = {k: max(0.0, min(1.0, v)) for k, v in scores.items()}
        weighted_total = sum(scores[k] * rubric[k]["weight"] for k in rubric if k in scores)

        return {
            "scores": scores,
            "weighted_total": round(weighted_total, 4),
            "rubric": rubric_name,
            "is_custom": is_custom,
            "criteria_count": len(rubric),
        }

    def get_rubric(self, name: str) -> Optional[Dict[str, Dict]]:
        """Get a rubric by name (custom first, then built-in)."""
        return _custom_rubrics.get(name) or RUBRICS.get(name)

    def list_rubrics(self) -> List[Dict[str, Any]]:
        """List all available rubrics (built-in + custom)."""
        result = []
        for name, rubric in RUBRICS.items():
            result.append({
                "name": name,
                "criteria_count": len(rubric),
                "criteria": list(rubric.keys()),
                "is_custom": False,
            })
        for name, rubric in _custom_rubrics.items():
            result.append({
                "name": name,
                "criteria_count": len(rubric),
                "criteria": list(rubric.keys()),
                "is_custom": True,
            })
        return result

    def register_rubric(
        self,
        name: str,
        criteria: Dict[str, Dict],
        workspace_id: Optional[str] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        Register a custom rubric.

        Args:
            name:      Unique name (e.g., "fintech_compliance").
            criteria:  Dict of criterion_name → {"weight": float, "description": str}.
            workspace_id: Optional workspace scope.
            persist:   If True, save to Supabase for cross-session use.

        Weights must sum to 1.0 (±0.01 tolerance).
        """
        # Validate weights sum to ~1.0
        total_weight = sum(c.get("weight", 0) for c in criteria.values())
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(
                f"Rubric weights must sum to 1.0, got {total_weight:.3f}. "
                f"Criteria: {list(criteria.keys())}"
            )

        # Validate each criterion has required fields
        for crit_name, crit in criteria.items():
            if "weight" not in crit or "description" not in crit:
                raise ValueError(f"Criterion '{crit_name}' must have 'weight' and 'description'")

        _custom_rubrics[name] = criteria
        logger.info(f"Custom rubric registered: {name} ({len(criteria)} criteria)")

        if persist:
            self._persist_rubric(name, criteria, workspace_id)

        return {
            "name": name,
            "criteria_count": len(criteria),
            "criteria": list(criteria.keys()),
            "is_custom": True,
        }

    def delete_rubric(self, name: str) -> bool:
        """Delete a custom rubric. Cannot delete built-in rubrics."""
        if name in RUBRICS:
            raise ValueError(f"Cannot delete built-in rubric '{name}'")
        if name in _custom_rubrics:
            del _custom_rubrics[name]
            self._delete_persisted_rubric(name)
            return True
        return False

    async def _llm_score(
        self,
        response: str,
        rubric: Dict,
        evaluator: LLMProvider,
        model: str,
        context: Optional[str] = None,
    ) -> Dict[str, float]:
        context_block = f"\nContext: {context[:500]}\n" if context else ""
        criteria_block = "\n".join(
            f"  - {k}: {v['description']} (weight {v['weight']:.0%})"
            for k, v in rubric.items()
        )
        prompt = (
            f"Score this response on each criterion from 0.0 to 1.0.\n"
            f"{context_block}\n"
            f"Response to evaluate:\n{response[:2000]}\n\n"
            f"Criteria:\n{criteria_block}\n\n"
            "Return ONLY a JSON object like: "
            '{"criterion_name": 0.85, ...}  — no extra text.'
        )

        result = await evaluator.generate(prompt, model)
        try:
            parsed = json.loads(result.response)
            # Ensure all criteria are present
            for k in rubric:
                if k not in parsed:
                    parsed[k] = 0.5
            return parsed
        except (json.JSONDecodeError, ValueError):
            return {k: 0.5 for k in rubric}

    def _heuristic_score(self, response: str, rubric: Dict) -> Dict[str, float]:
        """
        Improved heuristic scoring — uses multiple text signals.

        Better than the original flat base+bonus approach.
        """
        scores = {}
        lower = response.lower()
        words = lower.split()
        word_count = len(words)

        for criterion in rubric:
            base = 0.50

            # Length signals
            if word_count > 200:
                base += 0.10
            if word_count > 500:
                base += 0.05

            # Code presence
            if "```" in response:
                base += 0.08

            # Evidence/reasoning signals
            reasoning_words = {"because", "therefore", "evidence", "reason",
                              "specifically", "for example", "analysis shows"}
            if any(w in lower for w in reasoning_words):
                base += 0.10

            # Structured output (bullet points, numbered lists)
            if any(line.strip().startswith(("- ", "* ", "1.", "2.")) for line in response.split("\n")):
                base += 0.05

            # Criterion-specific heuristics
            if "security" in criterion and any(w in lower for w in ("vulnerability", "cve", "owasp", "injection", "xss")):
                base += 0.10
            if "test" in criterion and any(w in lower for w in ("test", "assert", "mock", "fixture", "coverage")):
                base += 0.10
            if "performance" in criterion and any(w in lower for w in ("o(n", "latency", "throughput", "benchmark", "profil")):
                base += 0.10

            scores[criterion] = min(1.0, base)

        return scores

    def _persist_rubric(self, name: str, criteria: Dict, workspace_id: Optional[str]) -> None:
        """Save custom rubric to Supabase."""
        try:
            from ...db.supabase_client import get_supabase_client
            get_supabase_client().table("custom_rubrics").upsert({
                "name": name,
                "workspace_id": workspace_id,
                "criteria": criteria,
            }).execute()
        except Exception as exc:
            logger.warning(f"Rubric persistence failed (non-fatal): {exc}")

    def _delete_persisted_rubric(self, name: str) -> None:
        try:
            from ...db.supabase_client import get_supabase_client
            get_supabase_client().table("custom_rubrics").delete().eq("name", name).execute()
        except Exception:
            pass

    async def load_custom_rubrics(self, workspace_id: Optional[str] = None) -> int:
        """Load custom rubrics from Supabase. Call on startup."""
        if self._custom_loaded:
            return len(_custom_rubrics)
        try:
            from ...db.supabase_client import get_supabase_client
            q = get_supabase_client().table("custom_rubrics").select("name,criteria")
            if workspace_id:
                q = q.eq("workspace_id", workspace_id)
            result = q.execute()
            for row in (result.data or []):
                _custom_rubrics[row["name"]] = row["criteria"]
            self._custom_loaded = True
            return len(_custom_rubrics)
        except Exception as exc:
            logger.warning(f"Loading custom rubrics failed: {exc}")
            return 0


# Singleton
_rubric_engine: Optional[RubricEngine] = None


def get_rubric_engine() -> RubricEngine:
    global _rubric_engine
    if _rubric_engine is None:
        _rubric_engine = RubricEngine()
    return _rubric_engine
