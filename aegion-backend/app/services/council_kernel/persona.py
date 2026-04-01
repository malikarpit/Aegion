"""
Persona Engine — Phase 16: Role-Based Council Perspectives.

Assigns distinct AEGION-domain expert personas to council members.
Each persona has a system prompt, focus keywords, and a specific axe to grind —
ensuring the council gets adversarial, multi-dimensional analysis rather than
homogeneous agreement.

6 built-in personas:
  security_auditor, performance_architect, cost_analyst,
  governance_advisor, user_advocate, devils_advocate
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .model_router import ModelRouter

# ──────────────────────────────────────────────────────────────────────────────
# Persona definitions
# ──────────────────────────────────────────────────────────────────────────────

PERSONAS: Dict[str, Dict[str, Any]] = {
    "security_auditor": {
        "name": "Security Auditor",
        "system_prompt": (
            "You are a paranoid security expert. Your ONLY concern is finding vulnerabilities, "
            "data exposure risks, injection attacks, authentication gaps, and supply chain threats. "
            "Rate everything through a security lens. Assume attackers are actively looking for flaws."
        ),
        "focus": ["CVE", "injection", "auth", "encryption", "OWASP", "supply chain", "privilege escalation"],
    },
    "performance_architect": {
        "name": "Performance Architect",
        "system_prompt": (
            "You are a performance obsessive. Every millisecond matters. "
            "Focus on latency, throughput, memory usage, query optimization, N+1 queries, "
            "caching opportunities, and scalability bottlenecks. "
            "Reject anything that introduces unnecessary overhead."
        ),
        "focus": ["latency", "throughput", "memory", "cache", "N+1", "index", "connection pool"],
    },
    "cost_analyst": {
        "name": "Cost Analyst",
        "system_prompt": (
            "You analyze every decision through a cost lens. API costs, compute costs, "
            "storage costs, egress costs, opportunity costs. "
            "Find the cheapest viable solution. "
            "Challenge expensive approaches with cheaper alternatives."
        ),
        "focus": ["cost", "pricing", "budget", "token", "compute", "storage", "cheaper"],
    },
    "governance_advisor": {
        "name": "Governance Advisor",
        "system_prompt": (
            "You enforce AEGION's governance model strictly. "
            "No AI writes to Chronos directly. No AI approves decisions autonomously. "
            "All changes must follow the tier system (T0→T3). "
            "You ensure governance boundaries are never violated and every change is auditable."
        ),
        "focus": ["Archon", "tier", "governance", "approval", "policy", "compliance", "audit"],
    },
    "user_advocate": {
        "name": "User Advocate",
        "system_prompt": (
            "You represent the end user. Is this feature useful? Is it intuitive? "
            "Does it add complexity without value? "
            "Challenge features that are technically cool but user-hostile. "
            "Simplicity wins. Documentation matters."
        ),
        "focus": ["UX", "usability", "simplicity", "documentation", "onboarding", "friction"],
    },
    "devils_advocate": {
        "name": "Devil's Advocate",
        "system_prompt": (
            "Your job is to DISAGREE with the majority position and find its flaws. "
            "Present counter-arguments even when the majority might be right. "
            "Find edge cases, failure modes, and unintended consequences. "
            "You exist to prevent groupthink."
        ),
        "focus": ["edge case", "failure mode", "risk", "alternative", "bias", "unintended"],
    },
}


class PersonaEngine:
    """
    Orchestrates persona-driven council debates.

    Each persona gets a dedicated system prompt injected before the proposition,
    ensuring genuinely differentiated, adversarial perspectives.
    """

    def __init__(self, model_router: Optional[ModelRouter] = None) -> None:
        self.router = model_router

    async def debate_with_personas(
        self,
        proposition: str,
        persona_keys: List[str],
        models: List[Tuple[str, str]],
        model_router: Optional[ModelRouter] = None,
    ) -> Dict[str, Any]:
        """
        Run proposition through the selected personas.

        Args:
            proposition:  The question or decision being debated.
            persona_keys: List of persona keys from PERSONAS dict.
            models:       (provider, model) tuples — cycled across personas.
            model_router: Provide if not set in constructor.

        Returns dict with proposition and per-persona responses.
        """
        router = model_router or self.router
        if router is None:
            raise RuntimeError("ModelRouter is required — pass via constructor or debate_with_personas()")

        responses = []
        for i, key in enumerate(persona_keys):
            persona = PERSONAS.get(key, PERSONAS["user_advocate"])
            provider, model = models[i % len(models)]

            prompt = (
                f"{persona['system_prompt']}\n\n"
                f"PROPOSITION: {proposition}\n\n"
                f"Respond in character as {persona['name']}. "
                f"Focus on: {', '.join(persona['focus'])}. "
                "Be specific. Provide evidence for your position."
            )

            try:
                result = await router.call(provider, model, prompt)
                responses.append({
                    "persona": persona["name"],
                    "persona_key": key,
                    "position": result.response,
                    "model": model,
                    "provider": provider,
                    "cost_usd": result.cost_usd,
                    "tokens": result.tokens_in + result.tokens_out,
                })
            except Exception as exc:
                responses.append({
                    "persona": persona["name"],
                    "persona_key": key,
                    "position": f"[Error: {exc}]",
                    "model": model,
                    "provider": provider,
                    "cost_usd": 0.0,
                    "tokens": 0,
                })

        return {
            "proposition": proposition,
            "persona_responses": responses,
            "total_cost_usd": round(sum(r["cost_usd"] for r in responses), 6),
        }

    @staticmethod
    def available_personas() -> List[str]:
        """Return list of available persona keys."""
        return list(PERSONAS.keys())


# Singleton
_persona_engine: Optional[PersonaEngine] = None


def get_persona_engine() -> PersonaEngine:
    global _persona_engine
    if _persona_engine is None:
        _persona_engine = PersonaEngine()
    return _persona_engine
