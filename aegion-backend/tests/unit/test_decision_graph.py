"""
Test Decision Graph (Phase 34 - AG-016).

Tests for graph visualization endpoint and data integrity.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, AuthorityContext
from app.services.noesis.graph_service import GraphService, GraphNodeType, GraphEdgeType
from app.ports.knowledge_graph import GraphNode



@pytest.fixture
def client():
    mock_user = AuthorityContext(user_id="test-arch", role="admin")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    c = TestClient(app)
    c.headers.update({
        "X-Aegion-Session": "test-session-graph",
        "X-Aegion-Intent": "graph",
    })
    yield c
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_get_decision_graph_empty(client):
    """Test retrieving graph when empty."""
    response = client.get("/api/v1/decisions/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


@pytest.mark.anyio
async def test_get_decision_graph_with_data(client):
    """Test graph retrieval with nodes and edges."""
    from app.api.v1.analytics import _graph_service
    
    # Setup test data
    ws = "graph-test-ws"
    
    # Create decisions
    d1 = await _graph_service.graph.add_node(
        node_type=GraphNodeType.DECISION,
        node_id="dec-1",
        properties={"title": "Use Python", "workspace_id": ws, "tier": "T1"}
    )
    d2 = await _graph_service.graph.add_node(
        node_type=GraphNodeType.DECISION,
        node_id="dec-2",
        properties={"title": "Use Rust", "workspace_id": ws, "tier": "T1"}
    )
    
    # Link them (supersedes)
    await _graph_service.graph.add_edge(
        source_id="dec-2",
        target_id="dec-1",
        edge_type=GraphEdgeType.SUPERSEDES
    )
    
    # Query via API
    response = client.get("/api/v1/decisions/graph", headers={"X-Workspace-Id": ws})
    assert response.status_code == 200
    data = response.json()
    
    nodes = data["nodes"]
    edges = data["edges"]
    
    node_ids = {n["node_id"] for n in nodes}
    assert "dec-1" in node_ids
    assert "dec-2" in node_ids
    
    assert len(edges) >= 1
    edge = next((e for e in edges if e["source_id"] == "dec-2" and e["target_id"] == "dec-1"), None)
    assert edge is not None
    assert edge["edge_type"] == "supersedes"
    
    assert edge["edge_type"] == "supersedes"
    
    # Cleanup (optional if using in-memory store that resets)


@pytest.mark.anyio
async def test_get_decision_graph_integrity(client):
    """Test that graph does not contain orphan edges."""
    from app.api.v1.analytics import _graph_service
    
    # Create an edge without a valid target (simulated corruption or partial sync)
    # Note: In a real graph DB, constraints usually prevent this, but we test the API response filtering
    
    # 1. Create a valid node
    d1 = await _graph_service.graph.add_node(
        node_type=GraphNodeType.DECISION,
        node_id="dec-orphan-test",
        properties={"title": "Orphan Test", "workspace_id": "ws-integrity"}
    )
    
    # 2. force-add an edge to a non-existent node (using backend port directly if possible, or mocked)
    # For now, we test that the SERVICE layer filters out edges where target is not in the node list
    
    # Manually add an edge to a missing node "dec-missing"
    await _graph_service.graph.add_edge(
        source_id="dec-orphan-test",
        target_id="dec-missing",
        edge_type=GraphEdgeType.RELATED_TO
    )
    
    response = client.get("/api/v1/decisions/graph", headers={"X-Workspace-Id": "ws-integrity"})
    assert response.status_code == 200
    data = response.json()
    
    # The service `get_adr_graph` logic explicitly filters:
    # `if edge.target_id in node_ids ...`
    
    edges = data["edges"]
    # Should NOT contain the edge to "dec-missing"
    orphan_edges = [e for e in edges if e["target_id"] == "dec-missing"]
    assert len(orphan_edges) == 0
