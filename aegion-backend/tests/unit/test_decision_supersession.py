import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_user():
    return AuthorityContext(
        user_id="user-1",
        scopes=["read", "write"],
        role="developer",
        can_approve_t1=True
    )

@pytest.fixture
def override_auth(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides = {}

from anyio import run

def test_supersede_decision(client, override_auth):
    """
    Test atomic supersession of a decision.
    Verifies S-2: "To 'change' a decision, create a new decision that supersedes it."
    """
    async def _setup():
        # Seed original decision in graph
        from app.api.v1.analytics import _graph_service
        from app.ports.knowledge_graph import GraphNodeType
        
        original_id = "dec-orig-123"
        await _graph_service.graph.add_node(
            node_type=GraphNodeType.DECISION,
            node_id=original_id,
            properties={
                "proposal_id": "prop-orig",
                "workspace_id": "default",
                "decided_at": datetime.now(timezone.utc).isoformat(),
                "verdict": "approved"
            }
        )
        
        # Seed the new proposal that will be used for supersession
        from app.ports.knowledge_graph import GraphNodeType as GNT
        await _graph_service.graph.add_node(
            node_type=GNT.PROPOSAL,
            node_id="prop-new-456",
            properties={
                "status": "approved",
                "title": "Updated architecture approach",
                "session_id": "sess-test-1",
                "impact_level": "local",
                "reversibility": "easy",
                "tier": "T1",
                "origin": "human",
            }
        )
    
    # Run async setup
    run(_setup)
    
    original_id = "dec-orig-123"
    
    payload = {
        "new_proposal_id": "prop-new-456",
        "justification": "Original decision was based on outdated assumptions."
    }
    
    headers = {
        "X-Aegion-Session": "sess-test-1",
        "X-Aegion-Intent": "test_supersession"
    }
    
    response = client.post(
        f"/api/v1/decisions/{original_id}/supersede",
        json=payload,
        headers=headers
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    
    # Check lineage data
    assert data["original_decision_id"] == original_id
    assert data["new_decision_id"] == "dec-prop-new-456"
    assert data["chain_position"] == 1
    assert "superseded_at" in data
    
    # Verify audit log (implied by 200 OK and presence of fields)

def test_get_lineage_chain(client, override_auth):
    """Test retrieving lineage chain."""
    
    async def _setup():
        # Seed chain: dec-lineage-1 -> dec-lineage-2 -> dec-lineage-3
        from app.api.v1.analytics import _graph_service
        from app.ports.knowledge_graph import GraphNodeType, GraphEdgeType
        
        # 1
        await _graph_service.graph.add_node(GraphNodeType.DECISION, "dec-lineage-1", {"decided_at": "2026-01-01T00:00:00Z"})
        # 2
        await _graph_service.graph.add_node(GraphNodeType.DECISION, "dec-lineage-2", {"decided_at": "2026-01-02T00:00:00Z"})
        await _graph_service.graph.add_edge("dec-lineage-2", "dec-lineage-1", GraphEdgeType.SUPERSEDES)
        # 3
        await _graph_service.graph.add_node(GraphNodeType.DECISION, "dec-lineage-3", {"decided_at": "2026-01-03T00:00:00Z"})
        await _graph_service.graph.add_edge("dec-lineage-3", "dec-lineage-2", GraphEdgeType.SUPERSEDES)
    
    run(_setup)
    
    decision_id = "dec-lineage-1"
    
    headers = {
        "X-Aegion-Session": "sess-test-1",
        "X-Aegion-Intent": "test_lineage"
    }
    
    response = client.get(f"/api/v1/decisions/{decision_id}/lineage", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3
    # Ordered by chain position
    assert data[0]["decision_id"] == "dec-lineage-1"
    assert data[1]["decision_id"] == "dec-lineage-2"
    assert data[2]["decision_id"] == "dec-lineage-3"
