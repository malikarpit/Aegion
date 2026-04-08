"""
Aegion Phase 3 Unit Tests - Dependency Graph.

Tests for EDG nodes, edges, and staleness propagation.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from pydantic import ValidationError

from app.contracts.dependency_node import (
    DependencyNode, DependencyEdge, NodeType, EdgeType, SourceType,
    StalenessReport, DependencyQuery
)
from app.services.praxis.dependency_graph import ExecutionDependencyGraph


class TestDependencyNodeContract:
    """Tests for DependencyNode data contract."""

    def test_dependency_node_creation(self):
        """Nodes can be created with required fields."""
        node = DependencyNode(
            node_id="src-123",
            node_type=NodeType.SOURCE,
            content_hash="abc123",
            workspace_id="ws-1"
        )
        
        assert node.node_id == "src-123"
        assert node.node_type == NodeType.SOURCE
        assert node.is_stale is False
        assert node.dependencies == []
        assert node.dependents == []

    def test_source_node_has_source_fields(self):
        """SOURCE nodes can have source-specific fields."""
        node = DependencyNode(
            node_id="src-456",
            node_type=NodeType.SOURCE,
            content_hash="def456",
            source_type=SourceType.FILE,
            source_path="/path/to/file.py",
            workspace_id="ws-1"
        )
        
        assert node.source_type == SourceType.FILE
        assert node.source_path == "/path/to/file.py"

    def test_node_is_immutable(self):
        """INVARIANT: DependencyNode is frozen after creation."""
        node = DependencyNode(
            node_id="src-789",
            node_type=NodeType.EVIDENCE,
            content_hash="ghi789",
            workspace_id="ws-1"
        )
        
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            node.is_stale = True

    def test_stale_node_has_reason(self):
        """Stale nodes include staleness reason and timing."""
        node = DependencyNode(
            node_id="evd-001",
            node_type=NodeType.EVIDENCE,
            content_hash="hash123",
            workspace_id="ws-1",
            is_stale=True,
            stale_reason="Source file changed",
            stale_since=datetime.now(timezone.utc)
        )
        
        assert node.is_stale is True
        assert "Source file changed" in node.stale_reason
        assert node.stale_since is not None


class TestDependencyEdgeContract:
    """Tests for DependencyEdge data contract."""

    def test_edge_creation(self):
        """Edges can be created with required fields."""
        edge = DependencyEdge(
            edge_id="edge-1",
            source_id="src-1",
            target_id="evd-1",
            edge_type=EdgeType.DERIVES_FROM
        )
        
        assert edge.source_id == "src-1"
        assert edge.target_id == "evd-1"
        assert edge.edge_type == EdgeType.DERIVES_FROM

    def test_edge_is_immutable(self):
        """INVARIANT: DependencyEdge is frozen after creation."""
        edge = DependencyEdge(
            edge_id="edge-2",
            source_id="src-2",
            target_id="evd-2",
            edge_type=EdgeType.VALIDATES
        )
        
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            edge.source_id = "different-source"


class TestStalenessReport:
    """Tests for StalenessReport data contract."""

    def test_staleness_report_properties(self):
        """StalenessReport computes derived properties."""
        report = StalenessReport(
            trigger_node_id="src-1",
            trigger_reason="Content changed",
            old_hash="old123",
            new_hash="new456",
            invalidated_nodes=["evd-1", "evd-2"],
            invalidated_evidence=["evd-1", "evd-2"],
            affected_decisions=["dec-1"]
        )
        
        assert report.total_invalidated == 4  # 2 nodes + 2 evidence
        assert report.has_affected_decisions is True

    def test_report_no_affected_decisions(self):
        """Report correctly shows no affected decisions."""
        report = StalenessReport(
            trigger_node_id="src-1",
            trigger_reason="Content changed",
            old_hash="old123",
            new_hash="new456",
            invalidated_nodes=["evd-1"],
            invalidated_evidence=["evd-1"],
            affected_decisions=[]
        )
        
        assert report.has_affected_decisions is False


class TestExecutionDependencyGraph:
    """Tests for ExecutionDependencyGraph service."""

    def test_add_and_get_node_sync(self):
        """Nodes can be added and retrieved."""
        async def run_test():
            edg = ExecutionDependencyGraph()
            node = DependencyNode(
                node_id="test-node",
                node_type=NodeType.SOURCE,
                content_hash="hash123",
                workspace_id="ws-1"
            )
            
            await edg.add_node(node)
            retrieved = await edg.get_node("test-node")
            
            assert retrieved is not None
            assert retrieved.node_id == "test-node"
        
        asyncio.run(run_test())

    def test_add_edge_creates_relationship_sync(self):
        """Adding an edge creates the dependency relationship."""
        async def run_test():
            edg = ExecutionDependencyGraph()
            src = DependencyNode(
                node_id="src",
                node_type=NodeType.SOURCE,
                content_hash="src-hash",
                workspace_id="ws-1"
            )
            evd = DependencyNode(
                node_id="evd",
                node_type=NodeType.EVIDENCE,
                content_hash="evd-hash",
                workspace_id="ws-1"
            )
            
            await edg.add_node(src)
            await edg.add_node(evd)
            edge = await edg.add_edge("src", "evd", EdgeType.DERIVES_FROM)
            
            assert edge.source_id == "src"
            assert edge.target_id == "evd"
        
        asyncio.run(run_test())

    def test_get_dependencies_returns_upstream_sync(self):
        """get_dependencies returns upstream nodes."""
        async def run_test():
            edg = ExecutionDependencyGraph()
            src = DependencyNode(
                node_id="src",
                node_type=NodeType.SOURCE,
                content_hash="src-hash",
                workspace_id="ws-1"
            )
            evd = DependencyNode(
                node_id="evd",
                node_type=NodeType.EVIDENCE,
                content_hash="evd-hash",
                workspace_id="ws-1"
            )
            
            await edg.add_node(src)
            await edg.add_node(evd)
            await edg.add_edge("src", "evd", EdgeType.DERIVES_FROM)
            
            deps = await edg.get_dependencies("evd")
            
            assert len(deps) == 1
            assert deps[0].node_id == "src"
        
        asyncio.run(run_test())

    def test_get_dependents_returns_downstream_sync(self):
        """get_dependents returns downstream nodes."""
        async def run_test():
            edg = ExecutionDependencyGraph()
            src = DependencyNode(
                node_id="src",
                node_type=NodeType.SOURCE,
                content_hash="src-hash",
                workspace_id="ws-1"
            )
            evd = DependencyNode(
                node_id="evd",
                node_type=NodeType.EVIDENCE,
                content_hash="evd-hash",
                workspace_id="ws-1"
            )
            
            await edg.add_node(src)
            await edg.add_node(evd)
            await edg.add_edge("src", "evd", EdgeType.DERIVES_FROM)
            
            deps = await edg.get_dependents("src")
            
            assert len(deps) == 1
            assert deps[0].node_id == "evd"
        
        asyncio.run(run_test())

    def test_staleness_propagation_sync(self):
        """Staleness propagates to downstream nodes."""
        async def run_test():
            edg = ExecutionDependencyGraph()
            # Create: src -> evd -> dec
            src = DependencyNode(
                node_id="src",
                node_type=NodeType.SOURCE,
                content_hash="original-hash",
                workspace_id="ws-1"
            )
            evd = DependencyNode(
                node_id="evd",
                node_type=NodeType.EVIDENCE,
                content_hash="evd-hash",
                workspace_id="ws-1"
            )
            dec = DependencyNode(
                node_id="dec",
                node_type=NodeType.DECISION,
                content_hash="dec-hash",
                workspace_id="ws-1"
            )
            
            await edg.add_node(src)
            await edg.add_node(evd)
            await edg.add_node(dec)
            await edg.add_edge("src", "evd", EdgeType.DERIVES_FROM)
            await edg.add_edge("evd", "dec", EdgeType.SUPPORTS)
            
            # Trigger staleness
            report = await edg.propagate_staleness("src", "new-hash")
            
            assert "evd" in report.invalidated_nodes
            assert "dec" in report.invalidated_nodes
        
        asyncio.run(run_test())

    def test_stale_nodes_query_sync(self):
        """get_stale_nodes returns only stale nodes in workspace."""
        async def run_test():
            edg = ExecutionDependencyGraph()
            stale = DependencyNode(
                node_id="stale-evd",
                node_type=NodeType.EVIDENCE,
                content_hash="hash1",
                workspace_id="ws-1",
                is_stale=True,
                stale_reason="test"
            )
            fresh = DependencyNode(
                node_id="fresh-evd",
                node_type=NodeType.EVIDENCE,
                content_hash="hash2",
                workspace_id="ws-1",
                is_stale=False
            )
            
            await edg.add_node(stale)
            await edg.add_node(fresh)
            
            stale_nodes = await edg.get_stale_nodes("ws-1")
            
            assert len(stale_nodes) == 1
            assert stale_nodes[0].node_id == "stale-evd"
        
        asyncio.run(run_test())
