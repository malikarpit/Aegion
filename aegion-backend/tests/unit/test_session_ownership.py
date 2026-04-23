"""
Tests for Collaboration Session Ownership — Section 1.12 (pure unit tests).

Covers session lifecycle, participant management, ownership transfer,
activity tracking, and cursor position updates WITHOUT external deps.
"""

import pytest

from app.services.collaboration.session_ownership import (
    SessionOwnership,
    ParticipantRole,
    get_session_ownership,
)


class TestSessionCreation:
    def test_create_session(self):
        svc = SessionOwnership()
        session = svc.create_session("sess-1", "user-A")
        assert session.session_id == "sess-1"
        assert session.owner_id == "user-A"
        assert "user-A" in session.participants

    def test_owner_has_owner_role(self):
        svc = SessionOwnership()
        session = svc.create_session("sess-1", "user-A")
        assert session.participants["user-A"].role == ParticipantRole.OWNER

    def test_get_owner(self):
        svc = SessionOwnership()
        svc.create_session("sess-1", "user-A")
        assert svc.get_owner("sess-1") == "user-A"

    def test_is_owner_true(self):
        svc = SessionOwnership()
        svc.create_session("sess-1", "user-A")
        assert svc.is_owner("sess-1", "user-A") is True

    def test_is_owner_false(self):
        svc = SessionOwnership()
        svc.create_session("sess-1", "user-A")
        assert svc.is_owner("sess-1", "user-B") is False

    def test_nonexistent_session(self):
        svc = SessionOwnership()
        assert svc.get_owner("nonexistent") is None
        assert svc.is_owner("nonexistent", "u") is False


class TestParticipants:
    def test_join_session(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        p = svc.join_session("s1", "B")
        assert p is not None
        assert p.role == ParticipantRole.COLLABORATOR

    def test_join_as_reviewer(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        p = svc.join_session("s1", "B", role=ParticipantRole.REVIEWER)
        assert p.role == ParticipantRole.REVIEWER

    def test_join_as_owner_demoted(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        p = svc.join_session("s1", "B", role=ParticipantRole.OWNER)
        assert p.role == ParticipantRole.COLLABORATOR

    def test_join_nonexistent(self):
        svc = SessionOwnership()
        assert svc.join_session("nope", "B") is None

    def test_get_participants_count(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        svc.join_session("s1", "B")
        svc.join_session("s1", "C")
        assert len(svc.get_participants("s1")) == 3

    def test_leave(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        svc.join_session("s1", "B")
        assert svc.leave_session("s1", "B") is True
        assert len(svc.get_participants("s1")) == 1

    def test_owner_cannot_leave(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        assert svc.leave_session("s1", "A") is False

    def test_leave_nonexistent_participant(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        assert svc.leave_session("s1", "X") is False


class TestOwnershipTransfer:
    def test_transfer(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        svc.join_session("s1", "B")
        assert svc.transfer_ownership("s1", "A", "B") is True
        assert svc.get_owner("s1") == "B"

    def test_old_owner_demoted(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        svc.join_session("s1", "B")
        svc.transfer_ownership("s1", "A", "B")
        parts = {p.user_id: p for p in svc.get_participants("s1")}
        assert parts["A"].role == ParticipantRole.COLLABORATOR
        assert parts["B"].role == ParticipantRole.OWNER

    def test_non_owner_cannot_transfer(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        svc.join_session("s1", "B")
        assert svc.transfer_ownership("s1", "B", "A") is False

    def test_transfer_to_non_participant(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        assert svc.transfer_ownership("s1", "A", "X") is False


class TestActivityCursor:
    def test_update_activity(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        # Just verify no exception is raised
        svc.update_activity("s1", "A")
        # Participant should still exist after update
        assert "A" in svc._sessions["s1"].participants

    def test_update_cursor(self):
        svc = SessionOwnership()
        svc.create_session("s1", "A")
        svc.update_cursor("s1", "A", {"line": 42, "col": 10})
        assert svc._sessions["s1"].participants["A"].cursor_position == {"line": 42, "col": 10}


class TestSingleton:
    def test_singleton(self):
        import app.services.collaboration.session_ownership as so
        so._session_ownership = None
        s1 = get_session_ownership()
        s2 = get_session_ownership()
        assert s1 is s2
        so._session_ownership = None
