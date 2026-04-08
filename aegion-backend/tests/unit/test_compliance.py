
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.archon.compliance import ComplianceExporter
from app.services.noesis.graph_service import GraphService
from app.ports.knowledge_graph import GraphEdgeType

@pytest.fixture
def mock_graph():
    mock = AsyncMock(spec=GraphService)
    # Mock proposal
    p1 = MagicMock()
    p1.properties = {"title": "Test Proposal", "tier": "T1", "description": "Needs changes.", "verdict": "approved"}
    p1.node_id = "prop-1"
    mock.get_proposal.return_value = p1
    
    # Mock evidence
    e1 = MagicMock()
    e1.properties = {"evidence_type": "automated_test", "summary": "Tests Passed"}
    mock.get_evidence_for_proposal.return_value = [e1]
    
    # Mock decision edges
    # Proposal -> SUPERSEDES -> Decision
    edge1 = MagicMock()
    edge1.target_id = "dec-1"
    
    # Decision -> APPROVED_BY -> User
    edge2 = MagicMock()
    edge2.target_id = "user1"
    
    def get_edges_side_effect(source_id, edge_type):
        if source_id == "prop-1" and edge_type == GraphEdgeType.SUPERSEDES:
            return [edge1]
        if source_id == "dec-1" and edge_type == GraphEdgeType.APPROVED_BY:
            return [edge2]
        return []
        
    mock.get_edges.side_effect = get_edges_side_effect
    
    # Mock decision node
    d1 = MagicMock()
    d1.properties = {"verdict": "approved"}
    d1.node_id = "dec-1"
    
    def get_node_side_effect(node_id):
        if node_id == "dec-1":
            return d1
        if node_id == "prop-1":
            return p1
        return None
        
    mock.get_node.side_effect = get_node_side_effect
    
    return mock

@pytest.fixture
def compliance_exporter(mock_graph):
    exporter = ComplianceExporter()
    # Mock graph provider specifically
    with patch('app.services.archon.compliance.get_shared_graph_service', return_value=mock_graph):
        yield exporter

@pytest.mark.asyncio
async def test_generate_pr_description(compliance_exporter, mock_graph):
    summary = await compliance_exporter.generate_pr_description("prop-1")
    
    assert "## 🧠 Logic & Compliance" in summary
    assert "**Proposal:** Test Proposal" in summary
    assert "**Tier:** T1" in summary
    assert "**Status:** Approved" in summary
    
    assert "### Reasoning" in summary
    assert "Needs changes." in summary
    
    assert "### Evidence" in summary
    assert "[automated_test] Tests Passed" in summary
    
    assert "### 🛡 Architect/Council Certificate" in summary
    assert "Decision `dec-1` confirmed by `user1`" in summary
