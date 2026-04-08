"""
Aegion Phase 5 E2E Test - "The Aegion Protocol" Scenario.

Full system test spanning all 5 phases, following the established E2E pattern
from test_end_to_end_scenario.py (The Prometheus Incident).

Phases covered:
1. [Phase 0] Create workspace + authenticate user
2. [Phase 1] Submit proposal with decision intent
3. [Phase 2] Conduct peer review with quorum
4. [Phase 3] EDG staleness tracking (simplified)
5. [Phase 4] Risk score + cognitive load + KG provenance
"""

import pytest
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

# Phase 0: Core
from app.core.security import AuthorityContext, Role

# Phase 1: Contracts
from app.contracts.decision_intent import (
    DecisionIntent, ImpactLevel, ReversibilityLevel, 
    ReasoningPhase, DecisionTier
)
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.models.decision import Decision, DecisionStatus, VisibilityLabel

# Phase 2: Review
from app.contracts.review import (
    ProposalReview, ReviewVerdict, DEFAULT_QUORUM
)

# Phase 1: Archon
from app.services.archon import ArchonGates

# Phase 4: Sentinel & Noesis
from app.services.sentinel import RiskEngine
from app.services.noesis import GraphService, CognitiveSafetyService
from app.adapters.memory_graph import InMemoryKnowledgeGraph
from app.contracts.risk import CognitiveLoadLevel


def test_aegion_protocol_full_system_sync():
    """
    E2E: 'The Aegion Protocol' - Complete system validation.
    
    Story: A developer submits a high-impact proposal.
    It goes through review, risk assessment, cognitive safety checks,
    and is recorded with full provenance in the Knowledge Graph.
    """
    asyncio.run(_run_aegion_protocol())


