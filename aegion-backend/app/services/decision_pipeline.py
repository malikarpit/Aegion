"""
Decision Pipeline — Phase 44 (Elevated): State-Graph Execution Engine.

Replaces the rigid linear stage array with a Directed Acyclic Graph (DAG)
of pipeline nodes connected by conditional edges — inspired by LangGraph.

Why DAGs beat linear pipelines:
  - Conditional branching: "If sentinel finds a critical vuln, skip debate,
    go straight to BLOCK."
  - Self-healing loops: "If peer review disagrees with debate, loop back to
    debate with the critique as new context."
  - Parallel fan-out: "Run sentinel AND persona analysis simultaneously,
    merge results before rubric scoring."
  - Short-circuit:  "If rules engine blocks, stop immediately."
  - State machine: Each node reads from and writes to a shared state dict,
    enabling downstream stages to react to upstream outputs.

Architecture:
  PipelineNode  — A named processing unit with an execute(state) → state method.
  PipelineEdge  — A directed connection with an optional condition(state) → bool.
  StateGraph    — The DAG definition with nodes, edges, and an entry point.
  DAGExecutor   — Walks the graph, managing state and enforcing invariants.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple

from ..core.logging import logger


# ──────────────────────────────────────────────────────────────────────────────
# Core Types
# ──────────────────────────────────────────────────────────────────────────────

class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    SHORT_CIRCUITED = "short_circuited"


@dataclass
class StageResult:
    """Result from executing a single pipeline node."""
    node_name: str
    status: NodeStatus
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    cost_usd: float = 0.0
    latency_ms: int = 0
    retry_count: int = 0


# Condition function type: takes the current state, returns True if the edge should be followed
ConditionFn = Callable[[Dict[str, Any]], bool]

# Node executor function type: takes (workspace_id, query, state) → updated state
NodeExecutorFn = Callable[
    [str, str, Dict[str, Any]],
    Coroutine[Any, Any, Dict[str, Any]],
]


@dataclass
class PipelineNode:
    """A processing unit in the DAG."""
    name: str
    executor: NodeExecutorFn              # Async function to execute
    max_retries: int = 1                  # How many times to retry on failure
    timeout_seconds: float = 120.0        # Hard timeout
    can_short_circuit: bool = False       # If True, can halt the entire pipeline
    is_parallel_safe: bool = False        # If True, can run in parallel with other safe nodes


@dataclass
class PipelineEdge:
    """A directed connection between two nodes."""
    source: str                           # Source node name
    target: str                           # Target node name
    condition: Optional[ConditionFn] = None  # Optional guard condition
    priority: int = 0                     # Higher = evaluated first when multiple edges leave a node
    label: str = ""                       # Human-readable description of the condition


@dataclass
class StateGraph:
    """
    The DAG definition: a compile-time structure.

    Building a graph:
        graph = StateGraph(entry="analyze")
        graph.add_node(PipelineNode("analyze", analyze_fn))
        graph.add_node(PipelineNode("sentinel", sentinel_fn, can_short_circuit=True))
        graph.add_edge(PipelineEdge("analyze", "sentinel"))
        graph.add_edge(PipelineEdge("sentinel", "debate", condition=lambda s: s.get("risk_score", 0) < 0.8))
        graph.add_edge(PipelineEdge("sentinel", "__END__", condition=lambda s: s.get("risk_score", 0) >= 0.8, label="critical_risk_block"))
    """
    entry: str                            # Name of the first node to execute
    nodes: Dict[str, PipelineNode] = field(default_factory=dict)
    edges: List[PipelineEdge] = field(default_factory=list)

    def add_node(self, node: PipelineNode) -> "StateGraph":
        self.nodes[node.name] = node
        return self

    def add_edge(self, edge: PipelineEdge) -> "StateGraph":
        self.edges.append(edge)
        return self

    def add_conditional_edges(
        self,
        source: str,
        branches: Dict[str, Tuple[ConditionFn, str]],
    ) -> "StateGraph":
        """
        Add multiple conditional edges from a single source.

        branches: {"label": (condition_fn, target_name), ...}
        """
        for label, (cond, target) in branches.items():
            self.add_edge(PipelineEdge(source, target, condition=cond, label=label))
        return self

    def get_outgoing_edges(self, node_name: str) -> List[PipelineEdge]:
        """Get all edges leaving a node, sorted by priority (descending)."""
        edges = [e for e in self.edges if e.source == node_name]
        edges.sort(key=lambda e: -e.priority)
        return edges

    def validate(self) -> List[str]:
        """Validate the graph structure. Returns list of error messages."""
        errors = []
        if self.entry not in self.nodes:
            errors.append(f"Entry node '{self.entry}' not found in graph nodes.")
        for edge in self.edges:
            if edge.source not in self.nodes:
                errors.append(f"Edge source '{edge.source}' not found in graph nodes.")
            if edge.target != "__END__" and edge.target not in self.nodes:
                errors.append(f"Edge target '{edge.target}' not found in graph nodes.")
        # Check for unreachable nodes
        reachable = self._reachable_from(self.entry)
        for name in self.nodes:
            if name not in reachable and name != self.entry:
                errors.append(f"Node '{name}' is unreachable from entry '{self.entry}'.")
        return errors

    def _reachable_from(self, start: str) -> Set[str]:
        visited: Set[str] = set()
        queue = [start]
        while queue:
            current = queue.pop(0)
            if current in visited or current == "__END__":
                continue
            visited.add(current)
            for edge in self.get_outgoing_edges(current):
                queue.append(edge.target)
        return visited


# ──────────────────────────────────────────────────────────────────────────────
# DAG Executor
# ──────────────────────────────────────────────────────────────────────────────

class DAGExecutor:
    """
    Executes a StateGraph with state management and conditional routing.

    Invariants:
      - Each node executes at most once (unless loop-back edges re-queue it).
      - A node's output is merged into the shared state dict.
      - Edges are evaluated in priority order; the first matching edge is followed.
      - If no edge matches, execution stops (implicit __END__).
      - If a short-circuit node sets state["__halt__"] = True, execution stops.
      - Maximum 20 node executions to prevent infinite loops.
    """

    MAX_EXECUTIONS = 20  # Safety limit against infinite loops

    def __init__(self, graph: StateGraph) -> None:
        self.graph = graph
        errors = graph.validate()
        if errors:
            raise ValueError(f"Invalid StateGraph: {'; '.join(errors)}")

    async def execute(
        self,
        workspace_id: str,
        query: str,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the DAG from entry to __END__.

        Returns:
            query:           Original query
            state:           Final state dict after all nodes
            execution_trace: Ordered list of StageResults
            total_cost_usd:  Sum of costs
            total_latency_ms: Wall-clock time
            halted:          True if short-circuited
            halt_reason:     Reason if halted
        """
        start = time.monotonic()
        state: Dict[str, Any] = dict(initial_state or {})
        state["__query__"] = query
        state["__workspace_id__"] = workspace_id

        trace: List[StageResult] = []
        visited: Dict[str, int] = {}  # node_name → execution count
        current_node_name = self.graph.entry
        execution_count = 0

        while current_node_name and current_node_name != "__END__":
            # Safety: prevent infinite loops
            execution_count += 1
            if execution_count > self.MAX_EXECUTIONS:
                logger.warning(f"DAG executor hit max executions ({self.MAX_EXECUTIONS})")
                break

            # Track per-node visits (allow up to 2 for loop-backs)
            visited[current_node_name] = visited.get(current_node_name, 0) + 1
            if visited[current_node_name] > 2:
                logger.warning(f"Node '{current_node_name}' visited > 2 times, breaking loop")
                break

            node = self.graph.nodes[current_node_name]
            stage_start = time.monotonic()
            result = await self._execute_node(node, workspace_id, query, state)
            result.latency_ms = int((time.monotonic() - stage_start) * 1000)
            trace.append(result)

            # Merge node output into state
            if result.status == NodeStatus.COMPLETED and result.output:
                state[f"stage_{node.name}"] = result.output
                # Also merge top-level keys for easier downstream access
                for k, v in result.output.items():
                    if not k.startswith("_"):
                        state[k] = v

            # Check for short-circuit
            if state.get("__halt__"):
                logger.info(f"Pipeline halted by node '{current_node_name}': {state.get('__halt_reason__', 'unspecified')}")
                break

            # Find the next node via edge evaluation
            current_node_name = self._resolve_next(current_node_name, state)

        latency = int((time.monotonic() - start) * 1000)
        total_cost = sum(r.cost_usd for r in trace)

        return {
            "query": query,
            "state": {k: v for k, v in state.items() if not k.startswith("__")},
            "execution_trace": [
                {
                    "node": r.node_name, "status": r.status.value,
                    "output": r.output, "error": r.error,
                    "cost_usd": r.cost_usd, "latency_ms": r.latency_ms,
                    "retries": r.retry_count,
                }
                for r in trace
            ],
            "total_cost_usd": round(total_cost, 6),
            "total_latency_ms": latency,
            "halted": bool(state.get("__halt__")),
            "halt_reason": state.get("__halt_reason__"),
        }

    async def _execute_node(
        self,
        node: PipelineNode,
        workspace_id: str,
        query: str,
        state: Dict[str, Any],
    ) -> StageResult:
        """Execute a single node with retry and timeout."""
        last_error = None
        for attempt in range(node.max_retries):
            try:
                result = await asyncio.wait_for(
                    node.executor(workspace_id, query, state),
                    timeout=node.timeout_seconds,
                )
                return StageResult(
                    node_name=node.name,
                    status=NodeStatus.COMPLETED,
                    output=result or {},
                    cost_usd=result.get("cost_usd", 0.0) if result else 0.0,
                    retry_count=attempt,
                )
            except asyncio.TimeoutError:
                last_error = f"Timeout after {node.timeout_seconds}s"
                logger.warning(f"Node '{node.name}' timed out (attempt {attempt+1}/{node.max_retries})")
            except Exception as exc:
                last_error = str(exc)
                logger.warning(f"Node '{node.name}' failed (attempt {attempt+1}): {exc}")

        return StageResult(
            node_name=node.name,
            status=NodeStatus.FAILED,
            error=last_error,
            retry_count=node.max_retries,
        )

    def _resolve_next(self, current: str, state: Dict[str, Any]) -> Optional[str]:
        """Evaluate outgoing edges and return the next node name (or None)."""
        for edge in self.graph.get_outgoing_edges(current):
            if edge.condition is None:
                return edge.target  # Unconditional edge
            try:
                if edge.condition(state):
                    return edge.target
            except Exception as exc:
                logger.warning(f"Edge condition '{edge.label}' from '{current}' failed: {exc}")
        return None  # No matching edge → implicit __END__


