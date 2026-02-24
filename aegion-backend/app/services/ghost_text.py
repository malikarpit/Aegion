"""
Ghost Text Engine — Phase 25: Inline AI Code Completions.

Powers the VS Code extension's inline completion feature.
Uses the FrugalGPT cascade for cost-effective completions.

Features:
  - Prefix/suffix context window for fill-in-the-middle (FIM)
  - Language-aware prompting
  - File path context for project awareness
  - Semantic cache integration (identical completion prompts are cached)
  - Cost tracking per completion
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.logging import logger


class GhostTextEngine:
    """
    Inline code completion engine backed by ACK cascade.

    Usage:
        ghost = GhostTextEngine()
        result = await ghost.complete(
            workspace_id="ws-123",
            prefix="def fib(n):\n    if n <= 1:\n        return n\n    ",
            suffix="\n\ndef main():\n    print(fib(10))",
            language="python",
            file_path="src/math/fib.py",
        )
        # result = {"completion": "return fib(n-1) + fib(n-2)", ...}
    """

    # Maximum context window sizes (characters)
    MAX_PREFIX = 2000
    MAX_SUFFIX = 500

    async def complete(
        self,
        workspace_id: str,
        prefix: str,
        suffix: str,
        language: str,
        file_path: str,
        max_tokens: int = 256,
    ) -> Dict[str, Any]:
        """
        Generate an inline code completion.

        Args:
            workspace_id: Current workspace.
            prefix:       Code before the cursor.
            suffix:       Code after the cursor.
            language:     Programming language.
            file_path:    File being edited.
            max_tokens:   Max completion length.

        Returns dict with: completion, model, cost_usd, confidence, latency_ms
        """
        prompt = self._build_prompt(prefix, suffix, language, file_path)

        try:
            from .council_kernel.engine import get_council_engine

            engine = get_council_engine()
            response = await engine.cascade_query(
                workspace_id=workspace_id,
                prompt=prompt,
                max_budget_usd=0.01,  # Hard cap: never spend more than $0.01 per completion
            )

            # Strip any markdown fences or explanation the model may add
            completion = self._clean_completion(response.response)

            return {
                "completion": completion,
                "model": response.model,
                "provider": response.provider,
                "cost_usd": response.cost_usd,
                "confidence": response.confidence,
                "latency_ms": response.latency_ms,
                "tokens_used": response.tokens_in + response.tokens_out,
            }
        except Exception as exc:
            logger.warning(f"Ghost text completion failed: {exc}")
            return {
                "completion": "",
                "model": "none",
                "provider": "none",
                "cost_usd": 0.0,
                "confidence": 0.0,
                "latency_ms": 0,
                "tokens_used": 0,
                "error": str(exc),
            }

    def _build_prompt(self, prefix: str, suffix: str, language: str, file_path: str) -> str:
        """Build a fill-in-the-middle (FIM) prompt."""
        trimmed_prefix = prefix[-self.MAX_PREFIX:]
        trimmed_suffix = suffix[:self.MAX_SUFFIX]

        return (
            f"Complete the {language} code between PREFIX and SUFFIX. "
            f"File: {file_path}\n\n"
            f"PREFIX:\n{trimmed_prefix}\n\n"
            f"SUFFIX:\n{trimmed_suffix}\n\n"
            "Return ONLY the completion code. No explanations, no markdown fences, "
            "no comments about what you're doing. Just the code that goes between PREFIX and SUFFIX."
        )

    def _clean_completion(self, raw: str) -> str:
        """Strip markdown fences and extra explanation from model output."""
        text = raw.strip()

        # Remove ```language ... ``` wrapper if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Drop first line (```python) and last line (```)
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        return text.strip()


# Singleton
_ghost_text: Optional[GhostTextEngine] = None


def get_ghost_text() -> GhostTextEngine:
    global _ghost_text
    if _ghost_text is None:
        _ghost_text = GhostTextEngine()
    return _ghost_text
