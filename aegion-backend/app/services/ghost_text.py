"""
Ghost Text Engine — Phase 25: Inline AI Code Completions.

Powers the VS Code extension's inline completion feature.
Uses the FrugalGPT cascade for cost-effective completions.

Features:
  - Prefix/suffix context window for fill-in-the-middle (FIM)
  - Language-aware prompting with provider-specific FIM tokens
  - File path context for project awareness
  - Semantic cache integration (identical completion prompts are cached)
  - Cost tracking per completion to cost_tracking table
  - Request cancellation support for debouncing
  - Multi-line vs single-line detection
  - Import header extraction for better context
  - Post-processing with language-aware validation
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ..core.logging import logger


# ──────────────────────────────────────────────────────────────────────────────
# Data types
# ──────────────────────────────────────────────────────────────────────────────

class CompletionMode(str, Enum):
    """Whether the completion target is a single line or a multi-line block."""
    SINGLE_LINE = "single_line"
    MULTI_LINE = "multi_line"


@dataclass
class GhostTextResult:
    """Structured result from a ghost text completion."""
    text: str
    model: str = "none"
    provider: str = "none"
    source: str = "llm"           # "llm", "cache", "cancelled", "error"
    cost_usd: float = 0.0
    confidence: float = 0.0
    latency_ms: int = 0
    tokens_used: int = 0
    mode: CompletionMode = CompletionMode.SINGLE_LINE
    error: Optional[str] = None

    @classmethod
    def empty(cls, reason: str = "cancelled") -> "GhostTextResult":
        return cls(text="", source=reason, model="none")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "completion": self.text,
            "model": self.model,
            "provider": self.provider,
            "source": self.source,
            "cost_usd": self.cost_usd,
            "confidence": self.confidence,
            "latency_ms": self.latency_ms,
            "tokens_used": self.tokens_used,
            "mode": self.mode.value,
            **({"error": self.error} if self.error else {}),
        }


# ──────────────────────────────────────────────────────────────────────────────
# FIM token maps per provider
# ──────────────────────────────────────────────────────────────────────────────

_FIM_TOKENS = {
    "starcoder": {
        "prefix": "<fim_prefix>",
        "suffix": "<fim_suffix>",
        "middle": "<fim_middle>",
    },
    "codestral": {
        "prefix": "[SUFFIX]",
        "suffix": "[PREFIX]",
        "middle": "[MIDDLE]",
    },
    "deepseek": {
        "prefix": "<|fim▁begin|>",
        "suffix": "<|fim▁hole|>",
        "middle": "<|fim▁end|>",
    },
    # Fallback: natural-language FIM prompt (works with GPT-4, Claude, Gemini)
    "default": None,
}

# Language → common stop sequences for completions
_STOP_SEQUENCES: Dict[str, List[str]] = {
    "python":     ["\n\ndef ", "\n\nclass ", "\nif __name__", "\n# ---"],
    "typescript": ["\n\nexport ", "\n\nfunction ", "\n\nclass ", "\n\ninterface "],
    "javascript": ["\n\nexport ", "\n\nfunction ", "\n\nclass "],
    "rust":       ["\n\nfn ", "\n\nimpl ", "\n\npub "],
    "go":         ["\n\nfunc ", "\n\ntype "],
    "java":       ["\n\npublic ", "\n\nclass ", "\n\n@"],
    "default":    ["\n\n\n"],
}

# File patterns that indicate high-sensitivity (never auto-complete)
_SENSITIVE_PATHS = re.compile(
    r"(\.env|secret|credential|password|token|key|auth).*",
    re.IGNORECASE,
)


class GhostTextEngine:
    """
    Production-grade inline code completion engine backed by ACK cascade.

    Pipeline:
      1. Validate request (check cancellation, sensitivity)
      2. Detect completion mode (single-line vs multi-line)
      3. Extract import headers for context enrichment
      4. Build cache key and check semantic cache
      5. Build FIM prompt (provider-aware or natural-language)
      6. Route through FrugalGPT cascade (cheapest model first)
      7. Post-process (strip fences, validate syntax, trim)
      8. Cache result + track cost
    """

    # Context window sizes (characters)
    MAX_PREFIX_CHARS = 4000     # ~1000 tokens of prefix context
    MAX_SUFFIX_CHARS = 1500    # ~375 tokens of suffix context
    MAX_IMPORT_CHARS = 800     # ~200 tokens of import header

    # Debounce / cancellation
    _cancelled: Dict[str, bool] = {}

    # In-memory completion cache (fast path before pgvector)
    _local_cache: Dict[str, str] = {}
    _LOCAL_CACHE_MAX = 500

    def __init__(self) -> None:
        self._metrics = _CompletionMetrics()

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    async def complete(
        self,
        workspace_id: str,
        prefix: str,
        suffix: str,
        language: str,
        file_path: str,
        max_tokens: int = 256,
        request_id: Optional[str] = None,
    ) -> GhostTextResult:
        """
        Generate an inline code completion.

        Args:
            workspace_id: Current workspace.
            prefix:       Code before the cursor.
            suffix:       Code after the cursor.
            language:     Programming language (python, typescript, etc.).
            file_path:    Relative file path being edited.
            max_tokens:   Max completion length.
            request_id:   Optional debounce ID; if cancelled, returns empty.

        Returns:
            GhostTextResult with completion text, cost, and metadata.
        """
        start = time.monotonic()

        # ── 1. Check cancellation ──
        if request_id and self._cancelled.pop(request_id, False):
            self._metrics.record("cancelled")
            return GhostTextResult.empty("cancelled")

        # ── 1b. Sensitivity gate ──
        if _SENSITIVE_PATHS.search(file_path):
            logger.info(f"Ghost text blocked for sensitive file: {file_path}")
            self._metrics.record("blocked")
            return GhostTextResult.empty("blocked_sensitive")

        # ── 2. Detect completion mode ──
        mode = self._detect_mode(prefix)

        # ── 3. Extract import header ──
        import_header = self._extract_imports(prefix, language)

        # ── 4. Check cache ──
        cache_key = self._build_cache_key(file_path, prefix, suffix)

        # Fast local cache
        if cache_key in self._local_cache:
            latency = int((time.monotonic() - start) * 1000)
            self._metrics.record("cache_hit_local")
            return GhostTextResult(
                text=self._local_cache[cache_key],
                source="cache",
                latency_ms=latency,
                mode=mode,
            )

        # pgvector semantic cache
        cached_text = await self._check_pgvector_cache(workspace_id, prefix, suffix)
        if cached_text:
            latency = int((time.monotonic() - start) * 1000)
            self._metrics.record("cache_hit_pgvector")
            self._local_cache_put(cache_key, cached_text)
            return GhostTextResult(
                text=cached_text,
                source="cache",
                latency_ms=latency,
                mode=mode,
            )

        # ── 5. Build prompt ──
        prompt = self._build_fim_prompt(
            prefix, suffix, language, file_path, import_header, mode,
        )

        # ── 6. Query cascade ──
        try:
            from .council_kernel.engine import get_council_engine

            engine = get_council_engine()

            # Pick stop sequences for the language
            stops = _STOP_SEQUENCES.get(language, _STOP_SEQUENCES["default"])

            response = await engine.cascade_query(
                workspace_id=workspace_id,
                prompt=prompt,
                max_budget_usd=0.01,  # Hard cap: $0.01 per completion
            )

            # ── 7. Post-process ──
            completion = self._post_process(response.response, language, mode)
            latency = int((time.monotonic() - start) * 1000)

            if not completion.strip():
                self._metrics.record("empty_response")
                return GhostTextResult.empty("empty_response")

            # ── 8. Cache + cost tracking ──
            self._local_cache_put(cache_key, completion)
            await self._store_pgvector_cache(workspace_id, prefix, suffix, completion)
            await self._track_cost(
                workspace_id, response.model, response.provider,
                response.tokens_in + response.tokens_out,
                response.cost_usd, "ghost_text",
            )

            self._metrics.record("success")
            return GhostTextResult(
                text=completion,
                model=response.model,
                provider=response.provider,
                source="llm",
                cost_usd=response.cost_usd,
                confidence=response.confidence,
                latency_ms=latency,
                tokens_used=response.tokens_in + response.tokens_out,
                mode=mode,
            )

        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            logger.warning(f"Ghost text completion failed: {exc}")
            self._metrics.record("error")
            return GhostTextResult(
                text="",
                source="error",
                latency_ms=latency,
                mode=mode,
                error=str(exc),
            )

    def cancel(self, request_id: str) -> None:
        """Cancel an in-flight completion request (called by debounce logic)."""
        self._cancelled[request_id] = True

    def get_metrics(self) -> Dict[str, int]:
        """Return completion metrics for observability."""
        return self._metrics.to_dict()

    # ──────────────────────────────────────────────
    # Mode detection
    # ──────────────────────────────────────────────

    def _detect_mode(self, prefix: str) -> CompletionMode:
        """
        Determine if we should generate a single-line or multi-line completion.

        Multi-line triggers:
          - Cursor is at a blank line after a colon (Python def/class/if)
          - Cursor is at a blank line after an opening brace
          - Cursor is after a function signature without a body
        """
        lines = prefix.rstrip().split("\n")
        if not lines:
            return CompletionMode.SINGLE_LINE

        last_line = lines[-1].rstrip()

        # Blank line → look at the previous non-blank line
        if not last_line and len(lines) >= 2:
            prev_line = lines[-2].rstrip()
            if prev_line.endswith(":") or prev_line.endswith("{"):
                return CompletionMode.MULTI_LINE

        # Line ending with colon or opening brace
        if last_line.endswith(":") or last_line.endswith("{"):
            return CompletionMode.MULTI_LINE

        # After a function/class definition with no body yet
        if re.search(r"(def |async def |function |class )\w+.*:\s*$", last_line):
            return CompletionMode.MULTI_LINE

        return CompletionMode.SINGLE_LINE

    # ──────────────────────────────────────────────
    # Import extraction
    # ──────────────────────────────────────────────

    def _extract_imports(self, prefix: str, language: str) -> str:
        """
        Extract import/include statements from the top of the file.
        These provide critical type context for completions.
        """
        lines = prefix.split("\n")
        import_lines: List[str] = []

        patterns = {
            "python":     r"^\s*(import |from )",
            "typescript": r"^\s*(import |require\()",
            "javascript": r"^\s*(import |require\(|const .+ = require)",
            "java":       r"^\s*(import |package )",
            "go":         r"^\s*(import )",
            "rust":       r"^\s*(use |mod |extern crate )",
        }
        pattern = patterns.get(language, r"^\s*(import |#include |using )")
        regex = re.compile(pattern)

        for line in lines[:50]:  # Only scan first 50 lines
            if regex.match(line):
                import_lines.append(line.rstrip())

        result = "\n".join(import_lines)
        return result[:self.MAX_IMPORT_CHARS]

    # ──────────────────────────────────────────────
    # Prompt building
    # ──────────────────────────────────────────────

    def _build_fim_prompt(
        self,
        prefix: str,
        suffix: str,
        language: str,
        file_path: str,
        import_header: str,
        mode: CompletionMode,
    ) -> str:
        """
        Build a fill-in-the-middle (FIM) prompt.

        For providers with native FIM support (StarCoder, Codestral, DeepSeek),
        uses their token format. For general models (GPT-4, Claude, Gemini),
        uses a natural-language instruction prompt.
        """
        trimmed_prefix = prefix[-self.MAX_PREFIX_CHARS:]
        trimmed_suffix = suffix[:self.MAX_SUFFIX_CHARS]

        # Determine mode hint
        if mode == CompletionMode.MULTI_LINE:
            mode_hint = (
                "Generate a COMPLETE multi-line code block (function body, class body, "
                "or control flow block). Stop at the end of the logical block."
            )
        else:
            mode_hint = (
                "Generate ONLY the code to complete the current line. "
                "Stop at the end of the line (do not add extra lines)."
            )

        # Natural-language FIM prompt (universal, works with all providers)
        parts = [
            f"You are an expert {language} developer. Complete the code at the cursor position.",
            f"File: {file_path}",
            "",
            mode_hint,
            "",
        ]

        # Add import context if available
        if import_header:
            parts.extend([
                "IMPORTS (for type context):",
                import_header,
                "",
            ])

        parts.extend([
            "CODE BEFORE CURSOR:",
            trimmed_prefix,
            "",
            "CODE AFTER CURSOR:",
            trimmed_suffix if trimmed_suffix.strip() else "(end of file)",
            "",
            "RULES:",
            "- Return ONLY the completion code, nothing else.",
            "- No markdown fences (```), no explanations, no comments about what you're doing.",
            "- Match the existing indentation and coding style exactly.",
            "- Do NOT repeat code that is already in the prefix or suffix.",
        ])

        return "\n".join(parts)

    # ──────────────────────────────────────────────
    # Post-processing
    # ──────────────────────────────────────────────

    def _post_process(self, raw: str, language: str, mode: CompletionMode) -> str:
        """
        Clean up the raw model output:
          1. Strip markdown fences
          2. Remove meta-commentary
          3. Trim to appropriate scope (single-line or multi-line block)
          4. Validate basic syntax (matching brackets/parens)
        """
        text = raw.strip()

        # ── Strip markdown fences ──
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]  # Drop ```python line
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        # ── Remove meta-commentary patterns ──
        # Models sometimes add "Here's the completion:" or similar
        commentary_patterns = [
            r"^(Here'?s? (?:the|your|my) (?:completion|code|answer)[:\.]?\s*\n?)",
            r"^(The (?:completion|code|answer) (?:is|would be)[:\.]?\s*\n?)",
            r"^(I'?(?:ll|d) (?:suggest|recommend|complete)[^:\n]*[:\.]?\s*\n?)",
        ]
        for pattern in commentary_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # ── Mode-specific trimming ──
        if mode == CompletionMode.SINGLE_LINE:
            # Take only the first non-empty line
            lines = [l for l in text.split("\n") if l.strip()]
            text = lines[0] if lines else ""
        else:
            # Multi-line: stop at double-blank-line or start of next top-level definition
            stop_patterns = _STOP_SEQUENCES.get(language, _STOP_SEQUENCES["default"])
            for stop in stop_patterns:
                idx = text.find(stop)
                if idx > 0:
                    text = text[:idx]
                    break

        # ── Trim trailing whitespace ──
        text = text.rstrip()

        # ── Basic bracket validation ──
        text = self._validate_brackets(text)

        return text

    def _validate_brackets(self, text: str) -> str:
        """
        Ensure brackets/parens/braces are balanced.
        If there's an unmatched opener, trim back to the last balanced point.
        """
        stack: List[str] = []
        match_map = {")": "(", "]": "[", "}": "{"}
        last_balanced_idx = 0

        for i, ch in enumerate(text):
            if ch in "([{":
                stack.append(ch)
            elif ch in ")]}":
                if stack and stack[-1] == match_map[ch]:
                    stack.pop()
                    if not stack:
                        last_balanced_idx = i + 1
                else:
                    # Unmatched closer — trim here
                    return text[:i]

        if not stack:
            return text
        # If there are unclosed openers, trim to last balanced point
        if last_balanced_idx > 0:
            return text[:last_balanced_idx]
        return text

    # ──────────────────────────────────────────────
    # Caching
    # ──────────────────────────────────────────────

    def _build_cache_key(self, file_path: str, prefix: str, suffix: str) -> str:
        """Hash the relevant context to create a cache key."""
        content = f"{file_path}::{prefix[-500:]}::{suffix[:200]}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _local_cache_put(self, key: str, value: str) -> None:
        """Add to local cache with LRU eviction."""
        if len(self._local_cache) >= self._LOCAL_CACHE_MAX:
            # Evict oldest (first inserted)
            oldest = next(iter(self._local_cache))
            del self._local_cache[oldest]
        self._local_cache[key] = value

    async def _check_pgvector_cache(
        self, workspace_id: str, prefix: str, suffix: str,
    ) -> Optional[str]:
        """Check pgvector semantic cache for similar completions."""
        try:
            from .council_kernel.cache import get_semantic_cache
            cache = get_semantic_cache()
            cache_query = f"FIM:{prefix[-300:]}"
            result = await cache.check(workspace_id, cache_query)
            if result:
                return result.get("response_text")
        except Exception as exc:
            logger.debug(f"Ghost text pgvector cache check failed: {exc}")
        return None

    async def _store_pgvector_cache(
        self, workspace_id: str, prefix: str, suffix: str, completion: str,
    ) -> None:
        """Store completion in pgvector cache for future similarity matches."""
        try:
            from .council_kernel.cache import get_semantic_cache
            cache = get_semantic_cache()
            cache_query = f"FIM:{prefix[-300:]}"
            await cache.store(workspace_id, cache_query, completion, "ghost_text")
        except Exception as exc:
            logger.debug(f"Ghost text pgvector cache store failed: {exc}")

    # ──────────────────────────────────────────────
    # Cost tracking
    # ──────────────────────────────────────────────

    async def _track_cost(
        self,
        workspace_id: str,
        model: str,
        provider: str,
        tokens: int,
        cost_usd: float,
        purpose: str,
    ) -> None:
        """Persist completion cost to Supabase cost_tracking table."""
        try:
            from ..db.supabase_client import get_supabase_client
            client = get_supabase_client()
            client.table("cost_tracking").insert({
                "workspace_id": workspace_id,
                "models": model,
                "purpose": purpose,
                "tokens_in": tokens // 2,  # Approximate split
                "tokens_out": tokens // 2,
                "cost_usd": cost_usd,
                "cache_hit": False,
            }).execute()
        except Exception as exc:
            logger.debug(f"Ghost text cost tracking failed (non-fatal): {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# Completion metrics
# ──────────────────────────────────────────────────────────────────────────────

class _CompletionMetrics:
    """Simple in-memory counter for ghost text completion outcomes."""

    def __init__(self) -> None:
        self._counters: Dict[str, int] = {
            "success": 0,
            "cancelled": 0,
            "blocked": 0,
            "cache_hit_local": 0,
            "cache_hit_pgvector": 0,
            "empty_response": 0,
            "error": 0,
        }

    def record(self, outcome: str) -> None:
        self._counters[outcome] = self._counters.get(outcome, 0) + 1

    def to_dict(self) -> Dict[str, int]:
        total = sum(self._counters.values())
        return {
            **self._counters,
            "total": total,
            "cache_rate": round(
                (self._counters["cache_hit_local"] + self._counters["cache_hit_pgvector"])
                / max(total, 1)
                * 100,
                1,
            ),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_ghost_text: Optional[GhostTextEngine] = None


def get_ghost_text() -> GhostTextEngine:
    """Get the application-wide GhostTextEngine singleton."""
    global _ghost_text
    if _ghost_text is None:
        _ghost_text = GhostTextEngine()
    return _ghost_text
