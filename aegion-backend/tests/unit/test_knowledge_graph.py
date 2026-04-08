"""
Aegion Phase 4 Unit Tests - Knowledge Graph.

Tests for InMemoryKnowledgeGraph adapter.
"""

import pytest
import asyncio

from app.adapters.memory_graph import InMemoryKnowledgeGraph
from app.ports.knowledge_graph import (
    GraphNodeType, GraphEdgeType, GraphNode, GraphEdge
)


class TestInMemoryKnowledgeGraph:
    """Tests for the in-memory knowledge graph adapter."""

    def test_add_and_get_node_sync(self):
        """Test adding and retrieving nodes."""
        async def run():
            graph = InMemoryKnowledgeGraph()
            
            node = await graph.add_node(
                node_type=GraphNodeType.DECISION,
                node_id="dec-001",
                properties={"title": "Test Decision"},
                labels={"important"}
            )
            
            assert node.node_id == "dec-001"
            assert node.node_type == GraphNodeType.DECISION
            assert node.properties["title"] == "Test Decision"
            assert "important" in node.labels
            
            retrieved = await graph.get_node("dec-001")
            assert retrieved is not None
            assert retrieved.node_id == "dec-001"
        
        asyncio.run(run())

    def test_update_node_sync(self):
        """Test updating node properties (non-evidence, mutable nodes)."""
        async def run():
            graph = InMemoryKnowledgeGraph()
            
            await graph.add_node(
                node_type=GraphNodeType.DECISION,
                node_id="dec-upd-001",
                properties={"status": "active"}
            )
            
            updated = await graph.update_node(
                "dec-upd-001",
                {"status": "archived", "new_field": "value"}
            )
            
            assert updated is not None
            assert updated.properties["status"] == "archived"
            assert updated.properties["new_field"] == "value"
            assert updated.updated_at is not None
        
        asyncio.run(run())

    def test_delete_node_and_edges_sync(self):
        """Test deleting a node removes its edges."""
        async def run():
            graph = InMemoryKnowledgeGraph()
            
            await graph.add_node(GraphNodeType.SOURCE, "src-001", {})
            await graph.add_node(GraphNodeType.EVIDENCE, "evd-001", {})
            await graph.add_edge("src-001", "evd-001", GraphEdgeType.DERIVES_FROM)
            
            # Delete source node
            deleted = await graph.delete_node("src-001")
            assert deleted is True
            
            # Node should be gone
            assert await graph.get_node("src-001") is None
            
            # Edge should be gone too
            edges = await graph.get_edges(source_id="src-001")
            assert len(edges) == 0
        
        asyncio.run(run())

    def test_find_nodes_by_type_sync(self):
        """Test finding nodes by type."""
        async def run():
            graph = InMemoryKnowledgeGraph()
            
            await graph.add_node(GraphNodeType.DECISION, "dec-001", {})
            await graph.add_node(GraphNodeType.DECISION, "dec-002", {})
            await graph.add_node(GraphNodeType.EVIDENCE, "evd-001", {})
            
            decisions = await graph.find_nodes(node_type=GraphNodeType.DECISION)
            assert len(decisions) == 2
            
            evidence = await graph.find_nodes(node_type=GraphNodeType.EVIDENCE)
            assert len(evidence) == 1
        
        asyncio.run(run())

    def test_add_edge_sync(self):
        """Test adding edges between nodes."""
        async def run():
            graph = InMemoryKnowledgeGraph()
            
            await graph.add_node(GraphNodeType.EVIDENCE, "evd-001", {})
            await graph.add_node(GraphNodeType.DECISION, "dec-001", {})
            
            edge = await graph.add_edge(
                source_id="evd-001",
                target_id="dec-001",
                edge_type=GraphEdgeType.SUPPORTS,
                weight=2.0
            )
            
            assert edge.source_id == "evd-001"
            assert edge.target_id == "dec-001"
            assert edge.edge_type == GraphEdgeType.SUPPORTS
            assert edge.weight == 2.0
        
        asyncio.run(run())

    def test_find_path_sync(self):
        """Test finding path between nodes."""
        async def run():
            graph = InMemoryKnowledgeGraph()
            
            # Create chain: src -> evd -> dec
            await graph.add_node(GraphNodeType.SOURCE, "src-001", {})
            await graph.add_node(GraphNodeType.EVIDENCE, "evd-001", {})
            await graph.add_node(GraphNodeType.DECISION, "dec-001", {})
            
            await graph.add_edge("src-001", "evd-001", GraphEdgeType.DERIVES_FROM)
            await graph.add_edge("evd-001", "dec-001", GraphEdgeType.SUPPORTS)
            
            path = await graph.find_path("src-001", "dec-001")
            
            assert path is not None
            assert path.path_length == 2
            assert len(path.nodes) == 3
            assert path.nodes[0].node_id == "src-001"
            assert path.nodes[-1].node_id == "dec-001"
        
        asyncio.run(run())

    def test_get_ancestors_sync(self):
        """Test getting upstream ancestors."""
        async def run():
            graph = InMemoryKnowledgeGraph()
            
            await graph.add_node(GraphNodeType.SOURCE, "src-001", {})
            await graph.add_node(GraphNodeType.SOURCE, "src-002", {})
            await graph.add_node(GraphNodeType.EVIDENCE, "evd-001", {})
            
            await graph.add_edge("src-001", "evd-001", GraphEdgeType.DERIVES_FROM)
            await graph.add_edge("src-002", "evd-001", GraphEdgeType.DERIVES_FROM)
            
            ancestors = await graph.get_ancestors("evd-001", depth=1)
            
            assert len(ancestors) == 2
            ancestor_ids = {a.node_id for a in ancestors}
            assert "src-001" in ancestor_ids
            assert "src-002" in ancestor_ids
        
        asyncio.run(run())

    def test_get_descendants_sync(self):
        """Test getting downstream descendants."""
        async def run():
            graph = InMemoryKnowledgeGraph()
            
            await graph.add_node(GraphNodeType.SOURCE, "src-001", {})
            await graph.add_node(GraphNodeType.EVIDENCE, "evd-001", {})
            await graph.add_node(GraphNodeType.EVIDENCE, "evd-002", {})
            await graph.add_node(GraphNodeType.DECISION, "dec-001", {})
            
            await graph.add_edge("src-001", "evd-001", GraphEdgeType.DERIVES_FROM)
            await graph.add_edge("src-001", "evd-002", GraphEdgeType.DERIVES_FROM)
            await graph.add_edge("evd-001", "dec-001", GraphEdgeType.SUPPORTS)
            
            descendants = await graph.get_descendants("src-001", depth=2)
            
            assert len(descendants) == 3  # evd-001, evd-002, dec-001
        
        asyncio.run(run())

    def test_get_subgraph_sync(self):
        """Test extracting subgraph around a node."""
        async def run():
            graph = InMemoryKnowledgeGraph()
            
            await graph.add_node(GraphNodeType.SOURCE, "src-001", {})
            await graph.add_node(GraphNodeType.EVIDENCE, "evd-001", {})
            await graph.add_node(GraphNodeType.DECISION, "dec-001", {})
            
            await graph.add_edge("src-001", "evd-001", GraphEdgeType.DERIVES_FROM)
            await graph.add_edge("evd-001", "dec-001", GraphEdgeType.SUPPORTS)
            
            subgraph = await graph.get_subgraph("evd-001", radius=1)
            
            assert subgraph.center_node_id == "evd-001"
            assert len(subgraph.nodes) == 3  # All nodes within radius 1
        
        asyncio.run(run())

    def test_connected_components_sync(self):
        """Test finding connected components."""
        async def run():
            graph = InMemoryKnowledgeGraph()
            
            # Component 1
            await graph.add_node(GraphNodeType.SOURCE, "src-001", {})
            await graph.add_node(GraphNodeType.EVIDENCE, "evd-001", {})
            await graph.add_edge("src-001", "evd-001", GraphEdgeType.DERIVES_FROM)
            
            # Component 2 (isolated)
            await graph.add_node(GraphNodeType.SOURCE, "src-002", {})
            await graph.add_node(GraphNodeType.EVIDENCE, "evd-002", {})
            await graph.add_edge("src-002", "evd-002", GraphEdgeType.DERIVES_FROM)
            
            components = await graph.find_connected_components()
            
            assert len(components) == 2
        
        asyncio.run(run())

    def test_node_degree_sync(self):
        """Test getting node degree."""
        async def run():
            graph = InMemoryKnowledgeGraph()
            
            await graph.add_node(GraphNodeType.EVIDENCE, "evd-001", {})
            await graph.add_node(GraphNodeType.SOURCE, "src-001", {})
            await graph.add_node(GraphNodeType.SOURCE, "src-002", {})
            await graph.add_node(GraphNodeType.DECISION, "dec-001", {})
            
            await graph.add_edge("src-001", "evd-001", GraphEdgeType.DERIVES_FROM)
            await graph.add_edge("src-002", "evd-001", GraphEdgeType.DERIVES_FROM)
            await graph.add_edge("evd-001", "dec-001", GraphEdgeType.SUPPORTS)
            
            in_degree = await graph.get_node_degree("evd-001", "in")
            out_degree = await graph.get_node_degree("evd-001", "out")
            both = await graph.get_node_degree("evd-001", "both")
            
            assert in_degree == 2
            assert out_degree == 1
            assert both == 3
        
        asyncio.run(run())

    def test_bulk_operations_sync(self):
        """Test bulk add operations."""
        async def run():
            graph = InMemoryKnowledgeGraph()
            
            nodes = [
                {"node_type": GraphNodeType.SOURCE, "node_id": "src-001", "properties": {}},
                {"node_type": GraphNodeType.SOURCE, "node_id": "src-002", "properties": {}},
            ]
            
            created_nodes = await graph.bulk_add_nodes(nodes)
            assert len(created_nodes) == 2
            
            # Add target
            await graph.add_node(GraphNodeType.EVIDENCE, "evd-001", {})
            
            edges = [
                {"source_id": "src-001", "target_id": "evd-001", "edge_type": GraphEdgeType.DERIVES_FROM},
                {"source_id": "src-002", "target_id": "evd-001", "edge_type": GraphEdgeType.DERIVES_FROM},
            ]
            
            created_edges = await graph.bulk_add_edges(edges)
            assert len(created_edges) == 2
        
        asyncio.run(run())
