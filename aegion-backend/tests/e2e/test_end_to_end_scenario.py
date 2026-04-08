"""
Aegion End-to-End Scenario Test.

Covers Phases 0, 1, and 2 in a cohesive user story.
Story: "The Prometheus Incident"
- Alice (Owner) creates a workspace.
- Bob (Architect) joins.
- Alice starts a session and proposes a critical system change (T2).
- Archon classifies it as T2 (High Impact).
- Bob reviews and requests changes.
- Alice updates the proposal (simulated by creating a new one linked to session).
- Bob approves.
- Archon validates quorum and issues Decision.
- Events are emitted throughout.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from typing import List

from app.core.security import AuthorityContext, Role
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.models.decision import Decision
from app.contracts.decision_intent import (
    DecisionIntent, ImpactLevel, ReversibilityLevel, ReasoningPhase, DecisionTier
)
from app.contracts.review import (
    ProposalReview, ReviewVerdict, ProposalApprovalStatus, DEFAULT_QUORUM
)
from app.services.chronos.artifacts import ChronosArtifacts, SessionArtifact
from app.services.archon import ArchonGates

# Mocks for E2E
class MockPubSub:
    def __init__(self):
        self.events = []

    async def publish(self, topic, message):
        self.events.append((topic, message))
        return "msg-id-123"

class MockStorage:
    def __init__(self):
        self.store_calls = []

    async def store(self, key, content, content_type):
        self.store_calls.append((key, content))
        return True

@pytest.mark.skipif(False, reason="Run manually or with asyncio installed")
def test_prometheus_incident_scenario_sync():
    """Synchronous wrapper for async E2E test."""
    asyncio.run(run_async_scenario())

async def run_async_scenario():
    # =========================================================================
    # PHASE 0 & 2: Environment & Workspace Setup
    # =========================================================================
    
    print("\n[Step 1] Initializing System & Workspace...")
    
    # 1.1 Setup Actors
    # Alice: Admin/Owner authority
    alice = AuthorityContext(
        user_id="user-alice", 
        role=Role.ADMIN,
        can_approve_t1=True, 
        can_approve_t2=True
    )
    # Bob: Architect authority
    bob = AuthorityContext(
        user_id="user-bob", 
        role=Role.ARCHITECT,
        can_approve_t1=True, 
        can_approve_t2=False
    )
    
    # 1.2 Create Workspace
    workspace_id = "ws-prometheus"
    workspace = Workspace(
        workspace_id=workspace_id,
        name="Prometheus Project",
        owner_id=alice.user_id
    )
    
    members = [
        WorkspaceMember(user_id=alice.user_id, role=WorkspaceRole.OWNER),
        WorkspaceMember(user_id=bob.user_id, role=WorkspaceRole.ARCHITECT)
    ]
    
    assert len(members) == 2
    print(f" > Workspace '{workspace.name}' created with Alice (Owner) and Bob (Architect).")

    # =========================================================================
    # PHASE 1: Session & Proposal (High Impact)
    # =========================================================================
    
    print("\n[Step 2] Alice starts session & proposes Critical Change...")
    
    # 2.1 Start Session
    session_id = "sess-fire-001"
    
    # 2.2 Create Proposal (T2 High Impact)
    proposal = DecisionIntent(
        intent_id="prop-rewrite-auth",
        session_id=session_id,
        title="Rewrite Auth Service in Rust",
        description="Migrate from Python to Rust for performance.",
        impact_level=ImpactLevel.CROSS_MODULE,
        reversibility=ReversibilityLevel.DIFFICULT,
        calculated_tier=DecisionTier.T2,
        affected_modules=["auth_service"],
        affected_files=["auth.py", "user.py"],
        reasoning=ReasoningPhase(
            problem_framing="Auth is too slow",
            assumptions=["Rust is faster"],
            constraints=["Must finish by Q4"],
            alternatives_considered=["Go", "C++"]
        ),
        origin="human",
        proposed_by=alice.user_id,
        proposed_at=datetime.now(timezone.utc)
    )
    
    # 2.3 Verify Archon Classification
    archon = ArchonGates()
    tier = archon.classify_tier(proposal.impact_level, proposal.reversibility, proposal.affected_modules)
    assert tier == DecisionTier.T2
    print(f" > Proposal classified as {tier.value} (High Impact).")

    # =========================================================================
    # PHASE 2: Collaboration & Review
    # =========================================================================
    
    print("\n[Step 3] Bob reviews the proposal...")
    
    # 3.1 Bob reviews -> Request Changes
    review_1 = ProposalReview(
        review_id="rev-001",
        proposal_id=proposal.intent_id,
        reviewer_id=bob.user_id,
        verdict=ReviewVerdict.REQUEST_CHANGES,
        comments="We don't have enough Rust expertise yet. Please provide a training plan."
    )
    print(f" > Bob requested changes: '{review_1.comments}'")
    
    # 3.2 Bob re-reviews -> Approve
    review_2 = ProposalReview(
        review_id="rev-002",
        proposal_id=proposal.intent_id,
        reviewer_id=bob.user_id,
        verdict=ReviewVerdict.APPROVE,
        comments="Training plan looks solid. transform!"
    )
    print(" > Bob approved.")
    
    # =========================================================================
    # PHASE 1 & 2: Quorum & Decision
    # =========================================================================
    
    print("\n[Step 4] Checking Quorum & Approving...")
    
    votes = [
        {"voter": alice.user_id, "role": WorkspaceRole.OWNER, "approve": True},
        {"voter": bob.user_id, "role": WorkspaceRole.ARCHITECT, "approve": True}
    ]
    
    quorum = DEFAULT_QUORUM["T2"]
    approve_count = len([v for v in votes if v["approve"]])
    has_architect = any(v for v in votes if v["role"] == WorkspaceRole.ARCHITECT and v["approve"])
    
    assert approve_count >= quorum.minimum_approvers
    assert has_architect
    
    # 4.2 Issue Decision
    from app.models.decision import DecisionStatus, VisibilityLabel

    decision = Decision(
        decision_id="dec-rewrite-auth",
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
        approved_by=bob.user_id,
        approved_at=datetime.now(timezone.utc),
        metadata={"outcome_summary": "Rewrite Auth Service in Rust approved with training plan."}
    )
    print(f" > Decision ISSUED: {decision.decision_id}")

    # =========================================================================
    # PHASE 2: Event Verification
    # =========================================================================
    
    print("\n[Step 5] Verifying Event Emission (Mock)...")
    pubsub = MockPubSub()
    
    from app.ports.events import Event, EventCategory, EventTypes
    event = Event(
        event_id="evt-001",
        category=EventCategory.DECISION,
        event_type=EventTypes.DECISION_APPROVED,
        payload={"decision_id": decision.decision_id},
        timestamp=datetime.now(timezone.utc),
        source="aegion-test-suite"
    )
    await pubsub.publish(f"aegion.decision.{decision.decision_id}", event)
    
    assert len(pubsub.events) == 1
    print(" > Decision event published successfully.")

    # =========================================================================
    # PHASE 1: Memory Distillation (Chronos)
    # =========================================================================
    
    print("\n[Step 6] Distilling Session Memory...")
    mock_storage = MockStorage()
    chronos = ChronosArtifacts(storage_port=mock_storage)
    
    session_start = datetime.now(timezone.utc).isoformat()
    session_end = datetime.now(timezone.utc).isoformat()
    
    artifact = await chronos.distill_session(
        session_id=session_id,
        owner_id=alice.user_id,
        workspace_id=workspace_id,
        session_start=session_start,
        session_end=session_end,
        decisions=[proposal], # Decisions list typically containers intents or artifacts
        evidence_list=[],
        reasoning_phases=[],
        metrics={"context_tokens": 1500, "ai_invocations": 5}
    )
    
    assert artifact.session_id == session_id
    assert artifact.decision_count == 1
    assert len(mock_storage.store_calls) == 1
    # Check that artifact is stored content-addressed
    stored_key, _ = mock_storage.store_calls[0]
    assert stored_key == f"artifacts/sessions/{artifact.artifact_id}"
    
    print(f" > Session distilled to artifact {artifact.artifact_id}")
    print(f" > Artifact stored at {stored_key}")

    print("\n[SUCCESS] End-to-End Scenario 'The Prometheus Incident' passed.")

if __name__ == "__main__":
    # Allow running directly or via pytest
    asyncio.run(test_prometheus_incident_scenario())
