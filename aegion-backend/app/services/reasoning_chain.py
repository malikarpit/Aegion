"""
MCTS Reasoning Engine — Phase 45 (Elevated): Inference-Time Scaling.

Replaces linear chain-of-thought with Monte Carlo Tree Search (MCTS) over
reasoning steps, inspired by the inference-time compute scaling paradigm
used in OpenAI o1/o3 and DeepMind AlphaProof.

How it works:
  1. The root node is the user's query.
  2. At each tree level, a "generator" LLM proposes N candidate next-thoughts.
  3. A separate "critic" LLM scores each candidate (the Q-value: 0.0–1.0).
  4. We SELECT the highest-UCB1 child, EXPAND it, SIMULATE to terminal depth,
     and BACKPROPAGATE the critic's score up the tree.
  5. After the search budget is exhausted, we extract the highest-value path
     from root to leaf — this is the final reasoning chain.

Why this matters:
  - Linear chain-of-thought can't recover from a bad early step.
  - MCTS explores multiple branches and self-corrects before committing.
  - The critic model catches hallucinations that the generator misses.
  - We get a full exploration tree for auditability (not just the final answer).

Configuration:
  - max_iterations: Total MCTS iterations (more = better but slower/costlier)
  - branch_factor:  Candidate thoughts generated per expansion
  - exploration_c:  UCB1 exploration constant (higher = more exploration)
  - max_depth:      Maximum reasoning depth before forced evaluation
"""

from __future__ import annotations

import asyncio
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.logging import logger


