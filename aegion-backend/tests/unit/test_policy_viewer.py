
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext, Role
from app.services.archon.registry import PolicyRegistry
import pytest


@pytest.fixture(autouse=True)
def override_auth():
    """Fixture-scoped auth override — survives test ordering."""
    app.dependency_overrides[get_current_user] = lambda: AuthorityContext(
        user_id="user-viewer",
        role=Role.DEVELOPER,
        can_approve_t1=False,
        can_approve_t2=False
    )
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_get_governance_policy():
    """
    Test GET /council/policy returns the active policy.
    """
    client = TestClient(app)
    response = client.get(
        "/api/v1/council/policy", 
        headers={
            "Authorization": "Bearer mock",
            "X-Aegion-Session": "sess-viewer-test",
            "X-Aegion-Intent": "policy.view"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify key structure from PolicyRegistry defaults
    assert "version" in data
    assert "effective_from" in data
    assert "tier_thresholds" in data
    assert "critical_modules" in data
    assert "forbidden_patterns" in data
    assert "invariants" in data
    
    # Check Thresholds
    thresholds = data["tier_thresholds"]
    assert "blast_radius_t1_limit" in thresholds
    assert thresholds["blast_radius_t1_limit"] == 5
    assert thresholds["blast_radius_t2_limit"] == 20
    
    # Check Invariants
    assert "AI_CANNOT_DIRECTLY_WRITE_DB" in data["invariants"]
