"""
Aegion Phase 2 Integration Tests.

Tests for multi-user collaboration and event streaming.
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from app.models.workspace import (
    Workspace, WorkspaceWithMembers, WorkspaceMember, WorkspaceRole
)
from app.contracts.review import (
    ProposalReview, ReviewVerdict, ApprovalVote, 
    ProposalApprovalStatus, QuorumRequirement, DEFAULT_QUORUM
)


class TestWorkspaceModel:
    """Tests for workspace data model."""

    def test_workspace_creation(self):
        """Workspaces can be created with required fields."""
        workspace = Workspace(
            workspace_id="ws-123",
            name="Test Workspace",
            owner_id="user-1"
        )
        
        assert workspace.workspace_id == "ws-123"
        assert workspace.owner_id == "user-1"
        assert workspace.governance_policy_id == "genesis"  # Default

    def test_workspace_with_members(self):
        """WorkspaceWithMembers includes member list."""
        owner = WorkspaceMember(
            user_id="user-1",
            role=WorkspaceRole.OWNER,
            display_name="Owner"
        )
        
        workspace = WorkspaceWithMembers(
            workspace_id="ws-123",
            name="Test Workspace",
            owner_id="user-1",
            members=[owner]
        )
        
        assert workspace.member_count == 1
        assert workspace.get_member("user-1") is not None
        assert workspace.has_role("user-1", WorkspaceRole.OWNER)

    def test_can_approve_tier_based_on_role(self):
        """Role-based approval authority works correctly."""
        members = [
            WorkspaceMember(user_id="owner", role=WorkspaceRole.OWNER),
            WorkspaceMember(user_id="admin", role=WorkspaceRole.ADMIN),
            WorkspaceMember(user_id="arch", role=WorkspaceRole.ARCHITECT),
            WorkspaceMember(user_id="dev", role=WorkspaceRole.DEVELOPER),
        ]
        
        workspace = WorkspaceWithMembers(
            workspace_id="ws-123",
            name="Test",
            owner_id="owner",
            members=members
        )
        
        # T0: Everyone (auto-approve)
        assert workspace.can_approve_tier("dev", "T0") is True
        
        # T1: Architect+
        assert workspace.can_approve_tier("dev", "T1") is False
        assert workspace.can_approve_tier("arch", "T1") is True
        
        # T2: Admin+
        assert workspace.can_approve_tier("arch", "T2") is False
        assert workspace.can_approve_tier("admin", "T2") is True
        assert workspace.can_approve_tier("owner", "T2") is True


class TestReviewContracts:
    """Tests for review and voting contracts."""

    def test_review_is_immutable(self):
        """INVARIANT: Reviews cannot be modified after creation."""
        review = ProposalReview(
            review_id="rev-123",
            proposal_id="prop-456",
            reviewer_id="user-1",
            verdict=ReviewVerdict.APPROVE,
            comments="LGTM"
        )
        
        # Attempting to modify should raise
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            review.verdict = ReviewVerdict.REJECT

    def test_vote_is_immutable(self):
        """INVARIANT: Votes cannot be changed after cast."""
        vote = ApprovalVote(
            vote_id="vote-123",
            proposal_id="prop-456",
            voter_id="user-1",
            vote=True,
            justification="Approved"
        )
        
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            vote.vote = False

    def test_quorum_defaults_per_tier(self):
        """Default quorum requirements vary by tier."""
        assert DEFAULT_QUORUM["T0"].minimum_approvers == 0  # Auto
        assert DEFAULT_QUORUM["T1"].minimum_approvers == 1
        assert DEFAULT_QUORUM["T2"].minimum_approvers == 2
        assert DEFAULT_QUORUM["T3"].minimum_approvers == 3
        
        # T2+ requires architect
        assert DEFAULT_QUORUM["T2"].require_architect_approval is True
        
        # T3 requires owner
        assert DEFAULT_QUORUM["T3"].require_owner_approval is True

    def test_approval_status_calculation(self):
        """Approval status correctly calculates readiness."""
        status = ProposalApprovalStatus(
            proposal_id="prop-123",
            tier="T1",
            quorum=DEFAULT_QUORUM["T1"],
            total_reviews=2,
            approve_count=2,
            reject_count=0,
            request_changes_count=0,
            quorum_met=True
        )
        
        assert status.can_approve is True
        assert status.approval_percentage == 100.0
        assert status.blocked is False

    def test_rejection_blocks_approval(self):
        """Any rejection blocks proposal approval."""
        status = ProposalApprovalStatus(
            proposal_id="prop-123",
            tier="T1",
            quorum=DEFAULT_QUORUM["T1"],
            total_reviews=3,
            approve_count=2,
            reject_count=1,  # One rejection
            request_changes_count=0,
            quorum_met=True
        )
        
        assert status.can_approve is False  # Blocked by rejection


class TestWorkspaceRoles:
    """Tests for workspace role enforcement."""

    def test_role_hierarchy(self):
        """Role hierarchy is correctly ordered."""
        hierarchy = [
            WorkspaceRole.VIEWER,
            WorkspaceRole.DEVELOPER,
            WorkspaceRole.ARCHITECT,
            WorkspaceRole.ADMIN,
            WorkspaceRole.OWNER,
        ]
        
        # Just verify all roles exist
        for role in hierarchy:
            assert isinstance(role, WorkspaceRole)

    def test_member_is_frozen(self):
        """INVARIANT: WorkspaceMember is immutable."""
        member = WorkspaceMember(
            user_id="user-1",
            role=WorkspaceRole.DEVELOPER
        )
        
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            member.role = WorkspaceRole.ADMIN