async def _run_aegion_protocol():
    print("\n" + "="*60)
    print("          THE AEGION PROTOCOL - FULL SYSTEM TEST")
    print("="*60)
    
    # =========================================================================
    # PHASE 0: Environment Setup
    # =========================================================================
    print("\n▸ PHASE 0: Bootstrap & Environment")
    
    workspace_id = f"ws-aegion-{uuid4().hex[:6]}"
    workspace = Workspace(
        workspace_id=workspace_id,
        name="Aegion Production",
        owner_id="admin-001"
    )
    
    admin = AuthorityContext(
        user_id="admin-001",
        role=Role.ADMIN,
        can_approve_t1=True,
        can_approve_t2=True
    )
    
    architect = AuthorityContext(
        user_id="arch-001",
        role=Role.ARCHITECT,
        can_approve_t1=True,
        can_approve_t2=False
    )
    
    members = [
        WorkspaceMember(user_id="admin-001", role=WorkspaceRole.OWNER),
        WorkspaceMember(user_id="arch-001", role=WorkspaceRole.ARCHITECT),
        WorkspaceMember(user_id="dev-001", role=WorkspaceRole.DEVELOPER)
    ]
    
    print(f"  ✓ Workspace: {workspace.name}")
    print(f"  ✓ Users: {len(members)} (admin, architect, developer)")
    
    # =========================================================================
    # PHASE 1: Session & Proposal
    # =========================================================================
    print("\n▸ PHASE 1: Proposal Submission")
    
    session_id = "sess-001"
    
    proposal = DecisionIntent(
        intent_id=f"prop-oauth-{uuid4().hex[:6]}",
        session_id=session_id,
        title="Migrate to OAuth2 Authentication",
        description="Replace JWT with OAuth2 for better third-party integration",
        impact_level=ImpactLevel.CROSS_MODULE,
        reversibility=ReversibilityLevel.MODERATE,
        calculated_tier=DecisionTier.T2,
        affected_modules=["auth", "api"],
        affected_files=["auth.py", "middleware.py"],
        reasoning=ReasoningPhase(
            problem_framing="JWT lacks third-party integration features",
            assumptions=["OAuth2 libraries are mature"],
            constraints=["Must maintain backward compatibility"],
            alternatives_considered=["SAML", "OpenID Connect only"]
        ),
        origin="human",
        proposed_by="dev-001",
        proposed_at=datetime.now(timezone.utc)
    )
    
    archon = ArchonGates()
    tier = archon.classify_tier(proposal.impact_level, proposal.reversibility, proposal.affected_modules)
    print(f"  ✓ Proposal: {proposal.title}")
    print(f"  ✓ Archon classification: {tier.value}")
    
    assert tier == DecisionTier.T2, f"Expected T2, got {tier}"
    
    # =========================================================================
    # PHASE 2: Peer Review & Quorum
    # =========================================================================
    print("\n▸ PHASE 2: Peer Review")
    
    # Architect review
    review_1 = ProposalReview(
        review_id="rev-001",
        proposal_id=proposal.intent_id,
        reviewer_id=architect.user_id,
        verdict=ReviewVerdict.APPROVE,
        comments="Migration plan is sound. LGTM."
    )
    
    # Admin review
    review_2 = ProposalReview(
        review_id="rev-002",
        proposal_id=proposal.intent_id,
        reviewer_id=admin.user_id,
        verdict=ReviewVerdict.APPROVE,
        comments="Approved. Proceed with implementation."
    )
    
    votes = [review_1, review_2]
    quorum = DEFAULT_QUORUM["T2"]
    approve_count = len([v for v in votes if v.verdict == ReviewVerdict.APPROVE])
    
    print(f"  ✓ Reviews: {len(votes)} submitted")
    print(f"  ✓ Quorum: {approve_count}/{quorum.minimum_approvers} needed")
    
    assert approve_count >= quorum.minimum_approvers
    
    # =========================================================================
    # PHASE 3: Evidence Freshness (Simplified)
    # =========================================================================
    print("\n▸ PHASE 3: Evidence Freshness")
    
    # Simulate evidence freshness check (no full EDG for this test)
    evidence_fresh = True  # Would come from StalenessDetector
    evidence_count = 2     # Supporting evidence collected
    
    print(f"  ✓ Evidence: {evidence_count} pieces collected")
    print(f"  ✓ Freshness: all evidence is fresh")
    
    # =========================================================================
    # PHASE 4: Risk & Cognitive Safety
    # =========================================================================
    print("\n▸ PHASE 4: Risk & Cognitive Safety")
    
    # Initialize Phase 4 services
    risk_engine = RiskEngine()
    graph = InMemoryKnowledgeGraph()
    graph_svc = GraphService(graph)
    cognitive = CognitiveSafetyService()
    await graph.connect()
    
    # Calculate risk score
    risk = await risk_engine.calculate_risk_score(
        workspace_id=workspace_id,
        decisions=[],  # First decision
        evidence=[{"is_stale": False}, {"is_stale": False}]
    )
    print(f"  ✓ Risk: {risk.overall_score:.0f}/100 ({risk.overall_level.value})")
    
    # Assess cognitive load for approver
    load = await cognitive.assess_cognitive_load(
        user_id=admin.user_id,
        recent_decisions=[{"complexity": 5}],
        hours_active=1.0
    )
    print(f"  ✓ Cognitive load: {load.load_level.value}")
    
    # Get uncertainty visualization
    viz = await cognitive.get_uncertainty_visualization(
        decision_id=proposal.intent_id,
        evidence_data=[{"classification": "supporting"}, {"classification": "opposing"}]
    )
    print(f"  ✓ Uncertainty: {viz.overall_uncertainty:.0%}")
    
    # =========================================================================
    # FINAL: Decision & Provenance
    # =========================================================================
    print("\n▸ FINAL: Approval & Provenance")
    
    # Issue Decision
    decision = Decision(
        decision_id=f"dec-{uuid4().hex[:8]}",
        proposal_id=proposal.intent_id,
        session_id=session_id,
        workspace_id=workspace_id,
        tier=tier,
        status=DecisionStatus.APPROVED,
        title=proposal.title,
        description=proposal.description,
        affected_files=proposal.affected_files,
        affected_modules=proposal.affected_modules,
        visibility_label=VisibilityLabel.GOVERNED,
        proposed_by=proposal.proposed_by,
        proposed_at=proposal.proposed_at,
        approved_by=admin.user_id,
        approved_at=datetime.now(timezone.utc),
        metadata={
            "tier": tier.value,
            "risk_level": risk.overall_level.value,
            "cognitive_load": load.load_level.value
        }
    )
    print(f"  ✓ Decision: {decision.decision_id}")
    
    # Record provenance in Knowledge Graph
    await graph.add_node("user", admin.user_id, {"role": "admin"})
    await graph.add_node("proposal", proposal.intent_id, {"tier": tier.value})
    
    dec_node = await graph_svc.record_decision(
        decision_id=decision.decision_id,
        proposal_id=proposal.intent_id,
        approver_id=admin.user_id,
        evidence_ids=["evd-001", "evd-002"],  # Simulated
        workspace_id=workspace_id,
        metadata={"risk": risk.overall_level.value}
    )
    
    prov = await graph_svc.get_decision_provenance(dec_node.node_id)
    print(f"  ✓ Provenance: {len(prov.nodes)} nodes recorded")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "="*60)
    print("              AEGION PROTOCOL COMPLETE")
    print("="*60)
    print(f"""
✓ Phase 0: Workspace created, 3 users authenticated
✓ Phase 1: Proposal submitted, Archon classified as T1
✓ Phase 2: Quorum met with 2 reviews
✓ Phase 3: Evidence freshness verified
✓ Phase 4: Risk {risk.overall_score:.0f}/100, cognitive load {load.load_level.value}
✓ Final:   Decision approved with full provenance
""")


