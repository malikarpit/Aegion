"""
Aegion LangGraph AI Orchestrator Adapter.

Implements AIOrchestrationPort using LangGraph logic.
Initial version — direct LLM call without governed debate pipeline.
"""

from typing import Dict, Any, List, AsyncIterator, Optional
import asyncio
import json

from ...ports.ai_orchestrator import (
    AIOrchestrationPort,
    AgentRegistryPort,
    AgentRole,
    AgentCapability,
    AIProposal,
    CouncilDebateResult,
)
from ...core.logging import logger
from ...core.config import settings


def _get_genai_model(model_name: str, temperature: float):
    """Lazy-init a Gemini model. Returns None if API key not configured."""
    try:
        import google.generativeai as genai
        api_key = getattr(settings, 'gemini_api_key', None) or __import__('os').environ.get('GEMINI_API_KEY')
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(
            model_name=model_name,
            generation_config={"temperature": temperature}
        )
    except Exception:
        return None


class LangGraphOrchestrator(AIOrchestrationPort):
    """LangGraph AI orchestrator — initial implementation."""

    async def invoke_child_council(
        self, prompt: str, context: Dict[str, Any], session_id: str
    ) -> AsyncIterator[str]:
        """Invoke Child AI Council. Streams response tokens."""
        model = _get_genai_model("gemini-2.0-flash", 0.7)
        response_text = None

        if model:
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: model.generate_content(prompt)
                )
                response_text = response.text
            except Exception as e:
                logger.warning(f"LLM call failed: {e}")

        if not response_text:
            response_text = json.dumps({
                "claim": f"[DEGRADED] Heuristic suggestion for: {prompt[:80]}",
                "reasoning": "LLM unavailable — this is a heuristic placeholder.",
                "degraded": True,
            }, indent=2)

        for char in response_text:
            yield char
            await asyncio.sleep(0.005)
