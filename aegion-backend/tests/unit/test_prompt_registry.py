"""
Tests for Self-Improvement — Section 1.16: DSPy-Style Prompt Auto-Tuning.

Covers:
    PromptVariant:
        - Average score computation
        - Template hashing (SHA-256)
        - Default values

    PromptRegistry:
        - Default template initialization (debate, peer review, sentinel, mcts)
        - compile() — variable substitution
        - compile() — few-shot injection
        - compile() — unknown template raises KeyError
        - record_outcome() — score tracking
        - record_outcome() — mutation threshold logic
        - inject_few_shot() — deduplication and max-5 limit
        - get_variant_history() — version lineage
        - list_templates() — all registered templates
        - Singleton pattern

References:
    - DSPy (Khattab et al., Stanford NLP, 2023)
    - "Programming, not Prompting" paradigm
"""

import pytest

from app.services.prompt_registry import (
    PromptVariant,
    CompiledPrompt,
    PromptRegistry,
    get_prompt_registry,
    _DEFAULT_TEMPLATES,
)


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT VARIANT
# ══════════════════════════════════════════════════════════════════════════════

class TestPromptVariant:
    """PromptVariant data structure."""

    def test_avg_score_zero_uses(self):
        v = PromptVariant(template="test")
        assert v.avg_score == 0.0

    def test_avg_score_computed(self):
        v = PromptVariant(template="test")
        v.total_uses = 4
        v.total_score = 3.2
        assert v.avg_score == 0.8

    def test_template_hash_deterministic(self):
        v1 = PromptVariant(template="hello world")
        v2 = PromptVariant(template="hello world")
        assert v1.template_hash == v2.template_hash

    def test_template_hash_different_content(self):
        v1 = PromptVariant(template="hello")
        v2 = PromptVariant(template="world")
        assert v1.template_hash != v2.template_hash

    def test_unique_ids(self):
        v1 = PromptVariant(template="a")
        v2 = PromptVariant(template="b")
        assert v1.id != v2.id


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT REGISTRY — INITIALIZATION
# ══════════════════════════════════════════════════════════════════════════════

class TestRegistryInit:
    """Registry initialization with default templates."""

    def test_default_templates_loaded(self):
        reg = PromptRegistry()
        templates = reg.list_templates()
        assert "debate.opening" in templates
        assert "debate.fresh_eyes" in templates
        assert "peer_review.independent" in templates
        assert "mcts.expand" in templates

    def test_all_defaults_have_active_variant(self):
        reg = PromptRegistry()
        for name in _DEFAULT_TEMPLATES:
            assert name in reg._active_variant

    def test_default_count_matches(self):
        reg = PromptRegistry()
        assert len(reg.list_templates()) == len(_DEFAULT_TEMPLATES)


# ══════════════════════════════════════════════════════════════════════════════
# COMPILE
# ══════════════════════════════════════════════════════════════════════════════

class TestCompile:
    """Prompt compilation with variable substitution."""

    @pytest.mark.asyncio
    async def test_compile_basic(self):
        reg = PromptRegistry()
        result = await reg.compile(
            "debate.opening",
            {"round": "2", "max_rounds": "4", "proposition": "Use React", "previous_context": ""},
        )
        assert isinstance(result, CompiledPrompt)
        assert "2" in result.text
        assert "Use React" in result.text

    @pytest.mark.asyncio
    async def test_compile_unknown_template(self):
        reg = PromptRegistry()
        with pytest.raises(KeyError, match="Unknown prompt template"):
            await reg.compile("nonexistent.template", {})

    @pytest.mark.asyncio
    async def test_compile_missing_variables_stay(self):
        """Variables not provided should stay as {variable} placeholders."""
        reg = PromptRegistry()
        result = await reg.compile("debate.opening", {"round": "1"})
        # {max_rounds} was not provided, should be left as-is
        assert "{max_rounds}" in result.text

    @pytest.mark.asyncio
    async def test_compile_with_few_shot(self):
        reg = PromptRegistry()
        await reg.inject_few_shot("debate.opening", [
            {"input": "Should we use TypeScript?", "output": "Yes, for type safety."}
        ])
        result = await reg.compile("debate.opening", {"round": "1", "max_rounds": "3",
                                                       "proposition": "test", "previous_context": ""})
        assert "EXAMPLE" in result.text
        assert result.few_shot_count == 1


