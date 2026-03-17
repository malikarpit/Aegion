"""
Model Router — multi-provider LLM abstraction.

Initial version: OpenAI-only support via httpx.
Multi-provider cascade (Anthropic, Google) will be added later.
"""

import httpx
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from ...core.logging import logger


@dataclass
class ModelSpec:
    """Specification for an LLM model."""
    model_id: str
    provider: str
    display_name: str
    context_window: int = 128000
    max_output_tokens: int = 4096
    input_price_per_m: float = 0.0
    output_price_per_m: float = 0.0


@dataclass
class ModelResponse:
    """Response from an LLM call."""
    response: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    model_used: str = ""
    provider_used: str = ""


class ModelRouter:
    """Routes LLM requests to configured providers."""

    def __init__(self):
        self.providers: Dict[str, any] = {}

    async def call(self, provider: str, model: str, prompt: str,
                   json_mode: bool = False) -> ModelResponse:
        """Call an LLM model via the specified provider."""
        if provider == "openai" and "openai" in self.providers:
            return await self._call_openai(model, prompt, json_mode)

        # Fallback mock
        logger.warning(f"No provider configured for {provider}, using mock")
        return ModelResponse(
            response='{"result": "mock response"}',
            model_used="mock",
            provider_used="none"
        )

    async def _call_openai(self, model: str, prompt: str,
                            json_mode: bool = False) -> ModelResponse:
        """Call OpenAI API directly via httpx."""
        api_key = self.providers.get("openai", {}).get("api_key", "")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return ModelResponse(
                response=content,
                tokens_in=usage.get("prompt_tokens", 0),
                tokens_out=usage.get("completion_tokens", 0),
                model_used=model,
                provider_used="openai",
            )
