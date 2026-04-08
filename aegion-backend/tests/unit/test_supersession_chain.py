"""
Aegion AG-004: Supersession Chain Integrity Tests.

Tests that supersession persists to graph, marks originals as superseded,
blocks re-supersession, and preserves ordered lineage chains.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from anyio import run
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import get_current_user, AuthorityContext
from app.ports.knowledge_graph import GraphNodeType, GraphEdgeType


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides = {}

@pytest.fixture
def mock_user():
    user = AuthorityContext(
        user_id="user-supersede",
        scopes=["read", "write"],
        role="architect",
        can_approve_t1=True,
        can_approve_t2=True
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return user


HEADERS = {
    "X-Aegion-Session": "sess-chain",
    "X-Aegion-Intent": "decision.supersede"
}


def _seed_decision_and_proposal(original_id: str, proposal_id: str):
    """Seed an original decision and an approved proposal in graph."""
    async def _setup():
        from app.api.v1.analytics import _graph_service
        # Original decision
        await _graph_service.graph.add_node(
            node_type=GraphNodeType.DECISION,
            node_id=original_id,
            properties={
                "proposal_id": "prop-orig",
                "workspace_id": "default",
                "decided_at": datetime.now(timezone.utc).isoformat(),
                "verdict": "approved",
                "status": "approved",
                "title": "Original Decision"
            }
        )
        # Approved proposal for supersession
        await _graph_service.graph.add_node(
            node_type=GraphNodeType.PROPOSAL,
            node_id=proposal_id,
            properties={
                "status": "approved",
                "title": "Superseding Proposal",
                "session_id": "sess-chain",
                "impact_level": "local",
                "reversibility": "easy",
                "tier": "T1",
                "origin": "human",
            }
        )
    run(_setup)


# ============================================================
# Test 1: Supersession persists new decision node
# ============================================================

class TestPersistNewDecision:
    def test_supersede_creates_new_decision_in_graph(self, client, mock_user):
        """After supersession, the new decision should exist in the graph."""
        _seed_decision_and_proposal("dec-persist-001", "prop-persist-001")

        response = client.post(
            "/api/v1/decisions/dec-persist-001/supersede",
            json={
                "new_proposal_id": "prop-persist-001",
                "justification": "Better approach found."
            },
            headers=HEADERS
        )
        assert response.status_code == 200
        new_id = response.json()["new_decision_id"]

        # Verify new node in graph
        async def _check():
            from app.api.v1.analytics import _graph_service
            node = await _graph_service.graph.get_node(new_id)
            assert node is not None
            assert node.properties.get("status") == "approved"
            assert node.properties.get("supersedes") == "dec-persist-001"
        run(_check)


# ============================================================
# Test 2: Original marked as superseded
# ============================================================

class TestOriginalMarkedSuperseded:
    def test_original_status_becomes_superseded(self, client, mock_user):
        """After supersession, the original decision status should be 'superseded'."""
        _seed_decision_and_proposal("dec-mark-001", "prop-mark-001")

        client.post(
            "/api/v1/decisions/dec-mark-001/supersede",
            json={
                "new_proposal_id": "prop-mark-001",
                "justification": "Updated requirements."
            },
            headers=HEADERS
        )

        async def _check():
            from app.api.v1.analytics import _graph_service
            node = await _graph_service.graph.get_node("dec-mark-001")
            assert node is not None
            assert node.properties.get("status") == "superseded"
            assert "superseded_by" in node.properties
        run(_check)


# ============================================================
# Test 3: SUPERSEDES edge created
# ============================================================

class TestSupersedesEdge:
    def test_supersedes_edge_exists(self, client, mock_user):
        """A SUPERSEDES edge from new → original should exist."""
        _seed_decision_and_proposal("dec-edge-001", "prop-edge-001")

        response = client.post(
            "/api/v1/decisions/dec-edge-001/supersede",
            json={
                "new_proposal_id": "prop-edge-001",
                "justification": "Architecture shift."
            },
            headers=HEADERS
        )
        new_id = response.json()["new_decision_id"]

        async def _check():
            from app.api.v1.analytics import _graph_service
            edges = await _graph_service.graph.get_edges(
                source_id=new_id,
                edge_type=GraphEdgeType.SUPERSEDES
            )
            assert len(edges) >= 1
            assert any(e.target_id == "dec-edge-001" for e in edges)
        run(_check)


# ============================================================
# Test 4: Re-supersession of superseded decision blocked
# ============================================================

class TestReSupersessionBlocked:
    def test_cannot_supersede_already_superseded(self, client, mock_user):
        """Attempting to supersede an already-superseded decision returns 400."""
        _seed_decision_and_proposal("dec-resup-001", "prop-resup-001")

        # First supersession — should succeed
        resp1 = client.post(
            "/api/v1/decisions/dec-resup-001/supersede",
            json={
                "new_proposal_id": "prop-resup-001",
                "justification": "First supersession."
            },
            headers=HEADERS
        )
        assert resp1.status_code == 200

        # Seed another approved proposal
        async def _seed_second():
            from app.api.v1.analytics import _graph_service
            await _graph_service.graph.add_node(
                node_type=GraphNodeType.PROPOSAL,
                node_id="prop-resup-002",
                properties={
                    "status": "approved",
                    "title": "Second supersession attempt",
                    "session_id": "sess-chain",
                    "impact_level": "local",
                    "reversibility": "easy",
                    "tier": "T1",
                    "origin": "human",
                }
            )
        run(_seed_second)

        # Second supersession — should fail (original already superseded)
        resp2 = client.post(
            "/api/v1/decisions/dec-resup-001/supersede",
            json={
                "new_proposal_id": "prop-resup-002",
                "justification": "Should fail."
            },
            headers=HEADERS
        )
        assert resp2.status_code == 400
        assert "already superseded" in resp2.json()["detail"]


# ============================================================
# Test 5: Lineage chain preserves order
# ============================================================

class TestLineageOrder:
    def test_lineage_chain_ordered(self, client, mock_user):
        """Lineage should order: 0 (root) → 1 → 2."""
        # Seed chain: dec-chain-A → dec-chain-B → dec-chain-C
        async def _setup():
            from app.api.v1.analytics import _graph_service
            await _graph_service.graph.add_node(
                GraphNodeType.DECISION, "dec-chain-A",
                {"decided_at": "2026-01-01T00:00:00Z", "status": "approved"}
            )
            await _graph_service.graph.add_node(
                GraphNodeType.DECISION, "dec-chain-B",
                {"decided_at": "2026-01-02T00:00:00Z", "status": "approved"}
            )
            await _graph_service.graph.add_edge("dec-chain-B", "dec-chain-A", GraphEdgeType.SUPERSEDES)
            await _graph_service.graph.add_node(
                GraphNodeType.DECISION, "dec-chain-C",
                {"decided_at": "2026-01-03T00:00:00Z", "status": "approved"}
            )
            await _graph_service.graph.add_edge("dec-chain-C", "dec-chain-B", GraphEdgeType.SUPERSEDES)
        run(_setup)

        response = client.get(
            "/api/v1/decisions/dec-chain-A/lineage",
            headers=HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["decision_id"] == "dec-chain-A"
        assert data[0]["chain_position"] == 0
        assert data[1]["decision_id"] == "dec-chain-B"
        assert data[1]["chain_position"] == 1
        assert data[2]["decision_id"] == "dec-chain-C"
        assert data[2]["chain_position"] == 2