# ══════════════════════════════════════════════════════════════════════════════
# RECORD OUTCOME
# ══════════════════════════════════════════════════════════════════════════════

class TestRecordOutcome:
    """Outcome tracking and mutation triggering."""

    @pytest.mark.asyncio
    async def test_record_updates_stats(self):
        reg = PromptRegistry()
        compiled = await reg.compile("debate.opening", {"round": "1", "max_rounds": "3",
                                                         "proposition": "x", "previous_context": ""})
        await reg.record_outcome("debate.opening", compiled.variant_id, 0.85)

        variant = reg._get_active_variant("debate.opening")
        assert variant.total_uses == 1
        assert variant.total_score == 0.85
        assert variant.best_score == 0.85

    @pytest.mark.asyncio
    async def test_record_best_worst_tracked(self):
        reg = PromptRegistry()
        compiled = await reg.compile("debate.opening", {"round": "1", "max_rounds": "3",
                                                         "proposition": "x", "previous_context": ""})
        vid = compiled.variant_id

        await reg.record_outcome("debate.opening", vid, 0.3)
        await reg.record_outcome("debate.opening", vid, 0.9)

        variant = reg._get_active_variant("debate.opening")
        assert variant.best_score == 0.9
        assert variant.worst_score == 0.3

    @pytest.mark.asyncio
    async def test_no_mutation_above_threshold(self):
        reg = PromptRegistry()
        compiled = await reg.compile("debate.opening", {"round": "1", "max_rounds": "3",
                                                         "proposition": "x", "previous_context": ""})
        vid = compiled.variant_id

        # Record 3 good scores
        for _ in range(3):
            result = await reg.record_outcome("debate.opening", vid, 0.85)

        # Should NOT trigger mutation (0.85 > 0.55 threshold)
        assert result is None

    @pytest.mark.asyncio
    async def test_record_nonexistent_variant(self):
        reg = PromptRegistry()
        result = await reg.record_outcome("debate.opening", "fake-id", 0.5)
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# FEW-SHOT INJECTION
# ══════════════════════════════════════════════════════════════════════════════

class TestFewShot:
    """Few-shot example injection."""

    @pytest.mark.asyncio
    async def test_inject_examples(self):
        reg = PromptRegistry()
        await reg.inject_few_shot("debate.opening", [
            {"input": "q1", "output": "a1"},
            {"input": "q2", "output": "a2"},
        ])
        variant = reg._get_active_variant("debate.opening")
        assert len(variant.few_shot_examples) == 2

    @pytest.mark.asyncio
    async def test_deduplication(self):
        reg = PromptRegistry()
        await reg.inject_few_shot("debate.opening", [{"input": "q1", "output": "a1"}])
        await reg.inject_few_shot("debate.opening", [{"input": "q1", "output": "a1_different"}])
        variant = reg._get_active_variant("debate.opening")
        assert len(variant.few_shot_examples) == 1

    @pytest.mark.asyncio
    async def test_max_five_examples(self):
        reg = PromptRegistry()
        examples = [{"input": f"q{i}", "output": f"a{i}"} for i in range(10)]
        await reg.inject_few_shot("debate.opening", examples)
        variant = reg._get_active_variant("debate.opening")
        assert len(variant.few_shot_examples) <= 5


# ══════════════════════════════════════════════════════════════════════════════
# VARIANT HISTORY
# ══════════════════════════════════════════════════════════════════════════════

class TestVariantHistory:
    """Version lineage tracking."""

    def test_history_has_v1(self):
        reg = PromptRegistry()
        history = reg.get_variant_history("debate.opening")
        assert len(history) == 1
        assert history[0]["version"] == 1
        assert history[0]["is_active"] is True

    def test_history_nonexistent(self):
        reg = PromptRegistry()
        assert reg.get_variant_history("nonexistent") == []


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

class TestSingleton:
    def test_singleton(self):
        import app.services.prompt_registry as pr
        pr._prompt_registry = None
        r1 = get_prompt_registry()
        r2 = get_prompt_registry()
        assert r1 is r2
        pr._prompt_registry = None
