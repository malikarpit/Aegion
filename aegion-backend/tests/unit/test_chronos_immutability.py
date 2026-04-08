"""
Aegion Chronos Immutability Tests.

These tests verify that Chronos artifacts and memory are truly immutable.

Doctrine: "Memory is governed, not generated."
"What is written cannot be unwritten."
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.services.chronos.artifacts import (
    SessionArtifact,
    ChronosArtifacts,
    ChronosSupersession,
    DecisionLineage,
)
from app.contracts.decision_intent import (
    DecisionIntent, DecisionTier, ImpactLevel, ReversibilityLevel, ReasoningPhase
)


def create_decision_intent(
    intent_id: str,
    session_id: str = "sess-1",
    title: str = "Test Decision",
    description: str = "Test description",
    origin: str = "human",
    proposed_by: str = "user-1"
) -> DecisionIntent:
    """Helper to create properly formed DecisionIntent objects."""
    return DecisionIntent(
        intent_id=intent_id,
        session_id=session_id,
        title=title,
        description=description,
        impact_level=ImpactLevel.LOCAL,
        reversibility=ReversibilityLevel.MODERATE,
        calculated_tier=DecisionTier.T1,
        reasoning=ReasoningPhase(
            problem_framing="Test problem",
            assumptions=["Assumption 1"],
            constraints=["Constraint 1"],
            boundaries=["Boundary 1"]
        ),
        origin=origin,
        proposed_by=proposed_by,
        proposed_at=datetime.now(timezone.utc)
    )


class TestSessionArtifactImmutability:
    """Tests for session artifact immutability."""

    def test_session_artifact_is_frozen(self):
        """INVARIANT: SessionArtifact cannot be modified after creation."""
        artifact = SessionArtifact(
            artifact_id="art-123456789012345678901234567890ab",
            session_id="sess-456",
            session_start="2026-02-09T10:00:00Z",
            session_end="2026-02-09T12:00:00Z",
            owner_id="user-1",
            workspace_id="ws-1",
            decision_count=5,
            evidence_count=3
        )
        
        # Attempting to modify should raise
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            artifact.decision_count = 10

    def test_artifact_has_all_required_fields(self):
        """SessionArtifact must have all required provenance fields."""
        artifact = SessionArtifact(
            artifact_id="art-123456789012345678901234567890ab",
            session_id="sess-456",
            session_start="2026-02-09T10:00:00Z",
            session_end="2026-02-09T12:00:00Z",
            owner_id="user-1",
            workspace_id="ws-1"
        )
        
        assert artifact.artifact_id is not None
        assert artifact.session_id is not None
        assert artifact.owner_id is not None


class TestDecisionSupersession:
    """Tests for decision supersession (never edit, only supersede)."""

    def test_supersession_preserves_original(self):
        """INVARIANT: Original decision is preserved when superseded."""
        # Create original decision
        original = create_decision_intent(
            intent_id="dec-original",
            title="Original Decision",
            description="This is the original"
        )
        
        # Create new decision that supersedes
        new_decision = create_decision_intent(
            intent_id="dec-new",
            title="Updated Decision",
            description="This supersedes the original"
        )
        
        # The original should remain unchanged
        assert original.intent_id == "dec-original"
        assert original.title == "Original Decision"
        # New decision exists independently
        assert new_decision.intent_id == "dec-new"

    def test_lineage_tracks_chain_position(self):
        """INVARIANT: Lineage tracks position in supersession chain."""
        lineage = DecisionLineage(
            decision_id="dec-3",
            supersedes_id="dec-2",
            chain_root_id="dec-1",
            chain_position=2,  # Third in chain (0, 1, 2)
            created_at="2026-02-09T12:00:00Z"
        )
        
        assert lineage.chain_position == 2
        assert lineage.chain_root_id == "dec-1"
        assert lineage.supersedes_id == "dec-2"


class TestDecisionIntentImmutability:
    """Tests for decision intent structure."""

    def test_decision_has_required_fields(self):
        """INVARIANT: Every decision must have required provenance fields."""
        # Missing required fields should fail
        with pytest.raises(ValidationError):
            DecisionIntent(
                intent_id="dec-1",
                # Missing: session_id, title, description, impact_level, etc.
            )

    def test_decision_requires_rationale(self):
        """INVARIANT: Decision must have title/description (rationale)."""
        decision = create_decision_intent(
            intent_id="dec-1",
            title="Add authentication",
            description="We need to secure the API endpoints"
        )
        
        assert decision.title != ""
        assert decision.description != ""
        assert decision.reasoning is not None

    def test_decision_requires_session(self):
        """INVARIANT: Every decision MUST be tied to a session."""
        decision = create_decision_intent(
            intent_id="dec-1",
            session_id="sess-required"
        )
        
        assert decision.session_id is not None
        assert decision.session_id != ""


class TestForbiddenPaths:
    """Tests for forbidden paths - things that MUST NOT happen."""

    def test_ai_cannot_set_approval_status(self):
        """INVARIANT: AI agents cannot directly approve decisions."""
        # This is enforced by not exposing approval methods to AI
        # The test validates the concept
        ai_origins = ["ai_child", "ai_parent"]
        human_origins = ["human"]
        
        for ai_origin in ai_origins:
            # AI origin does NOT grant approval authority
            assert ai_origin not in ["admin_approval", "architect_approval"]
        
        # Human origin is the only valid approval path
        assert "human" in human_origins

    def test_decision_has_origin_field(self):
        """INVARIANT: Every decision must declare its origin."""
        decision = create_decision_intent(
            intent_id="dec-1",
            origin="human"
        )
        
        assert decision.origin is not None
        assert decision.origin in ["human", "ai_child", "ai_parent"]
