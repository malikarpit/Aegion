"""
AI Commands Engine — Phase 42: Natural Language Command Processing.

Maps natural language commands to AEGION operations.
Falls back to ACK council for ambiguous commands.

Supported commands:
  "review my PR"          → diff review
  "check security"        → sentinel scan
  "what's the risk?"      → risk score
  "summarize session"     → distillation council
  "explain this decision" → reasoning chain lookup
  "show me the timeline"  → chronos timeline
  "debate this approach"  → debate engine
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..core.logging import logger


# Command pattern → handler name mapping
_COMMAND_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    # Security
    (re.compile(r"(?:check|scan|audit)\s+(?:security|vulnerabilities|code)", re.I), "security_scan", "Run a security scan"),
    (re.compile(r"(?:is|are)\s+(?:there|this)\s+(?:safe|secure|vulnerable)", re.I), "security_scan", "Security check"),

    # Risk
    (re.compile(r"(?:what(?:'s| is)?\s+(?:the\s+)?risk|risk\s+(?:score|level|assessment))", re.I), "risk_score", "Calculate risk score"),

    # Review
    (re.compile(r"(?:review|check)\s+(?:my|the|this)?\s*(?:PR|pull\s*request|diff|changes?)", re.I), "diff_review", "Review code changes"),

    # Debate
    (re.compile(r"(?:debate|discuss|argue)\s+(?:this|about|whether)", re.I), "debate", "Start a debate"),

    # Summary
    (re.compile(r"(?:summarize|summary|distill)\s+(?:this|the|current)?\s*(?:session|conversation|work)", re.I), "summarize", "Summarize session"),

    # Timeline
    (re.compile(r"(?:show|get|list)\s+(?:me\s+)?(?:the\s+)?(?:timeline|history|events)", re.I), "timeline", "Show timeline"),

    # Decision
    (re.compile(r"(?:explain|show|why)\s+(?:this|the|that)?\s*(?:decision|choice|reasoning)", re.I), "reasoning", "Explain reasoning"),

    # Ghost text
    (re.compile(r"(?:complete|finish|continue)\s+(?:this|the|my)?\s*(?:code|function|block)", re.I), "ghost_text", "Complete code"),

    # Cost
    (re.compile(r"(?:how much|cost|spending|budget|usage)", re.I), "cost_summary", "Show cost summary"),

    # Memory
    (re.compile(r"(?:remember|store|save)\s+(?:this|that)", re.I), "memory_store", "Store memory"),
    (re.compile(r"(?:recall|remember|what do you know about)", re.I), "memory_recall", "Recall memory"),
]


class CommandsEngine:
    """
    Natural language command router.

    Usage:
        cmd = CommandsEngine()
        result = await cmd.execute(workspace_id, "review my PR")
    """

    async def execute(
        self,
        workspace_id: str,
        command: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Parse and execute a natural language command.

        Returns:
            command:     Detected command name
            description: Human-readable description
            result:      Command output
        """
        context = context or {}

        # Try pattern matching
        for pattern, handler_name, description in _COMMAND_PATTERNS:
            if pattern.search(command):
                try:
                    result = await self._dispatch(handler_name, workspace_id, command, context)
                    return {
                        "command": handler_name,
                        "description": description,
                        "matched": True,
                        "result": result,
                    }
                except Exception as exc:
                    logger.warning(f"Command '{handler_name}' failed: {exc}")
                    return {
                        "command": handler_name,
                        "description": description,
                        "matched": True,
                        "result": None,
                        "error": str(exc),
                    }

        # No pattern matched — fall back to ACK council
        return await self._fallback_to_council(workspace_id, command, context)

    async def _dispatch(
        self,
        handler: str,
        workspace_id: str,
        command: str,
        context: Dict,
    ) -> Any:
        """Dispatch to the appropriate service."""

        if handler == "security_scan":
            from .sentinel.council_bridge import get_sentinel_bridge
            code = context.get("code", command)
            return await get_sentinel_bridge().security_scan(workspace_id, code)

        elif handler == "risk_score":
            from .sentinel.risk_engine import RiskEngine
            engine = RiskEngine()
            return (await engine.calculate_risk_score(workspace_id)).dict()

        elif handler == "diff_review":
            from .diff_review import get_diff_review
            diff = context.get("diff", "")
            if not diff:
                return {"message": "No diff provided. Pass diff text in context."}
            return await get_diff_review().review(workspace_id, diff)

        elif handler == "debate":
            from .council_kernel.engine import get_council_engine
            from .council_kernel.types import CouncilType
            engine = get_council_engine()
            result = await engine.consult(workspace_id, command, CouncilType.PARENT)
            return result.model_dump()

        elif handler == "summarize":
            from .council_kernel.engine import get_council_engine
            from .council_kernel.types import CouncilType
            engine = get_council_engine()
            result = await engine.consult(workspace_id, command, CouncilType.DISTILLATION)
            return result.model_dump()

        elif handler == "timeline":
            from .chronos.timeline import TimelineService
            tl = TimelineService()
            return await tl.get_timeline(workspace_id, limit=20)

        elif handler == "reasoning":
            from .reasoning_chain import get_reasoning_service
            return await get_reasoning_service().get_by_workspace(workspace_id, limit=5)

        elif handler == "ghost_text":
            from .ghost_text import get_ghost_text
            prefix = context.get("prefix", "")
            suffix = context.get("suffix", "")
            language = context.get("language", "python")
            file_path = context.get("file_path", "untitled")
            return await get_ghost_text().complete(workspace_id, prefix, suffix, language, file_path)

        elif handler == "cost_summary":
            from ..db.supabase_client import get_supabase_client
            result = get_supabase_client().table("cost_tracking").select("*").eq("workspace_id", workspace_id).execute()
            rows = result.data or []
            return {
                "total_cost_usd": sum(r.get("cost_usd", 0) for r in rows),
                "total_requests": len(rows),
                "cache_hits": sum(1 for r in rows if r.get("cache_hit")),
            }

        elif handler == "memory_store":
            from .memory_engine import get_memory_engine
            content = context.get("content", command)
            return await get_memory_engine().store(workspace_id, content, "context")

        elif handler == "memory_recall":
            from .memory_engine import get_memory_engine
            return await get_memory_engine().recall(workspace_id, command)

        return {"error": f"Unknown handler: {handler}"}

    async def _fallback_to_council(
        self,
        workspace_id: str,
        command: str,
        context: Dict,
    ) -> Dict[str, Any]:
        """Fall back to ACK council for unrecognized commands."""
        try:
            from .council_kernel.engine import get_council_engine
            from .council_kernel.types import CouncilType

            engine = get_council_engine()
            result = await engine.consult(workspace_id, command, CouncilType.CHILD, context)
            return {
                "command": "council_fallback",
                "description": "Routed to ACK council (no specific command matched)",
                "matched": False,
                "result": result.model_dump(),
            }
        except Exception as exc:
            return {
                "command": "unknown",
                "description": "Could not process command",
                "matched": False,
                "result": None,
                "error": str(exc),
            }


# Singleton
_commands_engine: Optional[CommandsEngine] = None

def get_commands_engine() -> CommandsEngine:
    global _commands_engine
    if _commands_engine is None:
        _commands_engine = CommandsEngine()
    return _commands_engine
