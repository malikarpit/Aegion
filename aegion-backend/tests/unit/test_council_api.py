
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from app.main import app
from app.api.v1.council import get_council_service, get_current_user
from app.services.council.council_service import CouncilService
from app.domain.council import CouncilSession, CouncilVote, CouncilOpinion, CouncilRole
from datetime import datetime, timezone

client = TestClient(app)
client.headers = {
    "X-Aegion-Session": "test-session",
    "X-Aegion-Workspace": "ws-789",
    "X-Aegion-Intent": "council:read",
    "X-Correlation-ID": "test-correlation"
}

# Mock User
def mock_get_current_user():
    return MagicMock(user_id="user-123", permissions=["council:read"])

# Mock Service
mock_service = AsyncMock(spec=CouncilService)

# Helper to setup service return values
def setup_mock_service():
    session = CouncilSession(
        session_id="session-api-123",
        proposal_id="proposal-456",
        workspace_id="ws-789",
        status="completed",
        consensus=CouncilVote.SUPPORT,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        opinions=[
            CouncilOpinion(
                member_id="mem-1",
                proposal_id="proposal-456",
                vote=CouncilVote.SUPPORT,
                analysis="LGTM",
                confidence=0.9
            )
        ]
    )
    mock_service.get_session.return_value = session
    mock_service.get_sessions_for_proposal.return_value = [session]
    mock_service.get_transcript.return_value = {
        "session_id": session.session_id,
        "transcript": [{"member": "mem-1", "vote": "support", "analysis": "LGTM"}]
    }

# Override dependencies
app.dependency_overrides[get_current_user] = mock_get_current_user
app.dependency_overrides[get_council_service] = lambda: mock_service

def test_get_session():
    setup_mock_service()
    response = client.get("/api/v1/council/sessions/session-api-123")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "session-api-123"
    assert data["status"] == "completed"

def test_get_transcript():
    setup_mock_service()
    response = client.get("/api/v1/council/sessions/session-api-123/transcript")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "session-api-123"
    assert len(data["transcript"]) == 1

def test_get_proposal_sessions():
    setup_mock_service()
    response = client.get("/api/v1/council/proposals/proposal-456/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["proposal_id"] == "proposal-456"

def test_get_session_not_found():
    mock_service.get_session.return_value = None
    response = client.get("/api/v1/council/sessions/non-existent")
    assert response.status_code == 404

def test_get_governance_status_passed():
    mock_service.verify_governance.return_value = True
    response = client.get("/api/v1/council/proposals/proposal-passed/governance-status")
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is True
    assert data["proposal_id"] == "proposal-passed"

def test_get_governance_status_failed():
    mock_service.verify_governance.return_value = False
    response = client.get("/api/v1/council/proposals/proposal-failed/governance-status")
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is False
    assert data["proposal_id"] == "proposal-failed"
