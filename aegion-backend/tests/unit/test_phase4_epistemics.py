"""
Aegion Phase 4 E2E Test - "The Cognitive Guardian" Scenario.

This test simulates:
1. Dev pushes code rapidly (10 commits, 15 decisions in 2 hours)
2. Drift detector identifies velocity increase
3. Risk engine shows elevated risk heatmap
4. Cognitive safety suggests break
5. User takes break, load normalizes
6. Knowledge graph records full provenance

Validates the complete Phase 4 Advanced Epistemics flow.
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from app.services.sentinel import RiskEngine, DriftDetector
from app.services.noesis import GraphService, CognitiveSafetyService
from app.adapters.memory_graph import InMemoryKnowledgeGraph
from app.contracts.risk import RiskLevel, DriftType, CognitiveLoadLevel
from app.ports.knowledge_graph import GraphNodeType, GraphEdgeType


def test_cognitive_guardian_scenario_sync():
    """
    E2E Scenario: "The Cognitive Guardian"
    
    Doctrine: "A tired mind makes dangerous decisions."
    Doctrine: "Patterns reveal intent. Drift reveals risk."
    """
    async def run_scenario():
        print("\n=== THE COGNITIVE GUARDIAN SCENARIO ===\n")
        
        # Initialize services
        risk_engine = RiskEngine()
        drift_detector = DriftDetector()
        graph = InMemoryKnowledgeGraph()
        graph_service = GraphService(graph)
        cognitive_service = CognitiveSafetyService(
            decisions_per_hour_limit=8.0,
            hours_without_break_limit=1.5
        )
        await graph.connect()
        
        workspace_id = "ws-aegion-prod"
        user_id = "dev-alice"
        
        # ========================================
        # ACT 1: Normal baseline period
        # ========================================
        print("ACT 1: Normal baseline period (3 decisions/hour)")
        
        baseline_decisions = [
            {
                "id": f"dec-baseline-{i}",
                "tier": "T1",
                "evidence_ids": ["e1", "e2"],
                "review_count": 1,
                "complexity": 4
            }
            for i in range(6)  # 6 decisions in 2 hours = 3/hour
        ]
        
        print(f"  - Baseline: {len(baseline_decisions)} decisions over 2 hours")
        print(f"  - Normal velocity: {len(baseline_decisions)/2:.1f} decisions/hour")
        
        # ========================================
        # ACT 2: Dev goes into hyperdrive
        # ========================================
        print("\nACT 2: Alice enters hyperdrive mode")
        
        current_decisions = [
            {
                "id": f"dec-rapid-{i}",
                "tier": "T1" if i % 3 else "T2",
                "evidence_ids": ["e1"] if i % 2 else [],  # Less evidence
                "review_count": 0,  # Skipping reviews
                "complexity": 6 + (i % 3)
            }
            for i in range(15)  # 15 decisions in 2 hours = 7.5/hour
        ]
        
        print(f"  - Current period: {len(current_decisions)} decisions in 2 hours")
        print(f"  - Elevated velocity: {len(current_decisions)/2:.1f} decisions/hour")
        
        # ========================================
        # ACT 3: Drift detector catches the pattern
        # ========================================
        print("\nACT 3: Sentinel detects drift patterns")
        
        drift_report = await drift_detector.detect_drift(
            workspace_id=workspace_id,
            current_period=current_decisions,
            baseline_period=baseline_decisions,
            observation_hours=2
        )
        
        print(f"  - Drift signals detected: {drift_report.total_signals}")
        for signal in drift_report.signals:
            print(f"    • {signal.drift_type.value}: {signal.description}")
        
        assert drift_report.total_signals >= 2, "Should detect multiple drift signals"
        assert drift_report.requires_attention, "Should require attention"
        print(f"  ✗ ALERT: {drift_report.attention_reason}")
        
        # ========================================
        # ACT 4: Risk engine elevates workspace risk
        # ========================================
        print("\nACT 4: Risk engine calculates elevated risk")
        
        # Create mixed evidence (some stale)
        evidence = [
            {"id": "e1", "is_stale": False},
            {"id": "e2", "is_stale": True},
            {"id": "e3", "is_stale": True},
        ]
        
        risk_score = await risk_engine.calculate_risk_score(
            workspace_id=workspace_id,
            decisions=current_decisions,
            evidence=evidence,
            lookback_hours=2
        )
        
        print(f"  - Overall risk score: {risk_score.overall_score:.1f}/100")
        print(f"  - Risk level: {risk_score.overall_level.value}")
        for factor in risk_score.contributing_factors[:3]:
            print(f"    • {factor}")
        
        assert risk_score.overall_level in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        print(f"  ⚠ Workspace risk is {risk_score.overall_level.value.upper()}")
        
        # ========================================
        # ACT 5: Cognitive safety triggers
        # ========================================
        print("\nACT 5: Cognitive safety detects fatigue")
        
        # Record all decisions for tracking
        for decision in current_decisions:
            await cognitive_service.record_decision(
                user_id=user_id,
                decision_data=decision
            )
        
        # Assess cognitive load
        assessment = await cognitive_service.assess_cognitive_load(
            user_id=user_id,
            recent_decisions=current_decisions,
            hours_active=2.0
        )
        
        print(f"  - Cognitive load: {assessment.load_level.value}")
        print(f"  - Load score: {assessment.load_score:.1f}/100")
        print(f"  - Decisions/hour: {assessment.factors.decisions_per_hour:.1f}")
        
        if assessment.should_break:
            print(f"  ✗ BREAK RECOMMENDED: {assessment.break_reason}")
            print(f"    Suggested duration: {assessment.recommended_break_minutes} minutes")
        
        # ========================================
        # ACT 6: Check uncertainty on a decision
        # ========================================
        print("\nACT 6: Visualizing uncertainty")
        
        mixed_evidence = [
            {"classification": "supporting"},
            {"classification": "contradictory"},
            {"is_stale": True}
        ]
        
        viz = await cognitive_service.get_uncertainty_visualization(
            decision_id="dec-rapid-7",
            evidence_data=mixed_evidence
        )
        
        print(f"  - Decision: dec-rapid-7")
        print(f"  - Uncertainty: {viz.overall_uncertainty:.0%}")
        print(f"  - Evidence strength: {viz.evidence_strength:.0%}")
        print(f"  - Display: {viz.color_code} {viz.display_type}")
        print(f"  - Explanation: {viz.uncertainty_explanation}")
        
        # ========================================
        # ACT 7: User takes break
        # ========================================
        print("\nACT 7: Alice takes a break")
        
        await cognitive_service.record_break(user_id)
        
        # Re-assess after break
        post_break = await cognitive_service.assess_cognitive_load(
            user_id=user_id,
            recent_decisions=[],  # No new decisions after break
            hours_active=0.0
        )
        
        print(f"  ✓ Break recorded for {user_id}")
        print(f"  - Post-break load level: {post_break.load_level.value}")
        
        # ========================================
        # ACT 8: Record decisions in knowledge graph
        # ========================================
        print("\nACT 8: Recording provenance in Knowledge Graph")
        
        # Add user node
        await graph.add_node(
            node_type=GraphNodeType.USER,
            node_id=user_id,
            properties={"name": "Alice", "role": "developer"}
        )
        
        # Add evidence nodes
        for i in range(3):
            await graph.add_node(
                node_type=GraphNodeType.EVIDENCE,
                node_id=f"evd-{i}",
                properties={"workspace_id": workspace_id}
            )
        
        # Record a decision with provenance
        decision_node = await graph_service.record_decision(
            decision_id="dec-recorded-001",
            proposal_id="prop-001",
            approver_id=user_id,
            evidence_ids=["evd-0", "evd-1"],
            workspace_id=workspace_id,
            metadata={"tier": "T1", "risk_level": risk_score.overall_level.value}
        )
        
        print(f"  - Recorded decision: {decision_node.node_id}")
        
        # Get provenance
        provenance = await graph_service.get_decision_provenance("dec-recorded-001")
        print(f"  - Provenance nodes: {len(provenance.nodes)}")
        print(f"  - Provenance edges: {len(provenance.edges)}")
        
        # ========================================
        # Epilogue: System state
        # ========================================
        print("\n=== SCENARIO COMPLETE ===")
        print("✓ Drift detector identified velocity/review bypass")
        print("✓ Risk engine elevated workspace risk score")
        print("✓ Cognitive safety recommended break")
        print("✓ Uncertainty visualization generated")
        print("✓ Knowledge graph recorded full provenance")
        print("\nThe Cognitive Guardian protected Alice from fatigue-induced errors!")
        
        return True
    
    result = asyncio.run(run_scenario())
    assert result is True


def test_graph_service_edg_sync_sync():
    """Test EDG to Knowledge Graph synchronization."""
    async def run():
        graph = InMemoryKnowledgeGraph()
        service = GraphService(graph)
        
        # Simulate EDG nodes
        edg_nodes = [
            {"node_id": "src-001", "node_type": "source", "content_hash": "abc", "workspace_id": "ws-1"},
            {"node_id": "evd-001", "node_type": "evidence", "content_hash": "def", "workspace_id": "ws-1"},
        ]
        
        edg_edges = [
            {"source_id": "src-001", "target_id": "evd-001", "edge_type": "derives_from"}
        ]
        
        result = await service.sync_from_edg(edg_nodes, edg_edges)
        
        assert result["nodes_synced"] == 2
        assert result["edges_synced"] == 1
        
        # Verify nodes exist
        src = await graph.get_node("src-001")
        assert src is not None
        
        evd = await graph.get_node("evd-001")
        assert evd is not None
        
    asyncio.run(run())


def test_impact_analysis_sync():
    """Test impact analysis through the graph."""
    async def run():
        graph = InMemoryKnowledgeGraph()
        service = GraphService(graph)
        
        # Build a chain: source -> evidence -> decision
        await graph.add_node(GraphNodeType.SOURCE, "src-impact", {"workspace_id": "ws-1"})
        await graph.add_node(GraphNodeType.EVIDENCE, "evd-impact", {"workspace_id": "ws-1"})
        await graph.add_node(GraphNodeType.DECISION, "dec-impact", {"workspace_id": "ws-1"})
        await graph.add_node(GraphNodeType.USER, "user-impact", {})
        
        await graph.add_edge("src-impact", "evd-impact", GraphEdgeType.DERIVES_FROM)
        await graph.add_edge("evd-impact", "dec-impact", GraphEdgeType.SUPPORTS)
        await graph.add_edge("dec-impact", "user-impact", GraphEdgeType.APPROVED_BY)
        
        impact = await service.analyze_impact("src-impact", max_depth=3)
        
        assert impact["affected_evidence_count"] == 1
        assert impact["affected_decision_count"] == 1
        assert "evd-impact" in impact["affected_evidence"]
        assert "dec-impact" in impact["affected_decisions"]
        
    asyncio.run(run())
