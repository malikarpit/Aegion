"""
Tests for MCTS Reasoning Chain — Section 1.15.

Covers:
    - ThoughtNode data structure (UCB1, Q-value, serialization)
    - MCTSConfig validation
    - MCTSReasoner core algorithms (select, backpropagate, extract best path)
    - Parsing helpers (candidates, critic scores, heuristic scores)
    - ReasoningChain backward-compat wrapper
    - ReasoningStep serialization

References:
    - Kocsis & Szepesvári "Bandit-based MCTS" (2006)
    - OpenAI o1 inference-time compute scaling paradigm
"""

import math
import pytest

from app.services.reasoning_chain import (
    ThoughtNode,
    MCTSConfig,
    MCTSReasoner,
    ReasoningChain,
    ReasoningStep,
    ReasoningChainService,
    get_reasoning_service,
)


# ══════════════════════════════════════════════════════════════════════════════
# THOUGHT NODE
# ══════════════════════════════════════════════════════════════════════════════

class TestThoughtNode:
    """ThoughtNode data structure and UCB1 computation."""

    def test_q_value_zero_visits(self):
        node = ThoughtNode(thought="test")
        assert node.q_value == 0.0

    def test_q_value_computed(self):
        node = ThoughtNode(thought="test")
        node.total_value = 3.0
        node.visit_count = 5
        assert node.q_value == 0.6

    def test_ucb1_unvisited(self):
        """Unvisited nodes should have infinite UCB1 (explore first)."""
        node = ThoughtNode(thought="test")
        assert node.ucb1(parent_visits=10) == float("inf")

    def test_ucb1_visited(self):
        """UCB1 should balance exploitation and exploration."""
        node = ThoughtNode(thought="test")
        node.total_value = 0.8
        node.visit_count = 4
        ucb = node.ucb1(parent_visits=10, c=1.414)
        # exploitation = 0.8/4 = 0.2
        # exploration = 1.414 * sqrt(ln(10)/4)
        exploitation = 0.2
        exploration = 1.414 * math.sqrt(math.log(10) / 4)
        assert abs(ucb - (exploitation + exploration)) < 0.001

    def test_to_dict(self):
        node = ThoughtNode(thought="analyze code", depth=2)
        d = node.to_dict()
        assert d["thought"] == "analyze code"
        assert d["depth"] == 2
        assert "id" in d
        assert "q_value" in d

    def test_unique_ids(self):
        n1 = ThoughtNode(thought="a")
        n2 = ThoughtNode(thought="b")
        assert n1.id != n2.id


# ══════════════════════════════════════════════════════════════════════════════
# MCTS CONFIG
# ══════════════════════════════════════════════════════════════════════════════

class TestMCTSConfig:
    """MCTS configuration."""

    def test_default_config(self):
        config = MCTSConfig()
        assert config.max_iterations == 8
        assert config.branch_factor == 3
        assert config.exploration_c == 1.414
        assert config.max_depth == 6

    def test_custom_config(self):
        config = MCTSConfig(max_iterations=20, branch_factor=5)
        assert config.max_iterations == 20
        assert config.branch_factor == 5


# ══════════════════════════════════════════════════════════════════════════════
# MCTS REASONER — CORE ALGORITHMS
# ══════════════════════════════════════════════════════════════════════════════

class TestMCTSSelect:
    """MCTS selection phase."""

    def test_select_root_no_children(self):
        """Selection on root with no children returns root."""
        reasoner = MCTSReasoner()
        root = ThoughtNode(thought="query")
        reasoner.nodes = {root.id: root}
        selected = reasoner._select(root)
        assert selected.id == root.id

    def test_select_prefers_unvisited(self):
        """Should prefer unvisited children (UCB1 = inf)."""
        reasoner = MCTSReasoner()
        root = ThoughtNode(thought="root", visit_count=5, total_value=2.0)
        child1 = ThoughtNode(thought="visited", parent_id=root.id, visit_count=3, total_value=1.5)
        child2 = ThoughtNode(thought="unvisited", parent_id=root.id, visit_count=0, total_value=0.0)
        root.children = [child1.id, child2.id]
        reasoner.nodes = {root.id: root, child1.id: child1, child2.id: child2}

        selected = reasoner._select(root)
        assert selected.id == child2.id  # Unvisited has UCB1 = inf

    def test_select_skips_pruned(self):
        """Should skip pruned children."""
        reasoner = MCTSReasoner()
        root = ThoughtNode(thought="root", visit_count=5, total_value=2.0)
        pruned = ThoughtNode(thought="pruned", parent_id=root.id, is_pruned=True, visit_count=1, total_value=0.1)
        good = ThoughtNode(thought="good", parent_id=root.id, visit_count=2, total_value=1.0)
        root.children = [pruned.id, good.id]
        reasoner.nodes = {root.id: root, pruned.id: pruned, good.id: good}

        selected = reasoner._select(root)
        assert selected.id == good.id