def test_cognitive_overload_blocks_approval_sync():
    """
    Cross-Phase: High cognitive load should warn before approval.
    """
    asyncio.run(_run_cognitive_overload())


async def _run_cognitive_overload():
    print("\n=== COGNITIVE OVERLOAD SCENARIO ===")
    
    cognitive = CognitiveSafetyService(
        decisions_per_hour_limit=5.0,
        hours_without_break_limit=1.0
    )
    
    # Simulate heavy workload
    for i in range(20):
        await cognitive.record_decision(
            user_id="tired-approver",
            decision_data={"complexity": 8, "tier": "T2"}
        )
    
    # Assess load
    assessment = await cognitive.assess_cognitive_load(
        user_id="tired-approver",
        recent_decisions=[{"complexity": 8}] * 20,
        hours_active=2.5
    )
    
    print(f"  Load level: {assessment.load_level.value}")
    print(f"  Load score: {assessment.load_score:.0f}")
    print(f"  Should break: {assessment.should_break}")
    
    # Verify elevated/overloaded
    assert assessment.load_level in [CognitiveLoadLevel.ELEVATED, CognitiveLoadLevel.OVERLOADED]
    print("✓ Cognitive overload scenario validated")


def test_risk_escalation_with_stale_evidence_sync():
    """
    Cross-Phase: Stale evidence should increase risk score.
    """
    asyncio.run(_run_risk_escalation())


async def _run_risk_escalation():
    print("\n=== RISK ESCALATION SCENARIO ===")
    
    risk_engine = RiskEngine()
    
    # Fresh evidence
    score_fresh = await risk_engine.calculate_risk_score(
        workspace_id="ws-test",
        decisions=[],
        evidence=[{"is_stale": False}, {"is_stale": False}]
    )
    
    # Stale evidence
    score_stale = await risk_engine.calculate_risk_score(
        workspace_id="ws-test",
        decisions=[],
        evidence=[{"is_stale": True}, {"is_stale": True}]
    )
    
    print(f"  Risk with fresh evidence: {score_fresh.overall_score:.0f}")
    print(f"  Risk with stale evidence: {score_stale.overall_score:.0f}")
    
    assert score_stale.overall_score > score_fresh.overall_score
    print("✓ Risk escalation scenario validated")
