
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.collaboration.handoff import HandoffService
from app.models.conflict import Conflict, ConflictSeverity
from app.services.noesis.graph_service import GraphService
from datetime import datetime

@pytest.fixture
def mock_ownership():
    mock = MagicMock()
    mock.get_owner.return_value = "user1"
    mock.get_participants.return_value = [MagicMock(user_id="user1"), MagicMock(user_id="user2")]
    return mock

@pytest.fixture
def mock_attribution():
    return MagicMock()

@pytest.fixture
def mock_graph():
    mock = AsyncMock(spec=GraphService)
    # Mock proposals
    p1 = MagicMock()
    p1.properties = {"title": "Test Proposal", "status": "pending", "tier": "T2"}
    p1.node_id = "prop-1"
    
    mock.list_proposals.return_value = [p1]
    mock.list_decisions.return_value = []
    return mock

@pytest.fixture
def mock_conflicts():
    mock = MagicMock()
    c1 = Conflict(
        conflict_id="c1",
        workspace_id="ws1",
        rule_id="r1",
        severity=ConflictSeverity.HIGH,
        message="Test Conflict",
        file_path="test.py",
        detected_at=datetime.utcnow()
    )
    mock.get_active_conflicts.return_value = [c1]
    return mock

@pytest.fixture
def handoff_service(mock_ownership, mock_attribution, mock_graph, mock_conflicts):
    service = HandoffService()
    service.ownership = mock_ownership
    service.attribution = mock_attribution
    # Mock graph provider specifically
    with patch('app.services.collaboration.handoff.get_shared_graph_service', return_value=mock_graph):
        service.conflicts = mock_conflicts
        yield service

@pytest.mark.asyncio
async def test_generate_handoff_summary(handoff_service, mock_graph):
    # Setup - mock the internal call to get_shared_graph_service inside the method if needed
    # But we patched it in fixture.
    # The method calls get_shared_graph_service() inside.
    
    summary = await handoff_service.generate_handoff_summary("session-123")
    
    assert "# Handoff Report: Session `session-123`" in summary
    assert "**Owner:** `user1`" in summary
    assert "**Participants:** user1, user2" in summary
    
    # Check Active Context
    assert "Active Context" in summary
    assert "**Proposals Pending**: 1" in summary
    assert "**Governance Conflicts**: 1" in summary
    
    # Check Conflicts Section
    assert "🚨 Active Conflicts" in summary
    assert "Test Conflict" in summary
    
    # Check Proposals Section
    assert "📝 Pending Proposals" in summary
    assert "[T2] **Test Proposal**" in summary
    
    # Check Pending Actions
    assert "Pending Actions" in summary
    assert "[ ] Review Proposal `prop-1`" in summary
    assert "[ ] Resolve Conflict `c1`" in summary