# ──────────────────────────────────────────────────────────────────────────────
# Tree Structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ThoughtNode:
    """A single node in the MCTS reasoning tree."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    thought: str = ""                         # The reasoning content at this node
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)  # Child node IDs
    depth: int = 0

    # MCTS statistics
    visit_count: int = 0
    total_value: float = 0.0                  # Sum of backpropagated Q-values
    prior_score: float = 0.0                  # Critic's initial score for this thought
    is_terminal: bool = False                 # True if this is a conclusion node
    is_pruned: bool = False                   # True if critic scored < prune_threshold

    # Metadata
    model_used: str = ""
    cost_usd: float = 0.0
    latency_ms: int = 0

    @property
    def q_value(self) -> float:
        """Average backpropagated value (exploitation signal)."""
        if self.visit_count == 0:
            return 0.0
        return self.total_value / self.visit_count

    def ucb1(self, parent_visits: int, c: float = 1.414) -> float:
        """Upper Confidence Bound for tree selection."""
        if self.visit_count == 0:
            return float("inf")  # Always explore unvisited nodes first
        exploitation = self.q_value
        exploration = c * math.sqrt(math.log(parent_visits) / self.visit_count)
        return exploitation + exploration

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "thought": self.thought,
            "parent_id": self.parent_id,
            "children": self.children,
            "depth": self.depth,
            "visit_count": self.visit_count,
            "q_value": round(self.q_value, 4),
            "prior_score": round(self.prior_score, 4),
            "is_terminal": self.is_terminal,
            "is_pruned": self.is_pruned,
            "model_used": self.model_used,
            "cost_usd": self.cost_usd,
        }


@dataclass
class MCTSConfig:
    """Tunable parameters for the MCTS search."""
    max_iterations: int = 8        # Total search budget (MCTS iterations)
    branch_factor: int = 3         # Candidate thoughts per expansion
    exploration_c: float = 1.414   # UCB1 exploration constant (sqrt(2) is standard)
    max_depth: int = 6             # Maximum reasoning depth
    prune_threshold: float = 0.25  # Critic score below which a branch is pruned
    min_terminal_confidence: float = 0.60  # Minimum confidence for a conclusion


# ──────────────────────────────────────────────────────────────────────────────
# MCTS Reasoner
# ──────────────────────────────────────────────────────────────────────────────

class MCTSReasoner:
    """
    Monte Carlo Tree Search over reasoning steps.

    Usage:
        reasoner = MCTSReasoner(council_engine)
        result = await reasoner.reason(workspace_id, query)
        # result contains the full tree + best path + final answer
    """

    def __init__(self, config: Optional[MCTSConfig] = None) -> None:
        self.config = config or MCTSConfig()
        self.nodes: Dict[str, ThoughtNode] = {}
        self.root_id: Optional[str] = None

    async def reason(
        self,
        workspace_id: str,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run MCTS reasoning on a query.

        Returns:
            query:              Original query
            best_path:          List of ThoughtNode dicts (root → conclusion)
            final_answer:       The terminal node's thought (the answer)
            confidence:         Q-value of the best terminal node
            tree_stats:         Statistics about the search
            total_cost_usd:     Sum of all LLM calls during search
            exploration_tree:   Full tree for auditability
        """
        start = time.monotonic()
        context = context or {}

        # Initialize root
        root = ThoughtNode(thought=query, depth=0, is_terminal=False)
        self.nodes = {root.id: root}
        self.root_id = root.id
        root.visit_count = 1  # Root is always "visited"

        total_cost = 0.0

        # Main MCTS loop
        for iteration in range(self.config.max_iterations):
            # 1. SELECT — walk down the tree using UCB1
            selected = self._select(root)

            # 2. EXPAND — generate candidate next-thoughts
            if not selected.is_terminal and selected.depth < self.config.max_depth:
                children, cost = await self._expand(selected, query, context)
                total_cost += cost

                # If expansion produced nothing, mark as terminal
                if not children:
                    selected.is_terminal = True
                    continue

                # 3. SIMULATE — evaluate each new child with the critic
                for child in children:
                    critic_score, cost = await self._simulate(child, query, context)
                    total_cost += cost
                    child.prior_score = critic_score

                    # Prune low-quality branches
                    if critic_score < self.config.prune_threshold:
                        child.is_pruned = True

                    # 4. BACKPROPAGATE — push the critic score up to the root
                    self._backpropagate(child, critic_score)
            else:
                # Selected node is terminal or at max depth — just backpropagate
                self._backpropagate(selected, selected.q_value)

        # Extract best path
        best_path = self._extract_best_path()
        final_node = best_path[-1] if best_path else root
        latency = int((time.monotonic() - start) * 1000)

        # Build the serializable result
        result = {
            "query": query,
            "best_path": [n.to_dict() for n in best_path],
            "final_answer": final_node.thought,
            "confidence": round(final_node.q_value, 4),
            "tree_stats": {
                "total_nodes": len(self.nodes),
                "total_iterations": self.config.max_iterations,
                "max_depth_reached": max((n.depth for n in self.nodes.values()), default=0),
                "pruned_branches": sum(1 for n in self.nodes.values() if n.is_pruned),
                "terminal_nodes": sum(1 for n in self.nodes.values() if n.is_terminal),
            },
            "total_cost_usd": round(total_cost, 6),
            "total_latency_ms": latency,
            "exploration_tree": {nid: n.to_dict() for nid, n in self.nodes.items()},
        }

        # Persist (best-effort)
        await self._persist(workspace_id, result)

        return result

    # ──────────────────────────────────────────────
    # MCTS Core: Selection
    # ──────────────────────────────────────────────

    def _select(self, node: ThoughtNode) -> ThoughtNode:
        """
        Walk down the tree selecting the child with highest UCB1 at each level.

        Stops when reaching an unexpanded or terminal node.
        """
        current = node
        while current.children and not current.is_terminal:
            # Get non-pruned children
            viable = [
                self.nodes[cid] for cid in current.children
                if cid in self.nodes and not self.nodes[cid].is_pruned
            ]
            if not viable:
                break  # All children pruned — this node becomes a dead end
            current = max(viable, key=lambda c: c.ucb1(current.visit_count, self.config.exploration_c))
        return current

    # ──────────────────────────────────────────────
    # MCTS Core: Expansion
    # ──────────────────────────────────────────────

    async def _expand(
        self,
        node: ThoughtNode,
        original_query: str,
        context: Dict,
    ) -> tuple[List[ThoughtNode], float]:
        """
        Generate N candidate next-thoughts from the current node.

        Uses the ACK cascade for cost-efficient generation.
        """
        # Build the path context from root to this node
        path = self._path_to_node(node)
        chain_so_far = "\n".join(f"Step {i+1}: {n.thought}" for i, n in enumerate(path) if n.thought != original_query)

        is_near_max_depth = node.depth >= (self.config.max_depth - 1)

        prompt = (
            f"ORIGINAL QUESTION: {original_query}\n\n"
            f"{'REASONING SO FAR:' if chain_so_far else 'This is the first reasoning step.'}\n"
            f"{chain_so_far}\n\n"
            f"Generate exactly {self.config.branch_factor} distinct candidate "
            f"{'FINAL ANSWERS (each should be a complete, self-contained response)' if is_near_max_depth else 'next reasoning steps (each exploring a DIFFERENT angle or approach)'}.\n\n"
            "Format each candidate on its own line, prefixed with [CANDIDATE N]:\n"
            f"[CANDIDATE 1]: ...\n"
            f"[CANDIDATE 2]: ...\n"
            f"[CANDIDATE 3]: ...\n"
        )

        try:
            from .council_kernel.engine import get_council_engine
            from .council_kernel.types import CouncilType
            engine = get_council_engine()
            response = await engine.cascade_query("_mcts", prompt, max_budget_usd=0.05)
            cost = response.cost_usd
        except Exception as exc:
            logger.warning(f"MCTS expansion failed: {exc}")
            return [], 0.0

        # Parse candidates from response
        candidates = self._parse_candidates(response.response)
        if not candidates:
            # Fallback: treat entire response as a single candidate
            candidates = [response.response.strip()]

        children = []
        for thought_text in candidates[:self.config.branch_factor]:
            child = ThoughtNode(
                thought=thought_text,
                parent_id=node.id,
                depth=node.depth + 1,
                model_used=response.model,
                cost_usd=cost / max(len(candidates), 1),
                is_terminal=is_near_max_depth,
            )
            self.nodes[child.id] = child
            node.children.append(child.id)
            children.append(child)

        return children, cost

    # ──────────────────────────────────────────────
    # MCTS Core: Simulation (Critic Evaluation)
    # ──────────────────────────────────────────────

    async def _simulate(
        self,
        node: ThoughtNode,
        original_query: str,
        context: Dict,
    ) -> tuple[float, float]:
        """
        Use a critic model to evaluate this reasoning step.

        The critic scores on multiple dimensions:
          - Logical coherence with the chain so far
          - Factual groundedness
          - Relevance to the original query
          - Novel insight (avoids restating previous steps)

        Returns (score, cost).
        """
        path = self._path_to_node(node)
        chain_so_far = "\n".join(
            f"Step {i+1}: {n.thought}" for i, n in enumerate(path[:-1])
            if n.thought != original_query
        )

        critic_prompt = (
            f"ORIGINAL QUESTION: {original_query}\n\n"
            f"REASONING CHAIN SO FAR:\n{chain_so_far or '(first step)'}\n\n"
            f"PROPOSED NEXT THOUGHT:\n{node.thought}\n\n"
            "CRITIC TASK: Score this reasoning step from 0.0 to 1.0 on these axes:\n"
            "• Logical Coherence: Does this step follow from the previous reasoning?\n"
            "• Factual Grounding: Is this step based on verifiable facts, not hallucination?\n"
            "• Query Relevance: Does this step move toward answering the original question?\n"
            "• Novel Insight: Does this add new information (not just restating prior steps)?\n"
            "• Completeness: If this is a final answer, does it fully address the question?\n\n"
            "Respond ONLY with a JSON object:\n"
            '{"coherence": 0.X, "grounding": 0.X, "relevance": 0.X, "novelty": 0.X, '
            '"completeness": 0.X, "overall": 0.X, "critique": "brief explanation"}'
        )

        try:
            from .council_kernel.engine import get_council_engine
            engine = get_council_engine()
            response = await engine.cascade_query("_mcts_critic", critic_prompt, max_budget_usd=0.02)
            cost = response.cost_usd

            # Parse the critic's score
            score = self._parse_critic_score(response.response)
            return score, cost
        except Exception as exc:
            logger.warning(f"MCTS critic failed: {exc}")
            # Fallback: use a heuristic score based on thought quality
            return self._heuristic_score(node.thought), 0.0

    # ──────────────────────────────────────────────
    # MCTS Core: Backpropagation
    # ──────────────────────────────────────────────

    def _backpropagate(self, node: ThoughtNode, value: float) -> None:
        """Walk up from node to root, updating visit counts and total values."""
        current: Optional[ThoughtNode] = node
        while current is not None:
            current.visit_count += 1
            current.total_value += value
            if current.parent_id and current.parent_id in self.nodes:
                current = self.nodes[current.parent_id]
            else:
                break

    # ──────────────────────────────────────────────
    # Path Extraction
    # ──────────────────────────────────────────────

    def _extract_best_path(self) -> List[ThoughtNode]:
        """
        After search is complete, extract the highest-value path from root to a leaf.

        At each node, we pick the child with the highest Q-value (exploitation only,
        no exploration — we're done exploring).
        """
        if not self.root_id or self.root_id not in self.nodes:
            return []

        path = []
        current = self.nodes[self.root_id]
        path.append(current)

        while current.children:
            viable = [
                self.nodes[cid] for cid in current.children
                if cid in self.nodes and not self.nodes[cid].is_pruned
            ]
            if not viable:
                break
            best_child = max(viable, key=lambda c: c.q_value)
            path.append(best_child)
            current = best_child

        return path

    def _path_to_node(self, node: ThoughtNode) -> List[ThoughtNode]:
        """Walk from node up to root, then reverse to get root→node path."""
        path = []
        current: Optional[ThoughtNode] = node
        while current is not None:
            path.append(current)
            if current.parent_id and current.parent_id in self.nodes:
                current = self.nodes[current.parent_id]
            else:
                break
        path.reverse()
        return path

    # ──────────────────────────────────────────────
    # Parsing Helpers
    # ──────────────────────────────────────────────

    def _parse_candidates(self, text: str) -> List[str]:
        """Parse [CANDIDATE N]: ... lines from the generator output."""
        import re
        pattern = r'\[CANDIDATE\s*\d+\]\s*:\s*(.+?)(?=\[CANDIDATE\s*\d+\]|\Z)'
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        return [m.strip() for m in matches if m.strip()]

    def _parse_critic_score(self, text: str) -> float:
        """Extract the 'overall' score from the critic's JSON response."""
        import json
        import re
        # Try to extract JSON from the response
        json_match = re.search(r'\{[^{}]+\}', text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                score = float(data.get("overall", 0.5))
                return max(0.0, min(1.0, score))
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        # Fallback: look for a bare float
        float_match = re.search(r'(?:overall|score)[:\s]*([0-9]*\.?[0-9]+)', text, re.IGNORECASE)
        if float_match:
            return max(0.0, min(1.0, float(float_match.group(1))))
        return 0.5  # Default if parsing fails

    def _heuristic_score(self, thought: str) -> float:
        """Fast heuristic quality score when the critic LLM is unavailable."""
        score = 0.5
        words = len(thought.split())
        # Length adequacy
        if words > 30:
            score += 0.1
        if words > 100:
            score += 0.1
        # Reasoning markers
        reasoning_markers = ["because", "therefore", "however", "specifically", "for example", "evidence"]
        marker_count = sum(1 for m in reasoning_markers if m in thought.lower())
        score += min(0.2, marker_count * 0.05)
        # Penalize hedging
        hedging = ["i think", "maybe", "possibly", "not sure", "i guess"]
        hedge_count = sum(1 for h in hedging if h in thought.lower())
        score -= hedge_count * 0.08

        return max(0.0, min(1.0, score))

    # ──────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────

    async def _persist(self, workspace_id: str, result: Dict) -> None:
        """Persist the MCTS tree to Supabase (best-effort)."""
        try:
            from ..db.supabase_client import get_supabase_client
            get_supabase_client().table("reasoning_chains").insert({
                "id": str(uuid.uuid4()),
                "workspace_id": workspace_id,
                "query": result["query"],
                "conclusion": result["final_answer"],
                "overall_confidence": result["confidence"],
                "steps": result["best_path"],
                "step_count": len(result["best_path"]),
                "decision_id": None,
                "total_cost_usd": result["total_cost_usd"],
                "tree_stats": result["tree_stats"],
            }).execute()
        except Exception as exc:
            logger.warning(f"MCTS persist failed: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# Backward-Compatible Wrappers
# ──────────────────────────────────────────────────────────────────────────────

class ReasoningStep:
    """Backward-compatible step wrapper (used by commands_engine)."""
    def __init__(self, step_type: str, description: str, **kwargs):
        self.id = str(uuid.uuid4())
        self.step_type = step_type
        self.description = description
        self.inputs = kwargs.get("inputs", {})
        self.output = kwargs.get("output")
        self.confidence = kwargs.get("confidence", 0.0)
        self.model = kwargs.get("model")
        self.cost_usd = kwargs.get("cost_usd", 0.0)
        self.duration_ms = kwargs.get("duration_ms", 0)
        self.timestamp = time.time()

    def to_dict(self):
        return {
            "id": self.id, "step_type": self.step_type,
            "description": self.description, "output": self.output,
            "confidence": self.confidence, "model": self.model,
        }


class ReasoningChain:
    """Backward-compatible chain interface. Wraps MCTS under the hood."""
    def __init__(self, workspace_id: str, decision_id: str, query: str):
        self.id = str(uuid.uuid4())
        self.workspace_id = workspace_id
        self.decision_id = decision_id
        self.query = query
        self.steps: List[ReasoningStep] = []
        self.conclusion: Optional[str] = None
        self.overall_confidence: float = 0.0
        self.total_cost: float = 0.0
        self.created_at = time.time()

    def add_step(self, step_type: str, description: str, **kwargs) -> ReasoningStep:
        step = ReasoningStep(step_type, description, **kwargs)
        self.steps.append(step)
        self.total_cost += kwargs.get("cost_usd", 0.0)
        return step

    def set_conclusion(self, conclusion: str, confidence: float = 0.0):
        self.conclusion = conclusion
        self.overall_confidence = confidence or (
            sum(s.confidence for s in self.steps) / max(len(self.steps), 1)
        )

    def to_dict(self):
        return {
            "id": self.id, "workspace_id": self.workspace_id,
            "decision_id": self.decision_id, "query": self.query,
            "steps": [s.to_dict() for s in self.steps],
            "conclusion": self.conclusion,
            "overall_confidence": self.overall_confidence,
            "total_cost_usd": self.total_cost,
            "step_count": len(self.steps), "created_at": self.created_at,
        }

    async def save(self) -> bool:
        try:
            from ..db.supabase_client import get_supabase_client
            get_supabase_client().table("reasoning_chains").insert(self.to_dict()).execute()
            return True
        except Exception as exc:
            logger.warning(f"Reasoning chain save failed: {exc}")
            return False


class ReasoningChainService:
    """Backward-compatible service. Now delegates heavy reasoning to MCTS."""

    def create(self, workspace_id: str, decision_id: str, query: str) -> ReasoningChain:
        return ReasoningChain(workspace_id, decision_id, query)

    async def reason_with_mcts(
        self,
        workspace_id: str,
        query: str,
        config: Optional[MCTSConfig] = None,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Run full MCTS reasoning (the cutting-edge path)."""
        reasoner = MCTSReasoner(config)
        return await reasoner.reason(workspace_id, query, context)

    async def get_by_decision(self, decision_id: str) -> Optional[Dict]:
        try:
            from ..db.supabase_client import get_supabase_client
            result = (
                get_supabase_client().table("reasoning_chains")
                .select("*").eq("decision_id", decision_id).single().execute()
            )
            return result.data
        except Exception:
            return None

    async def get_by_workspace(self, workspace_id: str, limit: int = 20) -> List[Dict]:
        try:
            from ..db.supabase_client import get_supabase_client
            result = (
                get_supabase_client().table("reasoning_chains")
                .select("id,decision_id,query,conclusion,overall_confidence,step_count,created_at,tree_stats")
                .eq("workspace_id", workspace_id)
                .order("created_at", desc=True).limit(limit).execute()
            )
            return result.data or []
        except Exception:
            return []


# Singleton
_reasoning_service: Optional[ReasoningChainService] = None

def get_reasoning_service() -> ReasoningChainService:
    global _reasoning_service
    if _reasoning_service is None:
        _reasoning_service = ReasoningChainService()
    return _reasoning_service
