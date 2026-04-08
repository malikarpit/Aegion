"""
Unit tests for SessionManager — Phase 69.

Tests session lifecycle and ownership covering:
  - Session creation
  - Session retrieval
  - Ownership claiming (normal + forced)
  - Ownership transfer initiation
  - Ownership release
  - Write permission checks
  - Session close
  - Artifact management
  - Error cases
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.services.session_manager import SessionManager
from app.models.session import SessionStatus


@pytest.fixture
def manager():
    """Create SessionManager with mocked stores."""
    mgr = SessionManager()
    mgr._session_store = MagicMock()
    mgr._session_store.save = AsyncMock()
    mgr._session_store.load = AsyncMock()
    mgr._ownership_store = MagicMock()
    mgr._ownership_store.save = AsyncMock()
    mgr._ownership_store.load = AsyncMock()
    return mgr


class TestSessionCreation:
    @pytest.mark.asyncio
    async def test_create_session_returns_session(self, manager):
        """Creating a session should return a valid Session object."""
        with patch('app.services.audit_store.get_audit_store') as mock_audit:
            mock_audit.return_value.record = MagicMock()
            session = await manager.create_session("ws-test", "user-1")

        assert session is not None
        assert session.session_id.startswith("sess-")
        assert session.owner_id == "user-1"
        assert session.workspace_id == "ws-test"
        assert session.status == SessionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_create_session_saves_to_store(self, manager):
        """Session and ownership should be persisted."""
        with patch('app.services.audit_store.get_audit_store') as mock_audit:
            mock_audit.return_value.record = MagicMock()
            await manager.create_session("ws-test", "user-1")

        assert manager._session_store.save.call_count == 1
        assert manager._ownership_store.save.call_count == 1

    @pytest.mark.asyncio
    async def test_create_session_records_audit(self, manager):
        """Session creation should produce an audit event."""
        with patch('app.services.audit_store.get_audit_store') as mock_audit:
            mock_store = MagicMock()
            mock_audit.return_value = mock_store

            await manager.create_session("ws-test", "user-1")

            mock_store.record.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_id_uniqueness(self, manager):
        """Multiple sessions should have unique IDs."""
        with patch('app.services.audit_store.get_audit_store') as mock_audit:
            mock_audit.return_value.record = MagicMock()
            s1 = await manager.create_session("ws", "u1")
            s2 = await manager.create_session("ws", "u1")

        assert s1.session_id != s2.session_id


class TestSessionRetrieval:
    @pytest.mark.asyncio
    async def test_get_session(self, manager):
        """Should delegate to store.load."""
        manager._session_store.load.return_value = MagicMock()
        result = await manager.get_session("sess-123", "ws-test")
        manager._session_store.load.assert_called_once_with("ws-test", "sess-123")

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, manager):
        """Should return None for nonexistent session."""
        manager._session_store.load.return_value = None
        result = await manager.get_session("sess-nonexistent", "ws-test")
        assert result is None


class TestOwnership:
    @pytest.mark.asyncio
    async def test_claim_ownership_unclaimed(self, manager):
        """Claiming an unclaimed session should succeed."""
        from app.models.collaboration import SessionOwnership, OwnershipStatus
        ownership = SessionOwnership(
            session_id="sess-1", workspace_id="ws",
            owner_id=None, status=OwnershipStatus.RELEASED,
        )
        manager._ownership_store.load.return_value = ownership

        result = await manager.claim_ownership("sess-1", "user-2")
        assert result.owner_id == "user-2"
        assert result.status == OwnershipStatus.CLAIMED

    @pytest.mark.asyncio
    async def test_claim_ownership_already_owned_fails(self, manager):
        """Claiming a session owned by another user should fail."""
        from app.models.collaboration import SessionOwnership, OwnershipStatus
        from app.core.errors import GovernanceError
        ownership = SessionOwnership(
            session_id="sess-1", workspace_id="ws",
            owner_id="user-1", status=OwnershipStatus.CLAIMED,
        )
        manager._ownership_store.load.return_value = ownership

        with pytest.raises(GovernanceError):
            await manager.claim_ownership("sess-1", "user-2", force=False)

    @pytest.mark.asyncio
    async def test_force_claim_ownership(self, manager):
        """Force claiming should override existing owner."""
        from app.models.collaboration import SessionOwnership, OwnershipStatus
        ownership = SessionOwnership(
            session_id="sess-1", workspace_id="ws",
            owner_id="user-1", status=OwnershipStatus.CLAIMED,
        )
        manager._ownership_store.load.return_value = ownership

        result = await manager.claim_ownership("sess-1", "user-2", force=True)
        assert result.owner_id == "user-2"

    @pytest.mark.asyncio
    async def test_transfer_ownership(self, manager):
        """Owner should be able to initiate transfer."""
        from app.models.collaboration import SessionOwnership, OwnershipStatus
        ownership = SessionOwnership(
            session_id="sess-1", workspace_id="ws",
            owner_id="user-1", status=OwnershipStatus.CLAIMED,
        )
        manager._ownership_store.load.return_value = ownership

        result = await manager.transfer_ownership("sess-1", "user-1", "user-2")
        assert result.status == OwnershipStatus.PENDING
        assert result.pending_transfer_to == "user-2"

    @pytest.mark.asyncio
    async def test_transfer_by_non_owner_fails(self, manager):
        """Non-owner cannot initiate transfer."""
        from app.models.collaboration import SessionOwnership, OwnershipStatus
        from app.core.errors import GovernanceError
        ownership = SessionOwnership(
            session_id="sess-1", workspace_id="ws",
            owner_id="user-1", status=OwnershipStatus.CLAIMED,
        )
        manager._ownership_store.load.return_value = ownership

        with pytest.raises(GovernanceError):
            await manager.transfer_ownership("sess-1", "user-2", "user-3")

    @pytest.mark.asyncio
    async def test_release_ownership(self, manager):
        """Owner should be able to release ownership."""
        from app.models.collaboration import SessionOwnership, OwnershipStatus
        ownership = SessionOwnership(
            session_id="sess-1", workspace_id="ws",
            owner_id="user-1", status=OwnershipStatus.CLAIMED,
        )
        manager._ownership_store.load.return_value = ownership

        result = await manager.release_ownership("sess-1", "user-1")
        assert result.status == OwnershipStatus.RELEASED
        assert result.owner_id is None


class TestWritePermissions:
    @pytest.mark.asyncio
    async def test_owner_has_write_permission(self, manager):
        from app.models.collaboration import SessionOwnership, OwnershipStatus
        ownership = SessionOwnership(
            session_id="sess-1", workspace_id="ws",
            owner_id="user-1", status=OwnershipStatus.CLAIMED,
        )
        manager._ownership_store.load.return_value = ownership

        assert await manager.check_write_permission("sess-1", "user-1") is True

    @pytest.mark.asyncio
    async def test_non_owner_no_write_permission(self, manager):
        from app.models.collaboration import SessionOwnership, OwnershipStatus
        ownership = SessionOwnership(
            session_id="sess-1", workspace_id="ws",
            owner_id="user-1", status=OwnershipStatus.CLAIMED,
        )
        manager._ownership_store.load.return_value = ownership

        assert await manager.check_write_permission("sess-1", "user-2") is False

    @pytest.mark.asyncio
    async def test_no_ownership_no_write(self, manager):
        manager._ownership_store.load.return_value = None
        assert await manager.check_write_permission("sess-1", "user-1") is False


class TestSessionLifecycle:
    @pytest.mark.asyncio
    async def test_close_session(self, manager):
        """Closing a session should set status to CLOSED."""
        from app.models.session import Session
        session = Session(
            session_id="sess-1", owner_id="user-1",
            workspace_id="ws", status=SessionStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            last_activity_at=datetime.now(timezone.utc),
        )
        manager._session_store.load.return_value = session

        with patch('app.services.audit_store.get_audit_store') as mock_audit:
            mock_audit.return_value.record = MagicMock()
            result = await manager.close_session("sess-1")

        assert result.status == SessionStatus.CLOSED
        assert result.closed_at is not None

    @pytest.mark.asyncio
    async def test_close_nonexistent_session_raises(self, manager):
        """Closing a nonexistent session should raise."""
        from app.core.errors import ResourceNotFoundError
        manager._session_store.load.return_value = None

        with pytest.raises(ResourceNotFoundError):
            await manager.close_session("sess-nonexistent")
