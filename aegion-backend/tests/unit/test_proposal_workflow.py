import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext
from app.contracts.decision_intent import DecisionTier
from unittest.mock import patch, MagicMock

@pytest.fixture
def client():
    return TestClient(app)

def create_mock_user(user_id="user-1", tier_auth=True):
    return AuthorityContext(
        user_id=user_id,
        scopes=["read", "write"],
        role="architect",
        can_approve_t1=True,
        can_approve_t2=tier_auth
    )


def test_proposal_self_approval_blocked(client):
    """Test that self-approval is blocked for T2 decisions."""
    
    headers = {
        "X-Aegion-Session": "sess-1",
        "X-Aegion-Intent": "proposal.create"
    }
    
    # 1. Create Proposal as User A (T2)
    user_a = create_mock_user("user-a")
    app.dependency_overrides[get_current_user] = lambda: user_a
    
    # Mock Archon to return T2 via explain_tier
    explain_t2 = {
        "tier": "T2",
        "quorum": 2,
        "evidence_required": 2,
        "self_approval_allowed": False,
        "reasons": ["Impact: system_wide, Reversibility: difficult → base tier T2"]
    }
    with patch("app.services.archon.gates.ArchonGates.explain_tier", return_value=explain_t2):
        create_payload = {
            "session_id": "sess-1",
            "title": "High Impact Change",
            "description": "Changes core system",
            "impact_level": "system_wide",
            "reversibility": "difficult",
            "reasoning": {
                "problem_framing": "Fix bug",
                "assumptions": [],
                "constraints": [],
                "alternatives_considered": []
            },
            "uncertainty": {
                "level": "medium",
                "confidence_score": 0.7,
                "reasoning": "Standard risk assessment",
                "sources": [],
                "is_blocking": False
            }
        }
        
        response = client.post("/api/v1/proposals/", json=create_payload, headers=headers)
        if response.status_code != 200:
            print(response.json())
        assert response.status_code == 200
        proposal_id = response.json()["proposal_id"]
        tier = response.json()["tier"]
        assert tier == "T2"

    # 2. Try to Approve as User A (Should Fail)
    approve_payload = {
        "evidence_ids": ["ev-1"], 
        "justification": "Looks good to me"
    }
    
    # Mock validate_evidence to pass
    with patch("app.services.archon.gates.ArchonGates.validate_evidence", return_value=(True, [])):
        response = client.post(f"/api/v1/proposals/{proposal_id}/approve", json=approve_payload, headers=headers)
        assert response.status_code == 400
        error_detail = response.json()["detail"]
        assert "Self-approval blocked" in error_detail or "Separation" in error_detail

    # 3. Approve as User B (Should Succeed)
    user_b = create_mock_user("user-b")
    app.dependency_overrides[get_current_user] = lambda: user_b
    
    # Mock InvariantEngine to bypass the catch-22 where first approval is blocked because count < 2
    from app.services.archon.invariant_engine import InvariantResult
    
    with patch("app.services.archon.gates.ArchonGates.validate_evidence", return_value=(True, [])), \
         patch("app.services.archon.opa.get_opa_service") as mock_opa, \
         patch("app.services.archon.invariant_engine.InvariantEngine.evaluate_for_approval") as mock_inv:
        
        mock_opa.return_value.evaluate_policy.return_value = {"allow": True}
        mock_inv.return_value = InvariantResult(passed=True, violations=[])
        
        response = client.post(f"/api/v1/proposals/{proposal_id}/approve", json=approve_payload, headers=headers)
        if response.status_code != 200:
            print(response.json())
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    app.dependency_overrides = {}