# ──────────────────────────────────────────────────────────────────────────────
# Built-in Stage Executors
# ──────────────────────────────────────────────────────────────────────────────

async def _stage_analyze(workspace_id: str, query: str, state: Dict) -> Dict:
    """Gather workspace evidence."""
    try:
        from .council_kernel.evidence import get_evidence_manager
        ev = get_evidence_manager()
        evidence = await ev.gather_evidence(workspace_id, query)
        formatted = ev.format_for_prompt(evidence)
        return {"evidence": formatted, "sources": list(evidence.keys()), "cost_usd": 0.0}
    except Exception:
        return {"evidence": "", "sources": [], "cost_usd": 0.0}


async def _stage_debate(workspace_id: str, query: str, state: Dict) -> Dict:
    """Run multi-model council debate."""
    from .council_kernel.engine import get_council_engine
    from .council_kernel.types import CouncilType
    enriched = query
    if state.get("evidence"):
        enriched += f"\n\nCONTEXT:\n{state['evidence']}"
    # If this is a loop-back, inject the critique from peer review
    if state.get("peer_review_critique"):
        enriched += f"\n\nPEER REVIEW FEEDBACK (address these concerns):\n{state['peer_review_critique']}"
    engine = get_council_engine()
    result = await engine.consult(workspace_id, enriched, CouncilType.PARENT, state)
    return {
        "synthesis": result.synthesis,
        "consensus": result.consensus_score,
        "dissenting_views": result.dissenting_views,
        "cost_usd": result.total_cost_usd,
    }


