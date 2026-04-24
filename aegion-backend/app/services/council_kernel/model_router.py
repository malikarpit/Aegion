"""
Model Router — Phase 9 (Enhanced): Universal LLM Provider Abstraction.

Complete multi-provider LLM orchestration layer.

Providers:
  - OpenAI       (o4-mini, o3, o1, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-4o, gpt-4o-mini, gpt-4-turbo)
  - Anthropic    (claude-opus-4, claude-sonnet-4, claude-sonnet-4-5, claude-haiku-3.5)
  - DeepSeek     (deepseek-chat, deepseek-coder, deepseek-reasoner)
  - Google       (gemini-2.5-pro, gemini-2.5-flash, gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash)
  - xAI/Grok     (grok-3, grok-3-mini, grok-2)
  - Mistral      (mistral-large, mistral-medium, mistral-small, codestral, pixtral-large)
  - Cohere       (command-r-plus, command-r, command-light)
  - Ollama       (any local model — free)
  - Custom       (ANY HTTP API — fully configurable request/response format)

Key design decisions:
  - Full model catalog with pricing, context windows, and capabilities
  - ModelSpec metadata lets the router make intelligent selection decisions
  - CustomProvider is format-agnostic: user defines their own request template + response JSONPath
  - Automatic retry with exponential backoff on transient failures
  - System prompt injection so council personas work correctly
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

from .types import CouncilProfile, CouncilType, ModelResponse

# ──────────────────────────────────────────────────────────────────────────────
# Model Capability & Pricing Metadata
# ──────────────────────────────────────────────────────────────────────────────

class ModelCapability(str, Enum):
    TEXT = "text"
    CODE = "code"
    REASONING = "reasoning"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    JSON_MODE = "json_mode"
    LONG_CONTEXT = "long_context"       # >100k tokens
    EXTENDED_THINKING = "extended_thinking"


@dataclass(frozen=True)
class ModelSpec:
    """Full specification for a model — pricing, limits, capabilities."""
    model_id: str
    provider: str
    display_name: str
    context_window: int                            # Max tokens (input + output)
    max_output_tokens: int                          # Max output tokens
    input_price_per_m: float                        # USD per 1M input tokens
    output_price_per_m: float                       # USD per 1M output tokens
    capabilities: Tuple[ModelCapability, ...] = ()  # What the model can do
    tier: int = 2                                   # Quality tier 1=budget 2=standard 3=frontier 4=reasoning
    default_temperature: float = 0.7
    supports_streaming: bool = True
    deprecated: bool = False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Complete Model Catalogs (prices as of 2026-04)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OPENAI_MODELS: Dict[str, ModelSpec] = {
    # ── Reasoning models ──
    "o4-mini": ModelSpec(
        "o4-mini", "openai", "OpenAI o4-mini",
        200_000, 100_000, 1.10, 4.40,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.EXTENDED_THINKING),
        tier=4),
    "o3": ModelSpec(
        "o3", "openai", "OpenAI o3",
        200_000, 100_000, 2.00, 8.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.EXTENDED_THINKING),
        tier=4),
    "o3-mini": ModelSpec(
        "o3-mini", "openai", "OpenAI o3-mini",
        200_000, 100_000, 1.10, 4.40,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING, ModelCapability.JSON_MODE,
         ModelCapability.EXTENDED_THINKING),
        tier=4),
    "o1": ModelSpec(
        "o1", "openai", "OpenAI o1",
        200_000, 100_000, 15.00, 60.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.EXTENDED_THINKING),
        tier=4),
    "o1-mini": ModelSpec(
        "o1-mini", "openai", "OpenAI o1-mini",
        128_000, 65_536, 3.00, 12.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING, ModelCapability.EXTENDED_THINKING),
        tier=4),
    # ── GPT-4.1 family ──
    "gpt-4.1": ModelSpec(
        "gpt-4.1", "openai", "GPT-4.1",
        1_047_576, 32_768, 2.00, 8.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.LONG_CONTEXT),
        tier=3),
    "gpt-4.1-mini": ModelSpec(
        "gpt-4.1-mini", "openai", "GPT-4.1 Mini",
        1_047_576, 32_768, 0.40, 1.60,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.LONG_CONTEXT),
        tier=2),
    "gpt-4.1-nano": ModelSpec(
        "gpt-4.1-nano", "openai", "GPT-4.1 Nano",
        1_047_576, 32_768, 0.10, 0.40,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.LONG_CONTEXT),
        tier=1),
    # ── GPT-4o family ──
    "gpt-4o": ModelSpec(
        "gpt-4o", "openai", "GPT-4o",
        128_000, 16_384, 2.50, 10.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=3),
    "gpt-4o-mini": ModelSpec(
        "gpt-4o-mini", "openai", "GPT-4o Mini",
        128_000, 16_384, 0.15, 0.60,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=1),
    # ── Legacy (still available) ──
    "gpt-4-turbo": ModelSpec(
        "gpt-4-turbo", "openai", "GPT-4 Turbo",
        128_000, 4_096, 10.00, 30.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=3),
}

ANTHROPIC_MODELS: Dict[str, ModelSpec] = {
    "claude-opus-4-20250514": ModelSpec(
        "claude-opus-4-20250514", "anthropic", "Claude Opus 4",
        200_000, 32_000, 15.00, 75.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.EXTENDED_THINKING),
        tier=4),
    "claude-sonnet-4-20250514": ModelSpec(
        "claude-sonnet-4-20250514", "anthropic", "Claude Sonnet 4",
        200_000, 16_000, 3.00, 15.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.EXTENDED_THINKING),
        tier=3),
    "claude-sonnet-4-5-20241022": ModelSpec(
        "claude-sonnet-4-5-20241022", "anthropic", "Claude Sonnet 4.5",
        200_000, 8_192, 3.00, 15.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.EXTENDED_THINKING),
        tier=3),
    "claude-haiku-3-5-20241022": ModelSpec(
        "claude-haiku-3-5-20241022", "anthropic", "Claude 3.5 Haiku",
        200_000, 8_192, 0.80, 4.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=2),
}

DEEPSEEK_MODELS: Dict[str, ModelSpec] = {
    "deepseek-chat": ModelSpec(
        "deepseek-chat", "deepseek", "DeepSeek V3",
        128_000, 8_192, 0.27, 1.10,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=2),
    "deepseek-reasoner": ModelSpec(
        "deepseek-reasoner", "deepseek", "DeepSeek R1",
        128_000, 8_192, 0.55, 2.19,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING, ModelCapability.EXTENDED_THINKING),
        tier=3),
}

GOOGLE_MODELS: Dict[str, ModelSpec] = {
    "gemini-2.5-pro-preview-06-05": ModelSpec(
        "gemini-2.5-pro-preview-06-05", "google", "Gemini 2.5 Pro",
        1_048_576, 65_536, 1.25, 10.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.LONG_CONTEXT,
         ModelCapability.EXTENDED_THINKING),
        tier=4),
    "gemini-2.5-flash-preview-05-20": ModelSpec(
        "gemini-2.5-flash-preview-05-20", "google", "Gemini 2.5 Flash",
        1_048_576, 65_536, 0.15, 0.60,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.LONG_CONTEXT,
         ModelCapability.EXTENDED_THINKING),
        tier=2),
    "gemini-2.0-flash": ModelSpec(
        "gemini-2.0-flash", "google", "Gemini 2.0 Flash",
        1_048_576, 8_192, 0.10, 0.40,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.LONG_CONTEXT),
        tier=1),
    "gemini-1.5-pro": ModelSpec(
        "gemini-1.5-pro", "google", "Gemini 1.5 Pro",
        2_000_000, 8_192, 1.25, 5.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.LONG_CONTEXT),
        tier=3),
    "gemini-1.5-flash": ModelSpec(
        "gemini-1.5-flash", "google", "Gemini 1.5 Flash",
        1_000_000, 8_192, 0.075, 0.30,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.LONG_CONTEXT),
        tier=1),
}

XAI_MODELS: Dict[str, ModelSpec] = {
    "grok-3": ModelSpec(
        "grok-3", "xai", "Grok 3",
        131_072, 16_384, 3.00, 15.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=3),
    "grok-3-mini": ModelSpec(
        "grok-3-mini", "xai", "Grok 3 Mini",
        131_072, 16_384, 0.30, 0.50,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE, ModelCapability.EXTENDED_THINKING),
        tier=2),
    "grok-2": ModelSpec(
        "grok-2", "xai", "Grok 2",
        131_072, 16_384, 2.00, 10.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=3),
}

MISTRAL_MODELS: Dict[str, ModelSpec] = {
    "mistral-large-latest": ModelSpec(
        "mistral-large-latest", "mistral", "Mistral Large",
        128_000, 8_192, 2.00, 6.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=3),
    "mistral-medium-latest": ModelSpec(
        "mistral-medium-latest", "mistral", "Mistral Medium",
        128_000, 8_192, 0.40, 2.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=2),
    "mistral-small-latest": ModelSpec(
        "mistral-small-latest", "mistral", "Mistral Small",
        128_000, 8_192, 0.10, 0.30,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=1),
    "codestral-latest": ModelSpec(
        "codestral-latest", "mistral", "Codestral",
        256_000, 8_192, 0.30, 0.90,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=2),
    "pixtral-large-latest": ModelSpec(
        "pixtral-large-latest", "mistral", "Pixtral Large",
        128_000, 8_192, 2.00, 6.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.VISION,
         ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=3),
}

COHERE_MODELS: Dict[str, ModelSpec] = {
    "command-r-plus": ModelSpec(
        "command-r-plus", "cohere", "Command R+",
        128_000, 4_096, 2.50, 10.00,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=3),
    "command-r": ModelSpec(
        "command-r", "cohere", "Command R",
        128_000, 4_096, 0.15, 0.60,
        (ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE),
        tier=2),
    "command-light": ModelSpec(
        "command-light", "cohere", "Command Light",
        4_096, 4_096, 0.30, 0.60,
        (ModelCapability.TEXT,),
        tier=1),
}

# Unified catalog — all known models
MODEL_CATALOG: Dict[str, ModelSpec] = {
    **OPENAI_MODELS, **ANTHROPIC_MODELS, **DEEPSEEK_MODELS,
    **GOOGLE_MODELS, **XAI_MODELS, **MISTRAL_MODELS, **COHERE_MODELS,
}


def _load_custom_models() -> Dict[str, ModelSpec]:
    """
    Load user-defined models from model_registry.json (W1.2).

    JSON file is optional — if missing, only built-in catalog is used.
    Each entry: { "model_id", "provider", "display_name", "context_window",
                  "max_output_tokens", "input_price_per_m", "output_price_per_m",
                  "capabilities": [str], "tier": int }
    """
    import json as _json
    registry_path = os.path.join(os.path.dirname(__file__), "model_registry.json")
    if not os.path.isfile(registry_path):
        return {}
    try:
        with open(registry_path, "r") as f:
            entries = _json.load(f)
        custom: Dict[str, ModelSpec] = {}
        for entry in entries:
            caps = tuple(ModelCapability(c) for c in entry.get("capabilities", ["text"]))
            custom[entry["model_id"]] = ModelSpec(
                model_id=entry["model_id"],
                provider=entry["provider"],
                display_name=entry.get("display_name", entry["model_id"]),
                context_window=entry.get("context_window", 128_000),
                max_output_tokens=entry.get("max_output_tokens", 4_096),
                input_price_per_m=entry.get("input_price_per_m", 1.0),
                output_price_per_m=entry.get("output_price_per_m", 3.0),
                capabilities=caps,
                tier=entry.get("tier", 2),
            )
        return custom
    except Exception as exc:
        logger.warning(f"Failed to load model_registry.json: {exc}")
        return {}


# Merge custom models (JSON overrides built-in on conflict)
MODEL_CATALOG.update(_load_custom_models())

# ──────────────────────────────────────────────────────────────────────────────
# Provider ABC
# ──────────────────────────────────────────────────────────────────────────────

MAX_RETRIES = 2
RETRY_BASE_DELAY = 0.5  # seconds


class LLMProvider(ABC):
    """Abstract base for all LLM providers."""

    provider_name: str = "unknown"
    models: Dict[str, ModelSpec] = {}

    @abstractmethod
    async def _raw_generate(self, prompt: str, model: str, system_prompt: Optional[str] = None, **kwargs) -> ModelResponse:
        """Provider-specific generation logic. Subclasses implement this."""

    async def generate(self, prompt: str, model: str, system_prompt: Optional[str] = None, **kwargs) -> ModelResponse:
        """
        Call the LLM with automatic retry on transient failures.

        Retries on 429 (rate limit), 500, 502, 503, 504.
        """
        last_exc = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return await self._raw_generate(prompt, model, system_prompt, **kwargs)
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                raise
            except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                raise
        raise last_exc  # type: ignore

    def list_models(self) -> List[ModelSpec]:
        """Return all models this provider supports."""
        return list(self.models.values())

    def _calc_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        spec = self.models.get(model)
        if spec:
            return (tokens_in * spec.input_price_per_m + tokens_out * spec.output_price_per_m) / 1_000_000
        return 0.0

    def _tier_confidence(self, model: str) -> float:
        """Base confidence from model tier — frontier models get higher base confidence."""
        spec = self.models.get(model)
        if not spec:
            return 0.70
        return {1: 0.70, 2: 0.78, 3: 0.85, 4: 0.92}.get(spec.tier, 0.75)


# ──────────────────────────────────────────────────────────────────────────────
# Concrete Providers
# ──────────────────────────────────────────────────────────────────────────────

class OpenAIProvider(LLMProvider):
    provider_name = "openai"
    models = OPENAI_MODELS
    BASE_URL = "https://api.openai.com/v1"

    def __init__(self, api_key: str, base_url: Optional[str] = None) -> None:
        self.api_key = api_key
        if base_url:
            self.BASE_URL = base_url.rstrip("/")

    async def _raw_generate(self, prompt: str, model: str = "gpt-4.1-mini", system_prompt: Optional[str] = None, **kwargs) -> ModelResponse:
        start = time.monotonic()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
        }
        if kwargs.get("max_tokens"):
            body["max_tokens"] = kwargs["max_tokens"]
        if kwargs.get("json_mode"):
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        return ModelResponse(
            model=model, provider=self.provider_name,
            response=data["choices"][0]["message"]["content"],
            confidence=self._tier_confidence(model),
            tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=self._calc_cost(model, tokens_in, tokens_out),
            latency_ms=int((time.monotonic() - start) * 1000),
        )


class AnthropicProvider(LLMProvider):
    provider_name = "anthropic"
    models = ANTHROPIC_MODELS
    BASE_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def _raw_generate(self, prompt: str, model: str = "claude-sonnet-4-20250514", system_prompt: Optional[str] = None, **kwargs) -> ModelResponse:
        start = time.monotonic()
        body: Dict[str, Any] = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 8192),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            body["system"] = system_prompt
        if kwargs.get("temperature") is not None:
            body["temperature"] = kwargs["temperature"]

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                self.BASE_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usage", {})
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)

        return ModelResponse(
            model=model, provider=self.provider_name,
            response=data["content"][0]["text"],
            confidence=self._tier_confidence(model),
            tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=self._calc_cost(model, tokens_in, tokens_out),
            latency_ms=int((time.monotonic() - start) * 1000),
        )


class DeepSeekProvider(LLMProvider):
    provider_name = "deepseek"
    models = DEEPSEEK_MODELS
    BASE_URL = "https://api.deepseek.com/v1/chat/completions"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def _raw_generate(self, prompt: str, model: str = "deepseek-chat", system_prompt: Optional[str] = None, **kwargs) -> ModelResponse:
        start = time.monotonic()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": messages,
                      "temperature": kwargs.get("temperature", 0.7)},
            )
            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        return ModelResponse(
            model=model, provider=self.provider_name,
            response=data["choices"][0]["message"]["content"],
            confidence=self._tier_confidence(model),
            tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=self._calc_cost(model, tokens_in, tokens_out),
            latency_ms=int((time.monotonic() - start) * 1000),
        )


class GeminiProvider(LLMProvider):
    provider_name = "google"
    models = GOOGLE_MODELS
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def _raw_generate(self, prompt: str, model: str = "gemini-2.5-flash-preview-05-20", system_prompt: Optional[str] = None, **kwargs) -> ModelResponse:
        start = time.monotonic()
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"[System Instructions]\n{system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will follow these instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/{model}:generateContent",
                params={"key": self.api_key},
                json={"contents": contents},
            )
            resp.raise_for_status()
            data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        tokens_in = usage.get("promptTokenCount", 0)
        tokens_out = usage.get("candidatesTokenCount", 0)

        return ModelResponse(
            model=model, provider=self.provider_name,
            response=text,
            confidence=self._tier_confidence(model),
            tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=self._calc_cost(model, tokens_in, tokens_out),
            latency_ms=int((time.monotonic() - start) * 1000),
        )


class XAIProvider(LLMProvider):
    """xAI Grok family — OpenAI-compatible API."""
    provider_name = "xai"
    models = XAI_MODELS
    BASE_URL = "https://api.x.ai/v1/chat/completions"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def _raw_generate(self, prompt: str, model: str = "grok-3-mini", system_prompt: Optional[str] = None, **kwargs) -> ModelResponse:
        start = time.monotonic()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": messages,
                      "temperature": kwargs.get("temperature", 0.7)},
            )
            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        return ModelResponse(
            model=model, provider=self.provider_name,
            response=data["choices"][0]["message"]["content"],
            confidence=self._tier_confidence(model),
            tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=self._calc_cost(model, tokens_in, tokens_out),
            latency_ms=int((time.monotonic() - start) * 1000),
        )


class MistralProvider(LLMProvider):
    provider_name = "mistral"
    models = MISTRAL_MODELS
    BASE_URL = "https://api.mistral.ai/v1/chat/completions"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def _raw_generate(self, prompt: str, model: str = "mistral-small-latest", system_prompt: Optional[str] = None, **kwargs) -> ModelResponse:
        start = time.monotonic()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": messages,
                      "temperature": kwargs.get("temperature", 0.7)},
            )
            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        return ModelResponse(
            model=model, provider=self.provider_name,
            response=data["choices"][0]["message"]["content"],
            confidence=self._tier_confidence(model),
            tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=self._calc_cost(model, tokens_in, tokens_out),
            latency_ms=int((time.monotonic() - start) * 1000),
        )


class CohereProvider(LLMProvider):
    provider_name = "cohere"
    models = COHERE_MODELS
    BASE_URL = "https://api.cohere.com/v2/chat"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def _raw_generate(self, prompt: str, model: str = "command-r", system_prompt: Optional[str] = None, **kwargs) -> ModelResponse:
        start = time.monotonic()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": messages},
            )
            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usage", {}).get("tokens", {})
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)
        text = data.get("message", {}).get("content", [{}])[0].get("text", "")

        return ModelResponse(
            model=model, provider=self.provider_name,
            response=text,
            confidence=self._tier_confidence(model),
            tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=self._calc_cost(model, tokens_in, tokens_out),
            latency_ms=int((time.monotonic() - start) * 1000),
        )


class OllamaProvider(LLMProvider):
    """Ollama local model runner — free, supports any GGUF / safetensors model."""
    provider_name = "ollama"
    models = {}  # Dynamic — depends on what the user has pulled

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")

    async def _raw_generate(self, prompt: str, model: str = "llama3.1:8b", system_prompt: Optional[str] = None, **kwargs) -> ModelResponse:
        start = time.monotonic()
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"[System: {system_prompt}]\n\n{prompt}"

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": full_prompt, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()

        return ModelResponse(
            model=model, provider=self.provider_name,
            response=data.get("response", ""),
            confidence=0.70,
            tokens_in=data.get("prompt_eval_count", 0),
            tokens_out=data.get("eval_count", 0),
            cost_usd=0.0,
            latency_ms=int((time.monotonic() - start) * 1000),
        )

    def list_models(self) -> List[ModelSpec]:
        """Ollama models are dynamic — return empty. Use /api/tags at runtime."""
        return []


# ──────────────────────────────────────────────────────────────────────────────
# Universal Custom Provider — ANY HTTP API
# ──────────────────────────────────────────────────────────────────────────────

class APIFormat(str, Enum):
    """Predefined API format templates for common patterns."""
    OPENAI = "openai"       # OpenAI-compatible (LM Studio, vLLM, Together, Fireworks, etc.)
    ANTHROPIC = "anthropic" # Anthropic Messages API format
    RAW = "raw"             # Fully user-defined — you specify everything


@dataclass
class CustomProviderConfig:
    """
    Fully flexible provider configuration.

    For OPENAI/ANTHROPIC formats, only base_url and api_key are needed.
    For RAW format, the user defines the entire request/response mapping.

    Example (RAW format for a custom REST API):
        CustomProviderConfig(
            name="my-internal-llm",
            base_url="https://internal.corp.com/api/v1/generate",
            api_key="sk-internal-...",
            api_format=APIFormat.RAW,
            request_template={
                "method": "POST",
                "headers": {"X-Api-Key": "{api_key}"},
                "body": {"input": "{prompt}", "model_name": "{model}", "params": {"temp": 0.7}}
            },
            response_path="output.generated_text",
            token_count_paths={"input": "usage.input_token_count", "output": "usage.output_token_count"},
        )
    """
    name: str = "custom"
    base_url: str = ""
    api_key: str = ""
    api_format: APIFormat = APIFormat.OPENAI
    default_model: str = "default"
    cost_per_m_input: float = 0.0       # User-specified cost for tracking
    cost_per_m_output: float = 0.0

    # ── RAW format configuration ──
    # request_template: JSON-serializable dict. Placeholders: {prompt}, {model}, {api_key}, {system_prompt}
    request_template: Optional[Dict[str, Any]] = None
    # JSONPath-like dot-notation path to extract the response text from the API JSON
    response_path: str = "choices.0.message.content"
    # Paths to extract token counts (optional)
    token_count_paths: Optional[Dict[str, str]] = None
    # Extra headers to send
    extra_headers: Optional[Dict[str, str]] = None
    # HTTP method override
    http_method: str = "POST"
    # Timeout in seconds
    timeout: float = 120.0


def _resolve_json_path(data: Any, path: str) -> Any:
    """Resolve a dot-notation path like 'choices.0.message.content' against a JSON object."""
    parts = path.split(".")
    current = data
    for part in parts:
        if current is None:
            return None
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (IndexError, ValueError):
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _interpolate(template: Any, variables: Dict[str, str]) -> Any:
    """Recursively replace {placeholders} in a template dict/str with variable values."""
    if isinstance(template, str):
        for key, val in variables.items():
            template = template.replace(f"{{{key}}}", val)
        return template
    if isinstance(template, dict):
        return {k: _interpolate(v, variables) for k, v in template.items()}
    if isinstance(template, list):
        return [_interpolate(item, variables) for item in template]
    return template


class CustomProvider(LLMProvider):
    """
    Universal custom provider — works with ANY HTTP API.

    Three modes:
    1. OPENAI format — just provide base_url + api_key. Works with LM Studio, vLLM, Together AI,
       Fireworks, Groq, Perplexity, Azure OpenAI, or any OpenAI-compatible endpoint.

    2. ANTHROPIC format — for Anthropic-compatible proxy endpoints (e.g. AWS Bedrock).

    3. RAW format — fully user-defined. The user specifies:
       - request_template: The full request body with {prompt}/{model}/{api_key} placeholders
       - response_path: Dot-notation JSONPath to where the response text lives
       - token_count_paths: Optional paths to extract token counts

       This allows connecting to absolutely ANY REST API that accepts text and returns text.
    """

    provider_name = "custom"
    models = {}

    def __init__(self, config: CustomProviderConfig) -> None:
        self.config = config
        self.provider_name = config.name

    async def _raw_generate(self, prompt: str, model: str = "", system_prompt: Optional[str] = None, **kwargs) -> ModelResponse:
        model = model or self.config.default_model
        start = time.monotonic()

        if self.config.api_format == APIFormat.OPENAI:
            data = await self._openai_format(prompt, model, system_prompt, **kwargs)
        elif self.config.api_format == APIFormat.ANTHROPIC:
            data = await self._anthropic_format(prompt, model, system_prompt, **kwargs)
        elif self.config.api_format == APIFormat.RAW:
            data = await self._raw_format(prompt, model, system_prompt, **kwargs)
        else:
            raise ValueError(f"Unknown API format: {self.config.api_format}")

        # Extract response text
        response_text = str(_resolve_json_path(data, self.config.response_path) or "")

        # Extract tokens
        tokens_in = 0
        tokens_out = 0
        if self.config.token_count_paths:
            raw_in = _resolve_json_path(data, self.config.token_count_paths.get("input", ""))
            raw_out = _resolve_json_path(data, self.config.token_count_paths.get("output", ""))
            tokens_in = int(raw_in) if raw_in else 0
            tokens_out = int(raw_out) if raw_out else 0

        cost = (tokens_in * self.config.cost_per_m_input + tokens_out * self.config.cost_per_m_output) / 1_000_000

        return ModelResponse(
            model=model, provider=self.provider_name,
            response=response_text,
            confidence=0.75,
            tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=cost,
            latency_ms=int((time.monotonic() - start) * 1000),
        )

    async def _openai_format(self, prompt: str, model: str, system_prompt: Optional[str], **kwargs) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        if self.config.extra_headers:
            headers.update(self.config.extra_headers)

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            resp = await client.post(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages,
                      "temperature": kwargs.get("temperature", 0.7)},
            )
            resp.raise_for_status()
            return resp.json()

    async def _anthropic_format(self, prompt: str, model: str, system_prompt: Optional[str], **kwargs) -> dict:
        body: dict = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 8192),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            body["system"] = system_prompt

        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        if self.config.extra_headers:
            headers.update(self.config.extra_headers)

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            resp = await client.post(
                self.config.base_url.rstrip("/"),
                headers=headers, json=body,
            )
            resp.raise_for_status()
            return resp.json()

    async def _raw_format(self, prompt: str, model: str, system_prompt: Optional[str], **kwargs) -> dict:
        """Fully user-defined request format."""
        if not self.config.request_template:
            raise ValueError("RAW format requires request_template in config")

        variables = {
            "prompt": prompt,
            "model": model,
            "api_key": self.config.api_key,
            "system_prompt": system_prompt or "",
        }

        template = self.config.request_template
        headers = _interpolate(template.get("headers", {}), variables)
        body = _interpolate(template.get("body", {}), variables)

        if self.config.extra_headers:
            headers.update(self.config.extra_headers)

        method = template.get("method", self.config.http_method).upper()

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            if method == "POST":
                resp = await client.post(self.config.base_url, headers=headers, json=body)
            elif method == "GET":
                resp = await client.get(self.config.base_url, headers=headers, params=body)
            elif method == "PUT":
                resp = await client.put(self.config.base_url, headers=headers, json=body)
            else:
                resp = await client.post(self.config.base_url, headers=headers, json=body)

            resp.raise_for_status()
            return resp.json()


# ──────────────────────────────────────────────────────────────────────────────
# ModelRouter — Intelligent model selection
# ──────────────────────────────────────────────────────────────────────────────

# Default model per provider tier (cheapest viable model)
_DEFAULT_MODELS: Dict[str, str] = {
    "deepseek":  "deepseek-chat",
    "google":    "gemini-2.5-flash-preview-05-20",
    "openai":    "gpt-4.1-mini",
    "anthropic": "claude-haiku-3-5-20241022",
    "xai":       "grok-3-mini",
    "mistral":   "mistral-small-latest",
    "cohere":    "command-r",
    "ollama":    "llama3.1:8b",
    "custom":    "default",
}

# Backward compatible alias
_MODEL_MAP = _DEFAULT_MODELS

_PROFILE_SIZES: Dict[str, int] = {
    "trivial":  1,
    "simple":   2,
    "moderate": 3,
    "complex":  4,
    "critical": 5,
}

# Priority order for model selection — cheapest-first for cost optimization
_PRIORITY: List[str] = ["deepseek", "ollama", "google", "mistral", "xai", "openai", "cohere", "anthropic", "custom"]

# Models to use for high-stakes (CRITICAL profile) — frontier models from each provider
_FRONTIER_MODELS: Dict[str, str] = {
    "openai":    "o4-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "google":    "gemini-2.5-pro-preview-06-05",
    "deepseek":  "deepseek-reasoner",
    "xai":       "grok-3",
    "mistral":   "mistral-large-latest",
    "cohere":    "command-r-plus",
}


class ModelRouter:
    """
    Intelligent multi-provider LLM router.

    Features:
      - Dynamic provider registration from user API keys
      - Model selection based on council profile (cost-optimized or frontier)
      - Capability-based filtering (e.g. "only models with REASONING")
      - Full model catalog with pricing metadata
      - Automatic retry with exponential backoff (built into LLMProvider)
    """

    def __init__(self) -> None:
        self.providers: Dict[str, LLMProvider] = {}

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        self.providers[name] = provider

    async def configure_from_user_keys(self, user_api_keys: Dict[str, Any]) -> None:
        """
        Register providers from user-supplied API keys.

        Expected keys: openai_key, anthropic_key, deepseek_key, google_key,
                       xai_key, mistral_key, cohere_key, ollama_url,
                       custom_providers (list of CustomProviderConfig dicts)
        """
        if user_api_keys.get("openai_key"):
            self.register_provider("openai", OpenAIProvider(
                user_api_keys["openai_key"],
                user_api_keys.get("openai_base_url"),
            ))
        if user_api_keys.get("anthropic_key"):
            self.register_provider("anthropic", AnthropicProvider(user_api_keys["anthropic_key"]))
        if user_api_keys.get("deepseek_key"):
            self.register_provider("deepseek", DeepSeekProvider(user_api_keys["deepseek_key"]))
        if user_api_keys.get("google_key"):
            self.register_provider("google", GeminiProvider(user_api_keys["google_key"]))
        if user_api_keys.get("xai_key"):
            self.register_provider("xai", XAIProvider(user_api_keys["xai_key"]))
        if user_api_keys.get("mistral_key"):
            self.register_provider("mistral", MistralProvider(user_api_keys["mistral_key"]))
        if user_api_keys.get("cohere_key"):
            self.register_provider("cohere", CohereProvider(user_api_keys["cohere_key"]))
        if user_api_keys.get("ollama_url"):
            self.register_provider("ollama", OllamaProvider(user_api_keys["ollama_url"]))

        # Register any number of custom providers
        for custom_cfg in user_api_keys.get("custom_providers", []):
            if isinstance(custom_cfg, dict):
                cfg = CustomProviderConfig(**custom_cfg)
            elif isinstance(custom_cfg, CustomProviderConfig):
                cfg = custom_cfg
            else:
                continue
            self.register_provider(cfg.name, CustomProvider(cfg))

        # Legacy single custom provider support
        if user_api_keys.get("custom_url"):
            cfg = CustomProviderConfig(
                name="custom",
                base_url=user_api_keys["custom_url"],
                api_key=user_api_keys.get("custom_key", ""),
                api_format=APIFormat(user_api_keys.get("custom_format", "openai")),
                default_model=user_api_keys.get("custom_model", "default"),
                response_path=user_api_keys.get("custom_response_path", "choices.0.message.content"),
            )
            self.register_provider("custom", CustomProvider(cfg))

    async def configure_single_key(self, api_key: str, provider_hint: Optional[str] = None) -> str:
        """
        Phase 98: Single-key onboarding (Mono-Council).

        Detects the provider from the key format and registers it as the sole provider.
        The full cascade, debate, and peer-review systems work with just one provider.

        Key detection heuristics:
          - sk-ant-*         → Anthropic
          - sk-* / sess-*    → OpenAI
          - AI*              → Google
          - xai-*            → xAI
          - dsk-*            → DeepSeek
          - http*            → Ollama (URL, not key)
          - *                → Tries OpenAI-compatible (most common)

        Args:
            api_key: The single API key or URL.
            provider_hint: Optional explicit provider name to skip detection.

        Returns:
            The detected/registered provider name.
        """
        # Explicit hint takes priority
        if provider_hint:
            name = provider_hint.lower()
        else:
            # Auto-detect from key format
            key = api_key.strip()
            if key.startswith("sk-ant-"):
                name = "anthropic"
            elif key.startswith("sk-") or key.startswith("sess-"):
                name = "openai"
            elif key.startswith("AI"):
                name = "google"
            elif key.startswith("xai-"):
                name = "xai"
            elif key.startswith("dsk-"):
                name = "deepseek"
            elif key.startswith("http"):
                name = "ollama"
            else:
                # Default to OpenAI-compatible — most custom endpoints use this format
                name = "openai"

        # Register the detected provider
        provider_map = {
            "openai": lambda k: OpenAIProvider(k),
            "anthropic": lambda k: AnthropicProvider(k),
            "deepseek": lambda k: DeepSeekProvider(k),
            "google": lambda k: GeminiProvider(k),
            "xai": lambda k: XAIProvider(k),
            "mistral": lambda k: MistralProvider(k),
            "cohere": lambda k: CohereProvider(k),
            "ollama": lambda k: OllamaProvider(k),
        }

        factory = provider_map.get(name)
        if factory:
            self.register_provider(name, factory(api_key))
        else:
            # Unknown provider — try as OpenAI-compatible custom endpoint
            self.register_provider(name, OpenAIProvider(api_key))

        logger.info(f"Phase 98: Mono-council configured with single provider: {name}")
        return name

    async def select_models(
        self,
        workspace_id: str,
        council_type: CouncilType,
        profile: CouncilProfile,
        required_capabilities: Optional[List[ModelCapability]] = None,
    ) -> List[Tuple[str, str]]:
        """
        Select (provider_name, model_id) tuples for a council run.

        For CRITICAL profile, selects frontier (best) models.
        For other profiles, selects cheapest-first.
        Optionally filters by required capabilities.
        """
        available = set(self.providers.keys())
        if not available:
            raise RuntimeError("No LLM providers configured. Call configure_from_user_keys() first.")

        count = _PROFILE_SIZES.get(profile.value, 2)
        use_frontier = profile == CouncilProfile.CRITICAL or council_type == CouncilType.PARENT

        selected: List[Tuple[str, str]] = []
        for pname in _PRIORITY:
            if pname not in available or len(selected) >= count:
                continue

            if use_frontier:
                model_id = _FRONTIER_MODELS.get(pname, _DEFAULT_MODELS.get(pname, "default"))
            else:
                model_id = _DEFAULT_MODELS.get(pname, "default")

            # Capability filter
            if required_capabilities:
                spec = MODEL_CATALOG.get(model_id)
                if spec and not all(cap in spec.capabilities for cap in required_capabilities):
                    continue

            selected.append((pname, model_id))

        return selected

    async def call(
        self,
        provider_name: str,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """Delegate a single call to the named provider."""
        provider = self.providers.get(provider_name)
        if provider is None:
            raise RuntimeError(f"Provider '{provider_name}' not registered")
        return await provider.generate(prompt, model, system_prompt=system_prompt, **kwargs)

    def get_model_spec(self, model_id: str) -> Optional[ModelSpec]:
        """Look up a model's specs from the catalog."""
        return MODEL_CATALOG.get(model_id)

    def list_available_models(self) -> Dict[str, List[ModelSpec]]:
        """Return all models available from registered providers."""
        result: Dict[str, List[ModelSpec]] = {}
        for name, provider in self.providers.items():
            result[name] = provider.list_models()
        return result

    def estimate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for a given model and token counts."""
        spec = MODEL_CATALOG.get(model_id)
        if not spec:
            return 0.0
        return (input_tokens * spec.input_price_per_m + output_tokens * spec.output_price_per_m) / 1_000_000
