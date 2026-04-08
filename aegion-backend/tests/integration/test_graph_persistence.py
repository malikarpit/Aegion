"""
Tests for graph snapshot persistence.

Verifies:
- Round-trip: export → clear → import preserves all state
- All node types, edge types, properties, labels are preserved
- Immutability doctrine still enforced after import
- Empty graph exports cleanly
- Timestamps survive round-trip
"""

import pytest
import asyncio
from datetime import datetime, timezone

from app.adapters.memory_graph import InMemoryKnowledgeGraph
from app.ports.knowledge_graph import GraphNodeType, GraphEdgeType


@pytest.fixture
def graph():
    return InMemoryKnowledgeGraph()


@pytest.mark.asyncio
async def test_empty_graph_export(graph):
    """Empty graph exports a valid snapshot with no nodes/edges."""
    snapshot = await graph.export_snapshot()

    assert snapshot["version"] == 1
    assert snapshot["nodes"] == {}
    assert snapshot["edges"] == {}
    assert "exported_at" in snapshot


@pytest.mark.asyncio
async def test_round_trip_single_node(graph):
    """A single node survives export → import."""
    await graph.add_node(
        GraphNodeType.PROPOSAL,
        "prop-1",
        {"title": "Add auth module", "impact": "cross_module"},
        labels={"governance", "security"},
    )

    snapshot = await graph.export_snapshot()

    # Import into a fresh graph
    graph2 = InMemoryKnowledgeGraph()
    await graph2.import_snapshot(snapshot)

    node = await graph2.get_node("prop-1")
    assert node is not None
    assert node.node_type == GraphNodeType.PROPOSAL
    assert node.properties["title"] == "Add auth module"
    assert node.properties["impact"] == "cross_module"
    assert "governance" in node.labels
    assert "security" in node.labels


@pytest.mark.asyncio
async def test_round_trip_nodes_and_edges(graph):
    """Nodes + edges + adjacency indices survive round-trip."""
    await graph.add_node(GraphNodeType.PROPOSAL, "p-1", {"title": "Proposal A"})
    await graph.add_node(GraphNodeType.EVIDENCE, "e-1", {"content": "Test result"})
    edge = await graph.add_edge("e-1", "p-1", GraphEdgeType.SUPPORTS)

    snapshot = await graph.export_snapshot()

    graph2 = InMemoryKnowledgeGraph()
    await graph2.import_snapshot(snapshot)

    # Nodes exist
    assert await graph2.get_node("p-1") is not None
    assert await graph2.get_node("e-1") is not None

    # Edge exists
    edges = await graph2.get_edges(source_id="e-1", target_id="p-1")
    assert len(edges) == 1
    assert edges[0].edge_type == GraphEdgeType.SUPPORTS

    # Adjacency indices work (traversal)
    ancestors = await graph2.get_ancestors("p-1", depth=1)
    assert any(n.node_id == "e-1" for n in ancestors)


@pytest.mark.asyncio
async def test_immutability_after_import(graph):
    """Evidence nodes remain immutable after import."""
    await graph.add_node(GraphNodeType.EVIDENCE, "ev-1", {"content": "proof"})

    snapshot = await graph.export_snapshot()

    graph2 = InMemoryKnowledgeGraph()
    await graph2.import_snapshot(snapshot)

    # Cannot update evidence
    with pytest.raises(ValueError, match="append-only"):
        await graph2.update_node("ev-1", {"content": "tampered"})

    # Cannot delete evidence
    with pytest.raises(ValueError, match="append-only"):
        await graph2.delete_node("ev-1")


@pytest.mark.asyncio
async def test_timestamps_preserved(graph):
    """Original timestamps survive round-trip, not replaced with import time."""
    node = await graph.add_node(
        GraphNodeType.SESSION, "s-1", {"mode": "governed"}
    )
    original_created = node.created_at

    snapshot = await graph.export_snapshot()

    # Small delay to ensure import time would differ
    graph2 = InMemoryKnowledgeGraph()
    await graph2.import_snapshot(snapshot)

    imported_node = await graph2.get_node("s-1")
    assert imported_node.created_at == original_created


@pytest.mark.asyncio
async def test_all_node_types_round_trip(graph):
    """All GraphNodeType values survive serialization."""
    for i, nt in enumerate(GraphNodeType):
        await graph.add_node(nt, f"node-{i}", {"type_test": nt.value})

    snapshot = await graph.export_snapshot()

    graph2 = InMemoryKnowledgeGraph()
    await graph2.import_snapshot(snapshot)

    for i, nt in enumerate(GraphNodeType):
        node = await graph2.get_node(f"node-{i}")
        assert node is not None, f"Missing node for type {nt}"
        assert node.node_type == nt


@pytest.mark.asyncio
async def test_all_edge_types_round_trip(graph):
    """All GraphEdgeType values survive serialization."""
    # Create two nodes to connect
    await graph.add_node(GraphNodeType.PROPOSAL, "src", {})
    await graph.add_node(GraphNodeType.PROPOSAL, "tgt", {})

    for i, et in enumerate(GraphEdgeType):
        # Use unique source nodes to avoid edge ID collisions
        src_id = f"src-{i}"
        await graph.add_node(GraphNodeType.PROPOSAL, src_id, {})
        await graph.add_edge(src_id, "tgt", et)

    snapshot = await graph.export_snapshot()

    graph2 = InMemoryKnowledgeGraph()
    await graph2.import_snapshot(snapshot)

    for i, et in enumerate(GraphEdgeType):
        src_id = f"src-{i}"
        edges = await graph2.get_edges(source_id=src_id, edge_type=et)
        assert len(edges) >= 1, f"Missing edge for type {et}"


@pytest.mark.asyncio
async def test_duplicate_id_still_blocked_after_import(graph):
    """Node ID uniqueness is still enforced after import."""
    await graph.add_node(GraphNodeType.PROPOSAL, "p-dup", {"v": 1})

    snapshot = await graph.export_snapshot()

    graph2 = InMemoryKnowledgeGraph()
    await graph2.import_snapshot(snapshot)

    with pytest.raises(ValueError, match="already exists"):
        await graph2.add_node(GraphNodeType.PROPOSAL, "p-dup", {"v": 2})


@pytest.mark.asyncio
async def test_import_replaces_existing_state(graph):
    """Import clears existing state before loading snapshot."""
    await graph.add_node(GraphNodeType.PROPOSAL, "old-1", {"title": "old"})

    # Import a snapshot that has different data
    snapshot = {
        "version": 1,
        "nodes": {
            "new-1": {
                "node_id": "new-1",
                "node_type": "proposal",
                "properties": {"title": "new"},
                "labels": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None,
            }
        },
        "edges": {},
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }

    await graph.import_snapshot(snapshot)

    # Old node is gone
    assert await graph.get_node("old-1") is None
    # New node is present
    assert await graph.get_node("new-1") is not None


@pytest.mark.asyncio
async def test_invalid_version_rejected(graph):
    """Unsupported snapshot versions are rejected."""
    with pytest.raises(ValueError, match="Unsupported snapshot version"):
        await graph.import_snapshot({"version": 99, "nodes": {}, "edges": {}})