async def _stage_peer_review(workspace_id: str, query: str, state: Dict) -> Dict:
    """Adversarial peer review of the debate synthesis."""
    from .council_kernel.engine import get_council_engine
    from .council_kernel.peer_review import PeerReviewEngine
    engine = get_council_engine()
    slots = await engine.model_router.select_models(
        workspace_id, None, None,
    )
    slots = slots[:3]  # Top 3 models
    if not slots:
        return {"review_passed": True, "cost_usd": 0.0}
    pr = PeerReviewEngine(engine.model_router)
    synthesis_to_review = state.get("synthesis", query)
    result = await pr.run(synthesis_to_review, slots)
    # Determine if review passes or requires loop-back
    review_passed = result.consensus_score >= 0.65
    critique = ""
    if not review_passed and result.dissenting_views:
        critique = "\n".join(result.dissenting_views[:3])
    return {
        "review_passed": review_passed,
        "review_consensus": result.consensus_score,
        "peer_review_critique": critique,
        "review_synthesis": result.synthesis,
        "cost_usd": result.total_cost_usd,
    }


async def _stage_rubric(workspace_id: str, query: str, state: Dict) -> Dict:
    """Score the current synthesis against quality rubric."""
    from .council_kernel.rubric import get_rubric_engine
    text = state.get("synthesis", state.get("review_synthesis", query))
    scores = await get_rubric_engine().score(text, rubric_name="architecture")
    return {"rubric_scores": scores, "cost_usd": 0.0}


