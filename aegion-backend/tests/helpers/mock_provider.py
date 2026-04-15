"""
Mock LLM Provider for testing.

Provides a configurable mock that implements the LLMProvider interface
for test isolation — no real API calls needed.
"""

from typing import Dict, List, Optional, Any
import time

from app.services.council_kernel.model_router import LLMProvider, ModelSpec, ModelCapability
from app.services.council_kernel.types import ModelResponse


class MockLLMProvider(LLMProvider):
    """
    Configurable mock LLM provider for testing.

    Usage:
        provider = MockLLMProvider(
            name="mock_openai",
            responses={"default": "This is a mock response."},
            confidence=0.85,
        )
        # Register with router:
        router.register_provider("openai", provider)
    """

    def __init__(
        self,
        name: str = "mock",
        responses: Optional[Dict[str, str]] = None,
        confidence: float = 0.85,
        cost_per_call: float = 0.001,
        tokens_in: int = 100,
        tokens_out: int = 150,
        latency_ms: int = 50,
        fail_on: Optional[List[str]] = None,
        tier: int = 2,
    ) -> None:
        self.provider_name = name
        self._responses = responses or {
            "default": (
                "This is a well-structured answer with detailed reasoning. "
                "Because the architecture follows clean separation of concerns, "
                "therefore the approach is recommended. Specifically, the database "
                "layer uses connection pooling for optimal performance. "
                "Step 1: Configure the connection pool. "
                "Step 2: Set max connections to 20. "
                "For example, use SQLAlchemy's QueuePool with overflow settings."
            )
        }
        self._confidence = confidence
        self._cost_per_call = cost_per_call
        self._tokens_in = tokens_in
        self._tokens_out = tokens_out
        self._latency_ms = latency_ms
        self._fail_on = fail_on or []
        self._tier = tier
        self._call_count = 0
        self._calls: List[Dict[str, Any]] = []
        self.models = {
            f"{name}-model": ModelSpec(
                model_id=f"{name}-model",
                provider=name,
                display_name=f"Mock {name}",
                context_window=128_000,
                max_output_tokens=8192,
                input_price_per_m=1.0,
                output_price_per_m=3.0,
                capabilities=(
                    ModelCapability.TEXT,
                    ModelCapability.CODE,
                    ModelCapability.REASONING,
                ),
                tier=tier,
            )
        }

    async def _raw_generate(
        self,
        prompt: str,
        model: str = "mock-model",
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate a mock response."""
        self._call_count += 1
        self._calls.append({
            "prompt": prompt,
            "model": model,
            "system_prompt": system_prompt,
            "kwargs": kwargs,
        })

        # Simulate failure for specific prompts
        for fail_pattern in self._fail_on:
            if fail_pattern.lower() in prompt.lower():
                raise RuntimeError(f"Mock provider '{self.provider_name}' simulated failure for: {fail_pattern}")

        # Select response based on prompt keywords
        response_text = self._responses.get("default", "Mock response.")
        for key, text in self._responses.items():
            if key != "default" and key.lower() in prompt.lower():
                response_text = text
                break

        return ModelResponse(
            model=model,
            provider=self.provider_name,
            response=response_text,
            confidence=self._confidence,
            tokens_in=self._tokens_in,
            tokens_out=self._tokens_out,
            cost_usd=self._cost_per_call,
            latency_ms=self._latency_ms,
            tier=self._tier,
        )

    def reset(self) -> None:
        """Reset call counters for test isolation."""
        self._call_count = 0
        self._calls.clear()


class FailingMockProvider(MockLLMProvider):
    """A mock provider that always fails — used to test cascade fallback."""

    def __init__(self, name: str = "failing_mock", **kwargs):
        super().__init__(name=name, **kwargs)

    async def _raw_generate(self, prompt: str, model: str = "", **kwargs) -> ModelResponse:
        self._call_count += 1
        raise RuntimeError(f"Provider '{self.provider_name}' is intentionally offline")
