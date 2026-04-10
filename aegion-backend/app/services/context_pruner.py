"""
Context Pruner — Phase 79: Compress conversation history to save tokens.

Keeps the last N turns verbatim; compresses older turns into a compact summary.
On long sessions this can save 30-50% of context tokens — the second-biggest
input-cost reduction after the Prompt Gateway.

Two summarization strategies:
  1. AI summary (Gemini 2.0 Flash) for histories > 100 words
  2. Heuristic keyword extraction as fallback (no LLM cost)
"""

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .council_kernel.model_router import ModelRouter

KEEP_RECENT: int = 3          # Verbatim turns to keep
MAX_SUMMARY_TOKENS: int = 150  # Target word budget for the compressed summary
GATEWAY_PROVIDER: str = "google"
GATEWAY_MODEL: str = "gemini-2.0-flash"

# Keywords that signal a turn is worth preserving in the summary
_IMPORTANT_KEYWORDS = (
    "decided", "approved", "rejected", "error", "fix", "implement",
    "changed", "blocked", "todo", "warning", "critical", "deploy",
)


class ContextPruner:
    """
    Prunes conversation history before passing it to the council.

    Usage in engine.py (Step 0.7):
        if config.context_pruning_enabled and context.get("conversation"):
            pruned = await context_pruner.prune(
                context["conversation"],
                model_router=self.model_router,
                keep_recent=config.context_keep_recent,
            )
            context["conversation"] = pruned["context"]
    """

    async def prune(
        self,
        conversation: List[Dict],
        model_router: Optional["ModelRouter"] = None,
        keep_recent: int = KEEP_RECENT,
    ) -> Dict:
        """
        Prune conversation history, retaining recent turns verbatim.

        Args:
            conversation:  List of {"role": ..., "content": ...} dicts.
            model_router:  If provided, uses Flash for AI summarization.
            keep_recent:   Number of recent turns to keep unchanged.

        Returns:
            dict with "context" (pruned list), "pruned", "saved_tokens", etc.
        """
        if len(conversation) <= keep_recent:
            return {
                "context": conversation,
                "pruned": False,
                "original_turns": len(conversation),
                "kept_turns": len(conversation),
                "compressed_turns": 0,
                "saved_tokens": 0,
            }

        recent = conversation[-keep_recent:]
        old = conversation[:-keep_recent]

        old_text = " ".join(m.get("content", "") for m in old)
        original_tokens = len(old_text.split())

        if model_router and original_tokens > 100:
            summary = await self._ai_summarize(old, model_router)
        else:
            summary = self._heuristic_summarize(old)

        pruned_context: List[Dict] = [
            {"role": "system", "content": f"[Summary of earlier conversation]: {summary}"}
        ]
        pruned_context.extend(recent)

        saved = max(0, original_tokens - len(summary.split()))

        return {
            "context": pruned_context,
            "pruned": True,
            "original_turns": len(conversation),
            "kept_turns": len(recent),
            "compressed_turns": len(old),
            "saved_tokens": saved,
        }

    async def _ai_summarize(self, old_turns: List[Dict], router: "ModelRouter") -> str:
        """Use the cheapest registered model to summarize old turns."""
        text = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')[:300]}"
            for m in old_turns
        )
        prompt = (
            f"Summarize this conversation history in under {MAX_SUMMARY_TOKENS} words.\n"
            "Keep: key decisions, code references, unresolved questions.\n"
            "Drop: greetings, acknowledgements, repeated information.\n\n"
            f"{text}"
        )
        try:
            # Use the global gateway model; fall back to any registered provider
            if GATEWAY_PROVIDER in router.providers:
                result = await router.call(GATEWAY_PROVIDER, GATEWAY_MODEL, prompt,
                                           max_tokens=200, temperature=0.3)
            elif router.providers:
                prov = next(iter(router.providers))
                models = list(router.providers[prov].models.keys()) if router.providers[prov].models else []
                mdl = models[0] if models else ""
                result = await router.call(prov, mdl, prompt,
                                           max_tokens=200, temperature=0.3)
            else:
                return self._heuristic_summarize(old_turns)
            return result.response[:600]
        except Exception:
            return self._heuristic_summarize(old_turns)

    def _heuristic_summarize(self, old_turns: List[Dict]) -> str:
        """Keyword-based fallback summary — zero LLM cost."""
        key_points: List[str] = []
        for m in old_turns:
            content = m.get("content", "")
            if any(kw in content.lower() for kw in _IMPORTANT_KEYWORDS):
                key_points.append(content[:100])
        return " | ".join(key_points[:5]) or "General discussion about the project."


# Module-level singleton
context_pruner = ContextPruner()