async def _stage_persona(workspace_id: str, query: str, state: Dict) -> Dict:
    """Expert persona debate."""
    from .council_kernel.engine import get_council_engine
    from .council_kernel.persona import get_persona_engine
    engine = get_council_engine()
    slots = await engine.model_router.select_models(workspace_id, None, None)
    pe = get_persona_engine()
    result = await pe.debate_with_personas(
        query, ["security_auditor", "cost_analyst", "governance_advisor", "devils_advocate"],
        slots, engine.model_router,
    )
    return {"personas": result, "cost_usd": 0.0}


async def _stage_rules(workspace_id: str, query: str, state: Dict) -> Dict:
    """Evaluate governance rules. Can halt pipeline."""
    from .rules_engine import get_rules_engine
    triggered = await get_rules_engine().evaluate(workspace_id, state)
    blocked = any(r.get("action") == "block" for r in triggered)
    if blocked:
        state["__halt__"] = True
        state["__halt_reason__"] = f"Rules engine blocked: {[r.get('rule_name') for r in triggered if r.get('action') == 'block']}"
    return {"triggered_rules": triggered, "blocked": blocked, "cost_usd": 0.0}


async def _stage_sentinel(workspace_id: str, query: str, state: Dict) -> Dict:
    """Security scan. Can halt pipeline on critical risk."""
    from .sentinel.council_bridge import get_sentinel_bridge
    result = await get_sentinel_bridge().analyze_change(
        workspace_id, {"content": state.get("synthesis", query), "files": []},
    )
    risk_score = result.get("risk_score", 0.0)
    if risk_score >= 0.9:  # Critical risk → halt
        state["__halt__"] = True
        state["__halt_reason__"] = f"Sentinel critical risk: {risk_score}"
    return {
        "risk_score": risk_score,
        "signals": result.get("signals", []),
        "recommended_tier": result.get("recommended_tier", "T0"),
        "cost_usd": 0.0,
    }


