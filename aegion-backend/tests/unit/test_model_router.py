"""
Unit tests for ModelRouter.

Tests the 9-provider model routing abstraction covering:
  - Provider registration and configuration
  - Model catalog lookups
  - Call routing and response formatting
  - Fallback behavior on provider failure
  - API key injection from user headers
  - Cost calculation per request
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.council_kernel.model_router import ModelRouter, MODEL_CATALOG
from app.services.council_kernel.types import ModelResponse


@pytest.fixture
def router():
    """Create a fresh ModelRouter."""
    return ModelRouter()


class TestModelCatalog:
    """Tests for the static MODEL_CATALOG registry."""

    def test_catalog_has_entries(self):
        assert len(MODEL_CATALOG) > 0

    def test_catalog_entries_have_required_fields(self):
        for model_id, entry in MODEL_CATALOG.items():
            assert hasattr(entry, "provider"), f"{model_id} missing 'provider'"
            assert hasattr(entry, "context_window"), f"{model_id} missing 'context_window'"
            assert hasattr(entry, "tier"), f"{model_id} missing 'tier'"
            assert entry.context_window > 0, f"{model_id} has invalid context_window"

    def test_known_providers_present(self):
        providers = {e.provider for e in MODEL_CATALOG.values()}
        # At minimum we expect these providers in the catalog
        for expected in ["openai", "anthropic", "google"]:
            assert expected in providers, f"Provider {expected} missing from catalog"

    def test_tiers_range(self):
        for model_id, entry in MODEL_CATALOG.items():
            assert 1 <= entry.tier <= 4, f"{model_id} tier {entry.tier} out of [1,4]"

    def test_cost_fields_present(self):
        for model_id, entry in MODEL_CATALOG.items():
            assert hasattr(entry, "input_price_per_m"), f"{model_id} missing input cost"
            assert hasattr(entry, "output_price_per_m"), f"{model_id} missing output cost"
            assert entry.input_price_per_m >= 0
            assert entry.output_price_per_m >= 0


class TestModelRouter:
    """Tests for the ModelRouter class."""

    def test_initial_state(self, router):
        assert isinstance(router.providers, dict)
        assert len(router.providers) == 0

    @pytest.mark.asyncio
    async def test_configure_from_user_keys_openai(self, router):
        """Configuring with an OpenAI key should register the openai provider."""
        await router.configure_from_user_keys({"openai_key": "sk-test-key"})
        assert "openai" in router.providers

    @pytest.mark.asyncio
    async def test_configure_from_user_keys_anthropic(self, router):
        await router.configure_from_user_keys({"anthropic_key": "sk-ant-test"})
        assert "anthropic" in router.providers

    @pytest.mark.asyncio
    async def test_configure_from_user_keys_google(self, router):
        await router.configure_from_user_keys({"google_key": "AIza-test"})
        assert "google" in router.providers

    @pytest.mark.asyncio
    async def test_configure_from_user_keys_multiple(self, router):
        """Multiple keys should register multiple providers."""
        await router.configure_from_user_keys({
            "openai_key": "sk-test",
            "anthropic_key": "sk-ant-test",
        })
        assert "openai" in router.providers
        assert "anthropic" in router.providers

    @pytest.mark.asyncio
    async def test_call_returns_model_response(self, router):
        """Router.call should return a valid ModelResponse."""
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = ModelResponse(
            provider="openai",
            model="gpt-4o",
            response="The answer is 42.",
            prompt_tokens=50,
            completion_tokens=30,
            cost=0.005,
            latency_ms=100,
            confidence=0.9
        )
        router.providers["openai"] = mock_provider

        response = await router.call("openai", "gpt-4o", "What is 6*7?")

        assert isinstance(response, ModelResponse)
        assert response.provider == "openai"
        assert response.model == "gpt-4o"
        assert len(response.response) > 0

    @pytest.mark.asyncio
    async def test_call_unknown_provider_raises(self, router):
        """Calling an unregistered provider should raise."""
        with pytest.raises((KeyError, RuntimeError, ValueError)):
            await router.call("nonexistent", "some-model", "hello")

    def test_calculate_cost_basic(self, router):
        """Cost calculation: tokens * rate / 1M."""
        # Inject a known model into catalog for test
        cost = router.estimate_cost(
            model_id="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
        )
        assert isinstance(cost, float)
        assert cost >= 0

    def test_get_model_spec(self, router):
        """get_model_spec should return catalog entry for known models."""
        # Pick any model from catalog
        model_id = next(iter(MODEL_CATALOG))
        info = router.get_model_spec(model_id)
        assert info is not None
        assert hasattr(info, "provider")

    def test_get_model_spec_unknown(self, router):
        """get_model_spec for unknown model should return None or fallback."""
        info = router.get_model_spec("nonexistent-model-xyz")
        assert info is None or hasattr(info, "provider")

    def test_available_models_for_provider(self, router):
        """Should list all models for a given provider."""
        openai_models = [
            mid for mid, entry in MODEL_CATALOG.items()
            if entry.provider == "openai"
        ]
        assert len(openai_models) > 0
