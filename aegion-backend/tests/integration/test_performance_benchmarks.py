"""
Aegion Performance Benchmarks.

Phase 5: Integration tests for performance validation.
Tests key operations under load and measures response times.
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

# Core imports
from app.core.security import AuthorityContext, Role
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.contracts.decision_intent import (
    DecisionIntent, ImpactLevel, ReversibilityLevel, 
    ReasoningPhase, DecisionTier
)
from app.services.archon import ArchonGates
from app.services.sentinel import RiskEngine
from app.services.noesis import GraphService, CognitiveSafetyService
from app.adapters.memory_graph import InMemoryKnowledgeGraph
from app.services.council import CouncilService
from app.ports.knowledge_graph import GraphNodeType


class BenchmarkResult:
    """Result of a benchmark run."""
    def __init__(self, name: str, iterations: int, times: List[float]):
        self.name = name
        self.iterations = iterations
        self.times = times
        self.total_time = sum(times)
        self.avg_time = self.total_time / len(times) if times else 0
        self.min_time = min(times) if times else 0
        self.max_time = max(times) if times else 0
    
    def __str__(self):
        return (
            f"{self.name}: {self.iterations} iterations, "
            f"avg={self.avg_time*1000:.2f}ms, "
            f"min={self.min_time*1000:.2f}ms, "
            f"max={self.max_time*1000:.2f}ms, "
            f"total={self.total_time:.2f}s"
        )


def benchmark(func, iterations: int = 100) -> BenchmarkResult:
    """Run a function multiple times and measure performance."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append(end - start)
    return BenchmarkResult(func.__name__, iterations, times)