async def _stage_recommend(workspace_id: str, query: str, state: Dict) -> Dict:
    """Synthesize all stage outputs into a final recommendation."""
    from .council_kernel.engine import get_council_engine
    from .council_kernel.types import CouncilType

    # Build a rich context from all prior stages
    parts = [f"Original Query: {query}"]
    if state.get("evidence"):
        parts.append(f"Evidence: {str(state['evidence'])[:800]}")
    if state.get("synthesis"):
        parts.append(f"Council Synthesis: {state['synthesis'][:800]}")
    if state.get("review_synthesis"):
        parts.append(f"Peer Review: {state['review_synthesis'][:500]}")
    if state.get("risk_score") is not None:
        parts.append(f"Security Risk: {state['risk_score']}")
    if state.get("rubric_scores"):
        parts.append(f"Rubric Scores: {state['rubric_scores']}")
    if state.get("personas"):
        parts.append(f"Expert Personas: {str(state['personas'])[:500]}")

    # Use the council to produce a final synthesis
    context_block = "\n\n".join(parts)
    final_prompt = (
        f"SYNTHESIS TASK: Based on all the analysis below, produce a clear, "
        f"actionable final recommendation.\n\n{context_block}"
    )
    engine = get_council_engine()
    result = await engine.cascade_query(workspace_id, final_prompt, max_budget_usd=0.10)
    return {
        "recommendation": result.response,
        "confidence": result.confidence,
        "cost_usd": result.cost_usd,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Pre-built Graph Templates
# ──────────────────────────────────────────────────────────────────────────────

def build_standard_graph() -> StateGraph:
    """Standard decision pipeline: analyze → debate → recommend."""
    g = StateGraph(entry="analyze")
    g.add_node(PipelineNode("analyze", _stage_analyze))
    g.add_node(PipelineNode("debate", _stage_debate))
    g.add_node(PipelineNode("rubric", _stage_rubric))
    g.add_node(PipelineNode("recommend", _stage_recommend))
    g.add_edge(PipelineEdge("analyze", "debate"))
    g.add_edge(PipelineEdge("debate", "rubric"))
    g.add_edge(PipelineEdge("rubric", "recommend"))
    g.add_edge(PipelineEdge("recommend", "__END__"))
    return g


def build_security_graph() -> StateGraph:
    """Security-focused: analyze → sentinel → (block or continue to review)."""
    g = StateGraph(entry="analyze")
    g.add_node(PipelineNode("analyze", _stage_analyze))
    g.add_node(PipelineNode("sentinel", _stage_sentinel, can_short_circuit=True))
    g.add_node(PipelineNode("peer_review", _stage_peer_review))
    g.add_node(PipelineNode("rubric", _stage_rubric))
    g.add_node(PipelineNode("recommend", _stage_recommend))
    g.add_edge(PipelineEdge("analyze", "sentinel"))
    # If critical risk, halt (sentinel sets __halt__)
    # Otherwise continue to peer review
    g.add_edge(PipelineEdge("sentinel", "peer_review",
                             condition=lambda s: s.get("risk_score", 0) < 0.9,
                             label="risk_acceptable"))
    g.add_edge(PipelineEdge("sentinel", "__END__",
                             condition=lambda s: s.get("risk_score", 0) >= 0.9,
                             label="critical_risk_halt",
                             priority=1))
    g.add_edge(PipelineEdge("peer_review", "rubric"))
    g.add_edge(PipelineEdge("rubric", "recommend"))
    g.add_edge(PipelineEdge("recommend", "__END__"))
    return g


def build_architecture_graph() -> StateGraph:
    """
    Architecture review with self-healing loop.

    If peer review consensus < 0.65, loops back to debate with the critique
    injected into context. Maximum 2 iterations.
    """
    g = StateGraph(entry="analyze")
    g.add_node(PipelineNode("analyze", _stage_analyze))
    g.add_node(PipelineNode("persona", _stage_persona))
    g.add_node(PipelineNode("debate", _stage_debate))
    g.add_node(PipelineNode("peer_review", _stage_peer_review))
    g.add_node(PipelineNode("rubric", _stage_rubric))
    g.add_node(PipelineNode("recommend", _stage_recommend))

    g.add_edge(PipelineEdge("analyze", "persona"))
    g.add_edge(PipelineEdge("persona", "debate"))
    g.add_edge(PipelineEdge("debate", "peer_review"))

    # Self-healing loop: if review fails, go back to debate with critique
    g.add_edge(PipelineEdge("peer_review", "debate",
                             condition=lambda s: not s.get("review_passed", True),
                             label="review_failed_loopback",
                             priority=1))
    # If review passes, continue to rubric
    g.add_edge(PipelineEdge("peer_review", "rubric",
                             condition=lambda s: s.get("review_passed", True),
                             label="review_passed"))

    g.add_edge(PipelineEdge("rubric", "recommend"))
    g.add_edge(PipelineEdge("recommend", "__END__"))
    return g


def build_quick_graph() -> StateGraph:
    """Quick pipeline: analyze → recommend (no debate)."""
    g = StateGraph(entry="analyze")
    g.add_node(PipelineNode("analyze", _stage_analyze))
    g.add_node(PipelineNode("recommend", _stage_recommend))
    g.add_edge(PipelineEdge("analyze", "recommend"))
    g.add_edge(PipelineEdge("recommend", "__END__"))
    return g


def build_governed_graph() -> StateGraph:
    """Full governance: analyze → rules → sentinel → debate → peer_review → rubric → recommend."""
    g = StateGraph(entry="analyze")
    g.add_node(PipelineNode("analyze", _stage_analyze))
    g.add_node(PipelineNode("rules", _stage_rules, can_short_circuit=True))
    g.add_node(PipelineNode("sentinel", _stage_sentinel, can_short_circuit=True))
    g.add_node(PipelineNode("debate", _stage_debate))
    g.add_node(PipelineNode("peer_review", _stage_peer_review))
    g.add_node(PipelineNode("rubric", _stage_rubric))
    g.add_node(PipelineNode("recommend", _stage_recommend))

    g.add_edge(PipelineEdge("analyze", "rules"))
    # Rules can halt
    g.add_edge(PipelineEdge("rules", "sentinel",
                             condition=lambda s: not s.get("blocked", False),
                             label="rules_passed"))
    g.add_edge(PipelineEdge("rules", "__END__",
                             condition=lambda s: s.get("blocked", False),
                             label="rules_blocked",
                             priority=1))
    g.add_edge(PipelineEdge("sentinel", "debate",
                             condition=lambda s: s.get("risk_score", 0) < 0.9))
    g.add_edge(PipelineEdge("sentinel", "__END__",
                             condition=lambda s: s.get("risk_score", 0) >= 0.9,
                             priority=1))
    g.add_edge(PipelineEdge("debate", "peer_review"))
    g.add_edge(PipelineEdge("peer_review", "debate",
                             condition=lambda s: not s.get("review_passed", True),
                             label="review_loopback",
                             priority=1))
    g.add_edge(PipelineEdge("peer_review", "rubric",
                             condition=lambda s: s.get("review_passed", True)))
    g.add_edge(PipelineEdge("rubric", "recommend"))
    g.add_edge(PipelineEdge("recommend", "__END__"))
    return g


# Template registry
PIPELINE_TEMPLATES = {
    "standard": build_standard_graph,
    "security_review": build_security_graph,
    "architecture": build_architecture_graph,
    "quick": build_quick_graph,
    "governed": build_governed_graph,
}


# ──────────────────────────────────────────────────────────────────────────────
# High-Level Service
# ──────────────────────────────────────────────────────────────────────────────

class DecisionPipeline:
    """
    High-level service for executing decision pipelines.

    Backward-compatible with the original interface while exposing the full
    DAG power for new consumers.
    """

    async def execute(
        self,
        workspace_id: str,
        query: str,
        template_name: str = "standard",
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a named pipeline template (backward-compatible)."""
        builder = PIPELINE_TEMPLATES.get(template_name)
        if not builder:
            raise ValueError(
                f"Unknown pipeline template: {template_name}. "
                f"Available: {list(PIPELINE_TEMPLATES.keys())}"
            )
        graph = builder()
        executor = DAGExecutor(graph)
        return await executor.execute(workspace_id, query, context)

    async def execute_graph(
        self,
        workspace_id: str,
        query: str,
        graph: StateGraph,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a custom StateGraph (for advanced users building their own DAGs)."""
        executor = DAGExecutor(graph)
        return await executor.execute(workspace_id, query, context)


# Singleton
_decision_pipeline: Optional[DecisionPipeline] = None

def get_decision_pipeline() -> DecisionPipeline:
    global _decision_pipeline
    if _decision_pipeline is None:
        _decision_pipeline = DecisionPipeline()
    return _decision_pipeline
