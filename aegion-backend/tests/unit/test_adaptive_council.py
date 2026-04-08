"""Unit tests for Phase 77: AdaptiveCouncil size and routing policies."""

import pytest
from unittest.mock import MagicMock, patch

from app.services.council_kernel.adaptive_council import (
    AdaptiveCouncil,
    SIZE_POLICIES,
    PROFILE_TO_COMPLEXITY,
)
from app.services.council_kernel.types import CouncilProfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def council():
    return AdaptiveCouncil()


def _mock_router(providers: list[str]) -> MagicMock:
    """Build a mock ModelRouter with the given provider names registered."""
    router = MagicMock()
    router.providers = {}
    for name in providers:
        provider = MagicMock()
        if name == "google":
            provider.models = {"gemini-2.0-flash": None, "gemini-2.5-pro-preview-06-05": None}
        elif name == "openai":
            provider.models = {"gpt-4.1-mini": None, "gpt-4.1": None}
        elif name == "anthropic":
            provider.models = {"claude-haiku-3-5-20241022": None, "claude-sonnet-4-20250514": None}
        elif name == "deepseek":
            provider.models = {"deepseek-chat": None, "deepseek-reasoner": None}
        else:
            provider.models = {}
        router.providers[name] = provider
    return router


# ---------------------------------------------------------------------------
# get_council_config — complexity → policy
# ---------------------------------------------------------------------------

class TestGetCouncilConfig:
    def test_simple_gives_1_model(self, council):
        cfg = council.get_council_config("simple")
        assert cfg["model_count"] == 1
        assert cfg["strategy"] == "cascade"
        assert cfg["prefer_cheap"] is True

    def test_medium_gives_2_models(self, council):
        cfg = council.get_council_config("medium")
        assert cfg["model_count"] == 2
        assert cfg["strategy"] == "peer_review"

    def test_complex_gives_3_models(self, council):
        cfg = council.get_council_config("complex")
        assert cfg["model_count"] == 3
        assert cfg["council_type"] == "parent"

    def test_critical_gives_4_models(self, council):
        cfg = council.get_council_config("critical")
        assert cfg["model_count"] == 4
        assert "red_team" in cfg["strategy"]

    def test_unknown_complexity_falls_back_to_medium(self, council):
        cfg = council.get_council_config("nonsense_value")
        assert cfg["model_count"] == 2  # medium default

    def test_none_complexity_falls_back_to_medium(self, council):
        cfg = council.get_council_config(None)
        assert cfg["model_count"] == 2

    def test_profile_value_strings_normalised(self, council):
        """CouncilProfile.value strings (e.g. 'moderate') must map correctly."""
        cfg = council.get_council_config("moderate")
        assert cfg["model_count"] == 2  # moderate → medium → 2

        cfg = council.get_council_config("trivial")
        assert cfg["model_count"] == 1  # trivial → simple → 1

    def test_user_override_applied(self, council):
        cfg = council.get_council_config("simple", user_override={"model_count": 3})
        assert cfg["model_count"] == 3  # override beats default

    def test_none_override_values_ignored(self, council):
        """None override values must not clobber valid defaults."""
        cfg = council.get_council_config("medium", user_override={"model_count": None})
        assert cfg["model_count"] == 2


# ---------------------------------------------------------------------------
# select_models — provider selection logic
# ---------------------------------------------------------------------------

class TestSelectModels:
    def test_returns_empty_when_no_providers(self, council):
        router = _mock_router([])
        assert council.select_models(router, count=2) == []

    def test_respects_count_upper_bound(self, council):
        router = _mock_router(["google", "openai", "anthropic"])
        slots = council.select_models(router, count=2, prefer_cheap=True)
        assert len(slots) <= 2

    def test_count_1_returns_single_provider(self, council):
        router = _mock_router(["google"])
        slots = council.select_models(router, count=1)
        assert len(slots) == 1
        assert slots[0][0] == "google"

    def test_cheap_priority_prefers_deepseek_over_openai(self, council):
        router = _mock_router(["openai", "deepseek"])
        slots = council.select_models(router, count=1, prefer_cheap=True)
        # deepseek is cheaper — should come first
        assert slots[0][0] == "deepseek"

    def test_quality_priority_prefers_anthropic_over_deepseek(self, council):
        router = _mock_router(["deepseek", "anthropic"])
        slots = council.select_models(router, count=1, prefer_cheap=False)
        assert slots[0][0] == "anthropic"

    def test_fewer_providers_than_count(self, council):
        """Should return what's available, not crash."""
        router = _mock_router(["google"])
        slots = council.select_models(router, count=3)
        assert len(slots) == 1  # only 1 registered

    def test_no_duplicate_providers(self, council):
        router = _mock_router(["google", "openai"])
        slots = council.select_models(router, count=2)
        providers = [s[0] for s in slots]
        assert len(providers) == len(set(providers))


# ---------------------------------------------------------------------------
# profile_to_complexity — bridge method
# ---------------------------------------------------------------------------

class TestProfileToComplexity:
    @pytest.mark.parametrize("profile,expected", [
        (CouncilProfile.TRIVIAL,  "simple"),
        (CouncilProfile.SIMPLE,   "simple"),
        (CouncilProfile.MODERATE, "medium"),
        (CouncilProfile.COMPLEX,  "complex"),
        (CouncilProfile.CRITICAL, "critical"),
    ])
    def test_profile_maps_correctly(self, council, profile, expected):
        assert council.profile_to_complexity(profile) == expected
