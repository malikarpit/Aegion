"""
Aegion In-Memory Knowledge Graph Adapter.

Testing/development implementation of KnowledgeGraphPort.
Uses in-memory data structures for fast testing.
"""

from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone
import hashlib

from ..ports.knowledge_graph import (
    KnowledgeGraphPort,
    GraphNode,
    GraphEdge,
    GraphNodeType,
    GraphEdgeType,
    PathResult,
    SubgraphResult,
)


class InMemoryKnowledgeGraph(KnowledgeGraphPort):
    """
    In-memory implementation of KnowledgeGraphPort.
    
    Suitable for testing and development.
    For production, use Neo4jAdapter or ArangoDBAdapter.
    """

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: Dict[str, GraphEdge] = {}
        self._outgoing: Dict[str, Set[str]] = {}  # node_id -> edge_ids
        self._incoming: Dict[str, Set[str]] = {}  # node_id -> edge_ids
        self._connected = False

    # ========== Node Operations ==========

    async def add_node(
        self,
        node_type: GraphNodeType,
        node_id: str,
        properties: Dict[str, Any],
        labels: Optional[Set[str]] = None
    ) -> GraphNode:
        """Add a node to the graph. Raises ValueError if node_id already exists."""
        if node_id in self._nodes:
            raise ValueError(
                f"Node '{node_id}' already exists (type={self._nodes[node_id].node_type.value}). "
                "Duplicate node IDs are not allowed."
            )
        node = GraphNode(
            node_id=node_id,
            node_type=node_type,
            properties=properties,
            labels=labels or set(),
            created_at=datetime.now(timezone.utc)
        )
        self._nodes[node_id] = node
        self._outgoing.setdefault(node_id, set())
        self._incoming.setdefault(node_id, set())
        return node

    async def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    async def update_node(
        self,
        node_id: str,
        properties: Dict[str, Any]
    ) -> Optional[GraphNode]:
        """Update node properties."""
        if node_id not in self._nodes:
            return None
        
        old_node = self._nodes[node_id]
        
        # Append-only enforcement: evidence nodes are immutable
        if old_node.node_type == GraphNodeType.EVIDENCE:
            raise ValueError(
                f"Evidence node '{node_id}' is append-only and cannot be modified. "
                "Doctrine: Evidence is immutable once recorded."
            )
        new_props = {**old_node.properties, **properties}
        
        # Create new immutable node
        new_node = GraphNode(
            node_id=old_node.node_id,
            node_type=old_node.node_type,
            properties=new_props,
            labels=old_node.labels,
            created_at=old_node.created_at,
            updated_at=datetime.now(timezone.utc)
        )
        self._nodes[node_id] = new_node
        return new_node

    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and its edges."""
        if node_id not in self._nodes:
            return False
        
        # Append-only enforcement: evidence nodes cannot be deleted
        if self._nodes[node_id].node_type == GraphNodeType.EVIDENCE:
            raise ValueError(
                f"Evidence node '{node_id}' is append-only and cannot be deleted. "
                "Doctrine: Evidence is immutable once recorded."
            )
        
        # Delete outgoing edges
        for edge_id in list(self._outgoing.get(node_id, set())):
            await self.delete_edge(edge_id)
        
        # Delete incoming edges
        for edge_id in list(self._incoming.get(node_id, set())):
            await self.delete_edge(edge_id)
        
        del self._nodes[node_id]
        self._outgoing.pop(node_id, None)
        self._incoming.pop(node_id, None)
        return True

    async def find_nodes(
        self,
        node_type: Optional[GraphNodeType] = None,
        labels: Optional[Set[str]] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[GraphNode]:
        """Find nodes matching criteria."""
        results = []
        for node in self._nodes.values():
            if node_type and node.node_type != node_type:
                continue
            if labels and not labels.issubset(node.labels):
                continue
            if properties:
                match = all(
                    node.properties.get(k) == v
                    for k, v in properties.items()
                )
                if not match:
                    continue
            results.append(node)
            if len(results) >= limit:
                break
        return results

    async def search_nodes(
        self,
        query: str,
        node_type: Optional[GraphNodeType] = None,
        limit: int = 10
    ) -> List[GraphNode]:
        """Simple substring search for in-memory graph."""
        results = []
        query = query.lower()
        
        for node in self._nodes.values():
            if node_type and node.node_type != node_type:
                continue
            
            # Search in string properties
            match = False
            for val in node.properties.values():
                if isinstance(val, str) and query in val.lower():
                    match = True
                    break
            
            if match:
                results.append(node)
                if len(results) >= limit:
                    break
        
        return results

    # ========== Edge Operations ==========

    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: GraphEdgeType,
        properties: Optional[Dict[str, Any]] = None,
        weight: float = 1.0
    ) -> GraphEdge:
        """Add an edge between nodes."""
        edge_id = f"edge-{hashlib.md5(f'{source_id}-{target_id}-{edge_type}'.encode()).hexdigest()[:8]}"
        
        edge = GraphEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            properties=properties or {},
            weight=weight,
            created_at=datetime.now(timezone.utc)
        )
        
        self._edges[edge_id] = edge
        self._outgoing.setdefault(source_id, set()).add(edge_id)
        self._incoming.setdefault(target_id, set()).add(edge_id)
        return edge

    async def get_edge(self, edge_id: str) -> Optional[GraphEdge]:
        """Get an edge by ID."""
        return self._edges.get(edge_id)

    async def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        if edge_id not in self._edges:
            return False
        
        edge = self._edges[edge_id]
        self._outgoing.get(edge.source_id, set()).discard(edge_id)
        self._incoming.get(edge.target_id, set()).discard(edge_id)
        del self._edges[edge_id]
        return True

    async def get_edges(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        edge_type: Optional[GraphEdgeType] = None
    ) -> List[GraphEdge]:
        """Get edges matching criteria."""
        results = []
        for edge in self._edges.values():
            if source_id and edge.source_id != source_id:
                continue
            if target_id and edge.target_id != target_id:
                continue
            if edge_type and edge.edge_type != edge_type:
                continue
            results.append(edge)
        return results

    # ========== Traversal Operations ==========

    async def find_path(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 10,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> Optional[PathResult]:
        """Find shortest path using BFS."""
        if from_id not in self._nodes or to_id not in self._nodes:
            return None
        
        from collections import deque
        
        visited = {from_id}
        queue = deque([(from_id, [], [])])  # (node_id, path_nodes, path_edges)
        
        while queue:
            current, path_nodes, path_edges = queue.popleft()
            
            if current == to_id:
                nodes = [self._nodes[nid] for nid in [from_id] + path_nodes]
                return PathResult(
                    nodes=nodes,
                    edges=path_edges,
                    total_weight=sum(e.weight for e in path_edges),
                    path_length=len(path_edges)
                )
            
            if len(path_edges) >= max_depth:
                continue
            
            for edge_id in self._outgoing.get(current, set()):
                edge = self._edges[edge_id]
                if edge_types and edge.edge_type not in edge_types:
                    continue
                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    queue.append((
                        edge.target_id,
                        path_nodes + [edge.target_id],
                        path_edges + [edge]
                    ))
        
        return None

    async def get_ancestors(
        self,
        node_id: str,
        depth: int = 3,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> List[GraphNode]:
        """Get upstream/ancestor nodes."""
        results = []
        visited = {node_id}
        current_level = {node_id}
        
        for _ in range(depth):
            next_level = set()
            for nid in current_level:
                for edge_id in self._incoming.get(nid, set()):
                    edge = self._edges[edge_id]
                    if edge_types and edge.edge_type not in edge_types:
                        continue
                    if edge.source_id not in visited:
                        visited.add(edge.source_id)
                        next_level.add(edge.source_id)
                        if edge.source_id in self._nodes:
                            results.append(self._nodes[edge.source_id])
            current_level = next_level
        
        return results

    async def get_descendants(
        self,
        node_id: str,
        depth: int = 3,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> List[GraphNode]:
        """Get downstream/descendant nodes."""
        results = []
        visited = {node_id}
        current_level = {node_id}
        
        for _ in range(depth):
            next_level = set()
            for nid in current_level:
                for edge_id in self._outgoing.get(nid, set()):
                    edge = self._edges[edge_id]
                    if edge_types and edge.edge_type not in edge_types:
                        continue
                    if edge.target_id not in visited:
                        visited.add(edge.target_id)
                        next_level.add(edge.target_id)
                        if edge.target_id in self._nodes:
                            results.append(self._nodes[edge.target_id])
            current_level = next_level
        
        return results

    async def get_subgraph(
        self,
        center_id: str,
        radius: int = 2,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> SubgraphResult:
        """Get subgraph around a node."""
        ancestors = await self.get_ancestors(center_id, radius, edge_types)
        descendants = await self.get_descendants(center_id, radius, edge_types)
        
        node_ids = {center_id} | {n.node_id for n in ancestors} | {n.node_id for n in descendants}
        nodes = [self._nodes[nid] for nid in node_ids if nid in self._nodes]
        
        edges = []
        for edge in self._edges.values():
            if edge.source_id in node_ids and edge.target_id in node_ids:
                if not edge_types or edge.edge_type in edge_types:
                    edges.append(edge)
        
        return SubgraphResult(
            nodes=nodes,
            edges=edges,
            center_node_id=center_id,
            radius=radius
        )

    # ========== Analysis Operations ==========

    async def find_connected_components(
        self,
        workspace_id: Optional[str] = None
    ) -> List[List[str]]:
        """Find connected components using DFS."""
        visited = set()
        components = []
        
        node_ids = list(self._nodes.keys())
        if workspace_id:
            node_ids = [
                nid for nid in node_ids
                if self._nodes[nid].properties.get("workspace_id") == workspace_id
            ]
        
        def dfs(node_id: str, component: List[str]):
            visited.add(node_id)
            component.append(node_id)
            
            for edge_id in self._outgoing.get(node_id, set()):
                edge = self._edges[edge_id]
                if edge.target_id not in visited:
                    dfs(edge.target_id, component)
            
            for edge_id in self._incoming.get(node_id, set()):
                edge = self._edges[edge_id]
                if edge.source_id not in visited:
                    dfs(edge.source_id, component)
        
        for node_id in node_ids:
            if node_id not in visited:
                component = []
                dfs(node_id, component)
                components.append(component)
        
        return components

    async def get_node_degree(
        self,
        node_id: str,
        direction: str = "both"
    ) -> int:
        """Get the degree of a node."""
        if direction == "in":
            return len(self._incoming.get(node_id, set()))
        elif direction == "out":
            return len(self._outgoing.get(node_id, set()))
        else:
            return (
                len(self._incoming.get(node_id, set())) +
                len(self._outgoing.get(node_id, set()))
            )

    async def find_similar_patterns(
        self,
        node_id: str,
        max_results: int = 10
    ) -> List[GraphNode]:
        """Find nodes with similar connection patterns."""
        if node_id not in self._nodes:
            return []
        
        target_in = len(self._incoming.get(node_id, set()))
        target_out = len(self._outgoing.get(node_id, set()))
        target_type = self._nodes[node_id].node_type
        
        # Simple similarity: same type, similar degree
        similarities = []
        for nid, node in self._nodes.items():
            if nid == node_id:
                continue
            if node.node_type != target_type:
                continue
            
            in_deg = len(self._incoming.get(nid, set()))
            out_deg = len(self._outgoing.get(nid, set()))
            
            # Euclidean distance in degree space
            diff = ((in_deg - target_in) ** 2 + (out_deg - target_out) ** 2) ** 0.5
            similarities.append((diff, node))
        
        similarities.sort(key=lambda x: x[0])
        return [node for _, node in similarities[:max_results]]

    # ========== Bulk Operations ==========

    async def bulk_add_nodes(
        self,
        nodes: List[Dict[str, Any]]
    ) -> List[GraphNode]:
        """Add multiple nodes in batch."""
        results = []
        for node_data in nodes:
            node = await self.add_node(
                node_type=node_data["node_type"],
                node_id=node_data["node_id"],
                properties=node_data.get("properties", {}),
                labels=node_data.get("labels")
            )
            results.append(node)
        return results

    async def bulk_add_edges(
        self,
        edges: List[Dict[str, Any]]
    ) -> List[GraphEdge]:
        """Add multiple edges in batch."""
        results = []
        for edge_data in edges:
            edge = await self.add_edge(
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                edge_type=edge_data["edge_type"],
                properties=edge_data.get("properties"),
                weight=edge_data.get("weight", 1.0)
            )
            results.append(edge)
        return results

    # ========== Snapshot Operations ==========

    async def export_snapshot(self) -> Dict[str, Any]:
        """
        Export full graph state as a serializable dict.

        Used by graph_provider to persist graph to disk.
        All node types, edge types, properties, and labels are preserved.
        """
        nodes_data = {}
        for nid, n in self._nodes.items():
            nodes_data[nid] = {
                "node_id": n.node_id,
                "node_type": n.node_type.value,
                "properties": n.properties,
                "labels": list(n.labels),
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "updated_at": n.updated_at.isoformat() if n.updated_at else None,
            }

        edges_data = {}
        for eid, e in self._edges.items():
            edges_data[eid] = {
                "edge_id": e.edge_id,
                "source_id": e.source_id,
                "target_id": e.target_id,
                "edge_type": e.edge_type.value,
                "properties": e.properties,
                "weight": e.weight,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }

        return {
            "nodes": nodes_data,
            "edges": edges_data,
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    async def import_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """
        Import graph state from a snapshot dict, replacing current state.

        Rebuilds all nodes, edges, and adjacency indices.
        Preserves original timestamps from the snapshot.
        """
        version = snapshot.get("version", 1)
        if version != 1:
            raise ValueError(f"Unsupported snapshot version: {version}")

        # Clear current state
        self._nodes.clear()
        self._edges.clear()
        self._outgoing.clear()
        self._incoming.clear()

        # Rebuild nodes
        for nid, ndata in snapshot.get("nodes", {}).items():
            created_at = (
                datetime.fromisoformat(ndata["created_at"])
                if ndata.get("created_at")
                else datetime.now(timezone.utc)
            )
            updated_at = (
                datetime.fromisoformat(ndata["updated_at"])
                if ndata.get("updated_at")
                else None
            )
            node = GraphNode(
                node_id=ndata["node_id"],
                node_type=GraphNodeType(ndata["node_type"]),
                properties=ndata.get("properties", {}),
                labels=set(ndata.get("labels", [])),
                created_at=created_at,
                updated_at=updated_at,
            )
            self._nodes[nid] = node
            self._outgoing.setdefault(nid, set())
            self._incoming.setdefault(nid, set())

        # Rebuild edges + adjacency indices
        for eid, edata in snapshot.get("edges", {}).items():
            created_at = (
                datetime.fromisoformat(edata["created_at"])
                if edata.get("created_at")
                else datetime.now(timezone.utc)
            )
            edge = GraphEdge(
                edge_id=edata["edge_id"],
                source_id=edata["source_id"],
                target_id=edata["target_id"],
                edge_type=GraphEdgeType(edata["edge_type"]),
                properties=edata.get("properties", {}),
                weight=edata.get("weight", 1.0),
                created_at=created_at,
            )
            self._edges[eid] = edge
            self._outgoing.setdefault(edge.source_id, set()).add(eid)
            self._incoming.setdefault(edge.target_id, set()).add(eid)

    # ========== Lifecycle ==========

    async def connect(self) -> None:
        """No-op for in-memory implementation."""
        self._connected = True

    async def disconnect(self) -> None:
        """No-op for in-memory implementation."""
        self._connected = False

    async def health_check(self) -> bool:
        """Always healthy for in-memory."""
        return True