class TestMCTSBackpropagate:
    """MCTS backpropagation phase."""

    def test_backprop_single_node(self):
        reasoner = MCTSReasoner()
        node = ThoughtNode(thought="leaf")
        reasoner.nodes = {node.id: node}

        reasoner._backpropagate(node, 0.8)
        assert node.visit_count == 1
        assert node.total_value == 0.8

    def test_backprop_chain(self):
        """Value should propagate from child to root."""
        reasoner = MCTSReasoner()
        root = ThoughtNode(thought="root")
        child = ThoughtNode(thought="child", parent_id=root.id)
        leaf = ThoughtNode(thought="leaf", parent_id=child.id)
        reasoner.nodes = {root.id: root, child.id: child, leaf.id: leaf}

        reasoner._backpropagate(leaf, 0.9)

        assert leaf.total_value == 0.9
        assert child.total_value == 0.9
        assert root.total_value == 0.9
        assert leaf.visit_count == 1
        assert child.visit_count == 1
        assert root.visit_count == 1


class TestMCTSExtractPath:
    """Best path extraction after search is complete."""

    def test_extract_single_node(self):
        reasoner = MCTSReasoner()
        root = ThoughtNode(thought="root")
        reasoner.nodes = {root.id: root}
        reasoner.root_id = root.id

        path = reasoner._extract_best_path()
        assert len(path) == 1
        assert path[0].thought == "root"

    def test_extract_picks_highest_q(self):
        """Should pick the child with highest Q-value at each level."""
        reasoner = MCTSReasoner()
        root = ThoughtNode(thought="root", visit_count=5)
        good = ThoughtNode(thought="good", parent_id=root.id, visit_count=3, total_value=2.4)
        bad = ThoughtNode(thought="bad", parent_id=root.id, visit_count=3, total_value=0.3)
        root.children = [good.id, bad.id]
        reasoner.nodes = {root.id: root, good.id: good, bad.id: bad}
        reasoner.root_id = root.id

        path = reasoner._extract_best_path()
        assert len(path) == 2
        assert path[1].thought == "good"  # Q=0.8 vs Q=0.1


# ══════════════════════════════════════════════════════════════════════════════
# PARSING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

class TestParsing:
    """Response parsing utilities."""

    def test_parse_candidates(self):
        reasoner = MCTSReasoner()
        text = (
            "[CANDIDATE 1]: First approach using dynamic programming\n"
            "[CANDIDATE 2]: Second approach using greedy algorithm\n"
            "[CANDIDATE 3]: Third approach using divide and conquer"
        )
        candidates = reasoner._parse_candidates(text)
        assert len(candidates) == 3
        assert "dynamic programming" in candidates[0]

    def test_parse_candidates_empty(self):
        reasoner = MCTSReasoner()
        candidates = reasoner._parse_candidates("just a normal text response")
        assert len(candidates) == 0

    def test_parse_critic_score_json(self):
        reasoner = MCTSReasoner()
        text = '{"coherence": 0.8, "grounding": 0.9, "overall": 0.85}'
        score = reasoner._parse_critic_score(text)
        assert score == 0.85

    def test_parse_critic_score_fallback(self):
        reasoner = MCTSReasoner()
        score = reasoner._parse_critic_score("unparseable garbage")
        assert score == 0.5  # Default

    def test_parse_critic_score_clamped(self):
        reasoner = MCTSReasoner()
        text = '{"overall": 1.5}'  # Over 1.0
        score = reasoner._parse_critic_score(text)
        assert score == 1.0