async def async_benchmark(func, iterations: int = 100) -> BenchmarkResult:
    """Run an async function multiple times and measure performance."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        await func()
        end = time.perf_counter()
        times.append(end - start)
    return BenchmarkResult(func.__name__, iterations, times)


# ========== Benchmark Tests ==========


def test_archon_tier_classification_benchmark():
    """Benchmark: Archon tier classification throughput."""
    archon = ArchonGates()
    
    def classify():
        archon.classify_tier(
            ImpactLevel.CROSS_MODULE,
            ReversibilityLevel.MODERATE,
            ["auth", "api"]
        )
    
    result = benchmark(classify, iterations=1000)
    print(f"\n{result}")
    
    # Assert: Should complete 1000 classifications in under 1 second
    assert result.total_time < 1.0, f"Too slow: {result.total_time}s"
    # Assert: Average under 1ms
    assert result.avg_time < 0.001, f"Avg too slow: {result.avg_time*1000}ms"


def test_decision_intent_creation_benchmark():
    """Benchmark: DecisionIntent model creation."""
    
    def create_intent():
        DecisionIntent(
            intent_id=f"intent-{time.time_ns()}",
            session_id="sess-001",
            title="Test Intent",
            description="Performance test",
            impact_level=ImpactLevel.LOCAL,
            reversibility=ReversibilityLevel.EASY,
            calculated_tier=DecisionTier.T1,
            affected_modules=["test"],
            affected_files=["test.py"],
            reasoning=ReasoningPhase(
                problem_framing="Testing performance",
                assumptions=["Fast is good"],
                constraints=["Must be efficient"],
                alternatives_considered=[]
            ),
            origin="human",
            proposed_by="user-001",
            proposed_at=datetime.now(timezone.utc)
        )
    
    result = benchmark(create_intent, iterations=500)
    print(f"\n{result}")
    
    # Assert: Under 2ms average for model creation
    assert result.avg_time < 0.002, f"Model creation too slow: {result.avg_time*1000}ms"


def test_risk_engine_benchmark_sync():
    """Benchmark: Risk score calculation throughput."""
    asyncio.run(_run_risk_benchmark())


async def _run_risk_benchmark():
    risk_engine = RiskEngine()
    
    async def calculate():
        await risk_engine.calculate_risk_score(
            workspace_id="ws-benchmark",
            decisions=[{"tier": "T1"}, {"tier": "T2"}],
            evidence=[{"is_stale": False}]
        )
    
    result = await async_benchmark(calculate, iterations=200)
    print(f"\n{result}")
    
    # Assert: Under 5ms average
    assert result.avg_time < 0.005, f"Risk calc too slow: {result.avg_time*1000}ms"


def test_cognitive_load_assessment_benchmark_sync():
    """Benchmark: Cognitive load assessment."""
    asyncio.run(_run_cognitive_benchmark())


async def _run_cognitive_benchmark():
    cognitive = CognitiveSafetyService()
    
    async def assess():
        await cognitive.assess_cognitive_load(
            user_id="user-benchmark",
            recent_decisions=[{"complexity": 5}] * 10,
            hours_active=2.0
        )
    
    result = await async_benchmark(assess, iterations=200)
    print(f"\n{result}")
    
    # Assert: Under 2ms average
    assert result.avg_time < 0.002, f"Cognitive assessment too slow: {result.avg_time*1000}ms"


def test_knowledge_graph_operations_benchmark_sync():
    """Benchmark: Knowledge graph add/query operations."""
    asyncio.run(_run_graph_benchmark())


async def _run_graph_benchmark():
    graph = InMemoryKnowledgeGraph()
    await graph.connect()
    
    counter = [0]
    
    async def add_and_query():
        counter[0] += 1
        node_id = f"bench-{counter[0]}"
        await graph.add_node(GraphNodeType.DECISION, node_id, {"test": True})
        await graph.get_node(node_id)
    
    result = await async_benchmark(add_and_query, iterations=500)
    print(f"\n{result}")
    
    # Assert: Under 1ms average for add+query
    assert result.avg_time < 0.001, f"Graph ops too slow: {result.avg_time*1000}ms"


def test_council_session_benchmark_sync():
    """Benchmark: Council session with mock opinions."""
    asyncio.run(_run_council_benchmark())


async def _run_council_benchmark():
    council = CouncilService()  # No LLM, uses mocks
    
    counter = [0]
    
    async def convene():
        counter[0] += 1
        proposal = DecisionIntent(
            intent_id=f"bench-prop-{counter[0]}",
            session_id="sess-bench",
            title="Benchmark Proposal",
            description="Testing council performance",
            impact_level=ImpactLevel.LOCAL,
            reversibility=ReversibilityLevel.EASY,
            calculated_tier=DecisionTier.T1,
            affected_modules=["benchmark"],
            affected_files=[],
            reasoning=ReasoningPhase(
                problem_framing="Speed test",
                assumptions=[],
                constraints=[],
                alternatives_considered=[]
            ),
            origin="human",
            proposed_by="user-bench",
            proposed_at=datetime.now(timezone.utc)
        )
        await council.convene_session(proposal, "ws-bench")
    
    result = await async_benchmark(convene, iterations=50)
    print(f"\n{result}")
    
    # Assert: Under 50ms average for mock council (3 members)
    assert result.avg_time < 0.05, f"Council session too slow: {result.avg_time*1000}ms"


def test_concurrent_workspace_operations_benchmark():
    """Benchmark: Concurrent workspace member operations."""
    
    def create_workspace():
        workspace = Workspace(
            workspace_id=f"ws-{time.time_ns()}",
            name="Benchmark Workspace",
            owner_id="owner-001"
        )
        members = [
            WorkspaceMember(user_id=f"user-{i}", role=WorkspaceRole.DEVELOPER)
            for i in range(10)
        ]
        return workspace, members
    
    result = benchmark(create_workspace, iterations=100)
    print(f"\n{result}")
    
    # Assert: Under 5ms average for workspace + 10 members
    assert result.avg_time < 0.005, f"Workspace creation too slow: {result.avg_time*1000}ms"


def test_full_proposal_flow_benchmark_sync():
    """Benchmark: Complete proposal → classification → validation flow."""
    asyncio.run(_run_full_flow_benchmark())


async def _run_full_flow_benchmark():
    archon = ArchonGates()
    risk_engine = RiskEngine()
    cognitive = CognitiveSafetyService()
    
    counter = [0]
    
    async def full_flow():
        counter[0] += 1
        
        # Create proposal
        proposal = DecisionIntent(
            intent_id=f"flow-{counter[0]}",
            session_id="sess-flow",
            title="Flow Test Proposal",
            description="Testing full flow",
            impact_level=ImpactLevel.CROSS_MODULE,
            reversibility=ReversibilityLevel.MODERATE,
            calculated_tier=DecisionTier.T2,
            affected_modules=["auth", "api"],
            reasoning=ReasoningPhase(
                problem_framing="Performance validation",
                assumptions=["System is fast"],
                constraints=[],
                alternatives_considered=[]
            ),
            origin="human",
            proposed_by="user-flow",
            proposed_at=datetime.now(timezone.utc)
        )
        
        # Classify tier
        tier = archon.classify_tier(
            proposal.impact_level,
            proposal.reversibility,
            proposal.affected_modules
        )
        
        # Calculate risk
        risk = await risk_engine.calculate_risk_score(
            workspace_id="ws-flow",
            decisions=[],
            evidence=[]
        )
        
        # Check cognitive load
        load = await cognitive.assess_cognitive_load(
            user_id="approver-001",
            recent_decisions=[],
            hours_active=1.0
        )
        
        return tier, risk, load
    
    result = await async_benchmark(full_flow, iterations=100)
    print(f"\n{result}")
    
    # Assert: Full flow under 10ms average
    assert result.avg_time < 0.01, f"Full flow too slow: {result.avg_time*1000}ms"


# ========== Performance Summary ==========


def test_performance_summary_sync():
    """Generate performance summary for all benchmarks."""
    asyncio.run(_generate_summary())


async def _generate_summary():
    print("\n" + "="*60)
    print("          AEGION PERFORMANCE BENCHMARK SUMMARY")
    print("="*60 + "\n")
    
    results = []
    
    # Archon
    archon = ArchonGates()
    result = benchmark(
        lambda: archon.classify_tier(
            ImpactLevel.CROSS_MODULE,
            ReversibilityLevel.MODERATE,
            ["auth"]
        ),
        iterations=1000
    )
    result.name = "Archon Classification"
    results.append(result)
    
    # Risk Engine
    risk_engine = RiskEngine()
    result = await async_benchmark(
        lambda: risk_engine.calculate_risk_score("ws", [], []),
        iterations=500
    )
    result.name = "Risk Calculation"
    results.append(result)
    
    # Cognitive
    cognitive = CognitiveSafetyService()
    result = await async_benchmark(
        lambda: cognitive.assess_cognitive_load("u", None, [], 1.0),
        iterations=500
    )
    result.name = "Cognitive Assessment"
    results.append(result)
    
    # Graph
    graph = InMemoryKnowledgeGraph()
    await graph.connect()
    counter = [0]
    async def graph_op():
        counter[0] += 1
        await graph.add_node(GraphNodeType.DECISION, f"n-{counter[0]}", {})
    result = await async_benchmark(graph_op, iterations=500)
    result.name = "Graph Add Node"
    results.append(result)
    
    # Print summary
    print(f"{'Operation':<25} {'Iterations':>10} {'Avg (ms)':>10} {'Min':>10} {'Max':>10}")
    print("-" * 65)
    for r in results:
        print(f"{r.name:<25} {r.iterations:>10} {r.avg_time*1000:>10.3f} {r.min_time*1000:>10.3f} {r.max_time*1000:>10.3f}")
    
    print("\n✓ All benchmarks completed")
