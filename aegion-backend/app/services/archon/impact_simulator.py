"""
Aegion Impact Simulation Engine.

Doctrine: "Predict before you commit."

Provides:
- Hypothetical decision analysis (What if I approve this?)
- Invariant pre-validation
- Downstream impact assessment (What gets unblocked?)
- Risk score calculation
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ...core.logging import logger
from ...contracts.decision_intent import DecisionTier
from ...contracts.evidence import Evidence
from .invariant_engine import get_invariant_engine, InvariantResult
from .gates import get_archon
from ...services.graph_provider import get_shared_graph


@dataclass
class SimulationResult:
    """Result of a decision simulation."""
    proposal_id: str
    action: str  # "approve" | "reject"
    tier: str
    
    # Validation status
    allowed: bool
    blocking_violations: List[str]
    alerting_violations: List[str]
    
    # Impact analysis
    impacted_nodes_count: int
    impacted_downstream_proposals: List[str]  # Proposals blocked by this one
    risk_score: float
    
    # Metadata
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    simulation_id: str = ""


class ImpactSimulator:
    """
    Simulates governance actions to predict outcome and impact.
    
    Usage:
        sim = ImpactSimulator(graph)
        result = sim.simulate_approval(
            proposal_id="prop-123",
            tier=DecisionTier.T2,
            evidence_list=[...]
        )
    """

    def __init__(self, graph=None):
        self.graph = graph or get_shared_graph()
        self.invariant_engine = get_invariant_engine()
        # We don't need ArchonGates instance directly as we reuse InvariantEngine
        # but we might need policy logic if we want to simulate tier classification.

    def simulate_approval(
        self,
        proposal_id: str,
        tier: DecisionTier,
        evidence_list: List[Evidence],
        user_id: str,
        user_roles: List[str] = None,
        workspace_id: str = None,
    ) -> SimulationResult:
        """
        Simulate an approval action.
        
        1. Checks all invariants (blocking & alerting).
        2. Checks graph for downstream dependencies (blocked proposals).
        3. Calculates a risk score.
        """
        # 1. Invariant Check
        # Construct the context just like ArchonGates does
        stale_count = sum(1 for e in evidence_list if e.is_stale)
        evidence_types = set(e.classification.value for e in evidence_list if not e.is_stale)
        
        # Determine if we need to fetch the proposal to check creation time vs evidence
        # For simulation, we assume evidence is newer if not provided, or fetch if critical.
        # Check if proposal exists in graph to get metadata?
        proposal_node = self.graph.get_node(proposal_id)
        if not proposal_node:
             # If simulating a non-existent proposal (e.g. drafting), use defaults
             # But usually we simulate existing proposals.
             proposal_created_at = datetime.now(timezone.utc) # Fallback
             proposer_id = "unknown"
        else:
            try:
                proposal_created_at = datetime.fromisoformat(proposal_node.get("created_at", ""))
            except ValueError:
                proposal_created_at = datetime.now(timezone.utc)
            proposer_id = proposal_node.get("created_by", "")

        all_after = all(
            not hasattr(e, 'created_at') or e.created_at is None or e.created_at >= proposal_created_at
            for e in evidence_list
        )

        inv_result = self.invariant_engine.evaluate_for_approval(
            tier=tier.value,
            proposer_id=proposer_id,
            approver_id=user_id,
            approver_type="human", # Assumption for simulation unless specified
            evidence_count=len(evidence_list),
            stale_evidence_count=stale_count,
            distinct_evidence_types=len(evidence_types),
            all_evidence_after_proposal=all_after,
            freeze_active=False, # Assume no freeze for simulation unless passed?
            proposal_id=proposal_id,
        )

        # 2. Downstream Impact
        # Find everything that depends on this proposal.
        # We look for nodes that have a BLOCKS edge FROM this proposal?
        # Or nodes that this proposal BLOCKS?
        # In causal graphs: A BLOCKS B means B cannot proceed until A is done.
        # So we look for outgoing BLOCKS edges from this proposal?
        # Wait, if A blocks B, the edge direction usually depends on convention.
        # Typically: B -> DEPENDS_ON -> A.
        # Or A -> BLOCKS -> B.
        # Let's assume standard dependency: B depends on A.
        # So we look for incoming DEPENDS_ON edges to A?
        # get_ancestors: upstream (what A depends on).
        # get_descendants: downstream (what depends on A).
        # If "descendants" follows outgoing edges, and edges are A->B?
        # neo4j_graph.py default semantic: "descendants" = outgoing.
        # If Dependency is B -> depends_on -> A, then A is the target.
        # So "descendants" of A would be nothing (if edge points to A).
        # "Ancestors" of A (incoming edges) would be B.
        # But commonly dependencies flow: A -> B (A causes B?).
        # NO, "A depends on B". Edge `(A)-[:DEPENDS_ON]->(B)`.
        # If I approve B, A becomes unblocked.
        # So I need to find "Inverse dependents" = nodes pointing TO me.
        # neo4j_graph.py `get_ancestors` and `get_descendants` semantic:
        # get_ancestors uses `(n)<-[:REL*]-(ancestor)`. Incoming.
        # get_descendants uses `(n)-[:REL*]->(descendant)`. Outgoing.
        
        # If edge is `(BlockedNode)-[:DEPENDS_ON]->(BlockerNode)`, then BlockerNode is the target.
        # So to find what BlockerNode blocks, we need INCOMING edges.
        # That corresponds to `get_ancestors` in neo4j_graph.py (incoming).
        
        # Let's check `get_ancestors` in neo4j_graph.py again.
        # Wait, let's look at the usage in `neo4j_graph.py`.
        # "Get upstream/ancestor nodes."
        
        # Strategy: Find nodes `n` where `(n)-[:DEPENDS_ON]->(proposal)`.
        # This means `proposal` is an ancestor of `n`? 
        # No, `n` is the source, `proposal` is target. 
        # `(n) --> (proposal)` means `proposal` is a "child" in graph theory if arrows point to children?
        # No, arrows usually point to dependencies.
        # So `proposal` is a dependency.
        
        # I will look for nodes that reference this proposal.
        # I can use `graph.run_query` if needed, or `get_edges(target_id=proposal_id)`.
        
        downstream_edges = self.graph.get_edges(target_id=proposal_id, edge_type="DEPENDS_ON")
        impacted_nodes = [edge["source"] for edge in downstream_edges]
        
        # Also check explicit BLOCKS edges if they exist: `(proposal)-[:BLOCKS]->(blocked_node)`
        blocking_edges = self.graph.get_edges(source_id=proposal_id, edge_type="BLOCKS")
        impacted_nodes.extend([edge["target"] for blocking_edges in blocking_edges])
        
        # 3. Risk Calculation
        # Base risk from tier
        base_risk = {
            "T0": 1.0,
            "T1": 10.0,
            "T2": 50.0,
            "T3": 100.0,
        }.get(tier.value, 10.0)
        
        # Multipliers
        impact_mod = 1.0 + (0.1 * len(impacted_nodes))
        violation_mod = 1.0 + (0.5 * len(inv_result.alerting_violations))
        if not inv_result.passed:
            violation_mod += 10.0 # Blocking violation creates high risk score/invalidity
            
        risk_score = base_risk * impact_mod * violation_mod

        return SimulationResult(
            proposal_id=proposal_id,
            action="approve",
            tier=tier.value,
            allowed=inv_result.passed,
            blocking_violations=[v.message for v in inv_result.blocking_violations],
            alerting_violations=[v.message for v in inv_result.alerting_violations],
            impacted_nodes_count=len(impacted_nodes),
            impacted_downstream_proposals=list(set(impacted_nodes)), # Unique
            risk_score=round(risk_score, 2),
            simulation_id=f"sim-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )


# Singleton
_simulator: Optional[ImpactSimulator] = None

def get_impact_simulator() -> ImpactSimulator:
    global _simulator
    if _simulator is None:
        _simulator = ImpactSimulator()
    return _simulator