class TestHeuristicScore:
    """Heuristic fallback scoring when critic LLM is unavailable."""

    def test_short_thought_lower(self):
        reasoner = MCTSReasoner()
        short = reasoner._heuristic_score("yes")
        long = reasoner._heuristic_score(
            "The issue is caused by an off-by-one error in the loop condition. "
            "Specifically, the iteration should use < instead of <= because "
            "the array is zero-indexed and has length N."
        )
        assert long > short

    def test_reasoning_markers_boost(self):
        reasoner = MCTSReasoner()
        plain = reasoner._heuristic_score("The code has a bug in line 42")
        reasoned = reasoner._heuristic_score(
            "The code has a bug in line 42 because the loop variable overflows. "
            "Therefore we need to add a bounds check. For example, we could use "
            "a guard clause to handle this specifically."
        )
        assert reasoned > plain

    def test_hedging_penalty(self):
        reasoner = MCTSReasoner()
        confident = reasoner._heuristic_score(
            "The solution is to refactor the authentication module to use JWT tokens "
            "with proper expiration handling." + " filler" * 20
        )
        hedging = reasoner._heuristic_score(
            "I think maybe the solution could possibly be to refactor the auth module "
            "but I'm not sure if it would work." + " filler" * 20
        )
        assert confident > hedging

    def test_score_clamped(self):
        reasoner = MCTSReasoner()
        score = reasoner._heuristic_score("")
        assert 0.0 <= score <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# BACKWARD-COMPAT WRAPPERS
# ══════════════════════════════════════════════════════════════════════════════

class TestReasoningStep:
    """Backward-compatible ReasoningStep."""

    def test_step_creation(self):
        step = ReasoningStep("analysis", "Analyzing code structure")
        assert step.step_type == "analysis"
        assert step.description == "Analyzing code structure"
        assert step.confidence == 0.0

    def test_step_with_kwargs(self):
        step = ReasoningStep("conclusion", "Found the bug", confidence=0.9, cost_usd=0.01)
        assert step.confidence == 0.9
        assert step.cost_usd == 0.01

    def test_step_to_dict(self):
        step = ReasoningStep("test", "desc")
        d = step.to_dict()
        assert "id" in d
        assert d["step_type"] == "test"


class TestReasoningChain:
    """Backward-compatible ReasoningChain."""

    def test_chain_creation(self):
        chain = ReasoningChain("ws-1", "dec-1", "Why is this slow?")
        assert chain.workspace_id == "ws-1"
        assert chain.query == "Why is this slow?"

    def test_add_step(self):
        chain = ReasoningChain("ws-1", "dec-1", "query")
        chain.add_step("analysis", "Profiling the code", cost_usd=0.005)
        assert len(chain.steps) == 1
        assert chain.total_cost == 0.005

    def test_set_conclusion(self):
        chain = ReasoningChain("ws-1", "dec-1", "query")
        chain.add_step("a", "step1", confidence=0.8)
        chain.add_step("b", "step2", confidence=0.6)
        chain.set_conclusion("The bottleneck is the database query")
        assert chain.conclusion == "The bottleneck is the database query"
        assert chain.overall_confidence == 0.7  # Average of 0.8 and 0.6

    def test_to_dict(self):
        chain = ReasoningChain("ws-1", "dec-1", "query")
        d = chain.to_dict()
        assert d["workspace_id"] == "ws-1"
        assert "steps" in d
        assert "conclusion" in d


class TestReasoningService:
    """ReasoningChainService singleton."""

    def test_singleton(self):
        import app.services.reasoning_chain as rc_module
        rc_module._reasoning_service = None
        s1 = get_reasoning_service()
        s2 = get_reasoning_service()
        assert s1 is s2
        rc_module._reasoning_service = None

    def test_create_chain(self):
        service = ReasoningChainService()
        chain = service.create("ws-1", "dec-1", "query")
        assert isinstance(chain, ReasoningChain)
