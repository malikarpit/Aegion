"""
Aegion Noesis Graph Service.

Phase 4: Advanced Epistemics
High-level knowledge graph operations over the KnowledgeGraphPort.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from ...ports.knowledge_graph import (
    KnowledgeGraphPort,
    GraphNode,
    GraphEdge,
    GraphNodeType,
    GraphEdgeType,
    PathResult,
    SubgraphResult,
)
from ...core.logging import logger


class GraphService:
    """
    High-level knowledge graph operations.
    
    Doctrine: "All knowledge is connected. The graph remembers."
    
    Provides:
    - EDG sync: Import from Phase 3 EDG
    - Provenance tracking: Who decided what and why
    - Impact analysis: What depends on what
    - Pattern discovery: Find similar decisions
    """

    def __init__(self, graph: KnowledgeGraphPort):
        self.graph = graph

    # ========== EDG Sync ==========

    async def sync_from_edg(
        self,
        edg_nodes: List[Dict[str, Any]],
        edg_edges: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Sync nodes and edges from the in-memory EDG to persistent storage.
        
        Returns counts of synced entities.
        """
        node_count = 0
        edge_count = 0
        
        # Sync nodes
        for edg_node in edg_nodes:
            node_type = self._edg_type_to_graph_type(edg_node.get("node_type"))
            
            await self.graph.add_node(
                node_type=node_type,
                node_id=edg_node["node_id"],
                properties={
                    "content_hash": edg_node.get("content_hash"),
                    "workspace_id": edg_node.get("workspace_id"),
                    "is_stale": edg_node.get("is_stale", False),
                    "source_path": edg_node.get("source_path"),
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                },
                labels={edg_node.get("node_type", "unknown")}
            )
            node_count += 1
        
        # Sync edges
        for edg_edge in edg_edges:
            edge_type = self._edg_edge_to_graph_edge(edg_edge.get("edge_type"))
            
            await self.graph.add_edge(
                source_id=edg_edge["source_id"],
                target_id=edg_edge["target_id"],
                edge_type=edge_type
            )
            edge_count += 1
        
        logger.info(
            f"EDG sync complete: {node_count} nodes, {edge_count} edges"
        )
        
        return {
            "nodes_synced": node_count,
            "edges_synced": edge_count
        }

    # ========== Provenance Tracking ==========

    async def record_decision(
        self,
        decision_id: str,
        proposal_id: str,
        approver_id: str,
        evidence_ids: List[str],
        workspace_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GraphNode:
        """
        Record a decision with its full provenance chain.
        """
        # Add decision node
        decision_node = await self.graph.add_node(
            node_type=GraphNodeType.DECISION,
            node_id=decision_id,
            properties={
                "proposal_id": proposal_id,
                "workspace_id": workspace_id,
                "decided_at": datetime.now(timezone.utc).isoformat(),
                **(metadata or {})
            },
            labels={"decision", workspace_id}
        )
        
        # Link to approver
        await self.graph.add_edge(
            source_id=decision_id,
            target_id=approver_id,
            edge_type=GraphEdgeType.APPROVED_BY
        )
        
        # Link to evidence
        for evidence_id in evidence_ids:
            await self.graph.add_edge(
                source_id=evidence_id,
                target_id=decision_id,
                edge_type=GraphEdgeType.SUPPORTS
            )
        
        # Link to proposal
        await self.graph.add_edge(
            source_id=proposal_id,
            target_id=decision_id,
            edge_type=GraphEdgeType.SUPERSEDES
        )
        
        return decision_node

    async def record_rejection(
        self,
        decision_id: str,
        proposal_id: str,
        rejector_id: str,
        workspace_id: str,
        reason: str
    ) -> GraphNode:
        """
        Record a rejection decision.
        """
        # Add decision node
        decision_node = await self.graph.add_node(
            node_type=GraphNodeType.DECISION,
            node_id=decision_id,
            properties={
                "proposal_id": proposal_id,
                "workspace_id": workspace_id,
                "decided_at": datetime.now(timezone.utc).isoformat(),
                "verdict": "rejected",
                "justification": reason
            },
            labels={"decision", "rejection", workspace_id}
        )
        
        # Link to rejector
        await self.graph.add_edge(
            source_id=decision_id,
            target_id=rejector_id,
            edge_type=GraphEdgeType.REJECTED_BY
        )
        
        # Link to proposal
        await self.graph.add_edge(
            source_id=proposal_id,
            target_id=decision_id,
            edge_type=GraphEdgeType.SUPERSEDES
        )
        
        # Update proposal status
        await self.update_proposal_status(proposal_id, "rejected")
        
        return decision_node

    async def record_proposal(
        self,
        proposal_id: str,
        creator_id: str,
        title: str,
        description: str,
        tier: str,
        status: str,
        workspace_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GraphNode:
        """Record a proposal."""
        return await self.graph.add_node(
            node_type=GraphNodeType.PROPOSAL,
            node_id=proposal_id,
            properties={
                "title": title,
                "description": description,
                "tier": tier,
                "status": status,
                "created_by": creator_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "workspace_id": workspace_id,
                **(metadata or {})
            },
            labels={"proposal", workspace_id}
        )

    async def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get any node by ID, regardless of type."""
        return await self.graph.get_node(node_id)

    async def get_proposal(self, proposal_id: str) -> Optional[GraphNode]:
        """Get a proposal by ID."""
        node = await self.graph.get_node(proposal_id)
        if node and node.node_type == GraphNodeType.PROPOSAL:
            return node
        return None

    async def update_proposal_status(self, proposal_id: str, status: str) -> bool:
        """Update proposal status."""
        node = await self.graph.update_node(
            node_id=proposal_id,
            properties={"status": status}
        )
        return node is not None

    async def update_node_properties(self, node_id: str, properties: Dict[str, Any]) -> bool:
        """Update arbitrary node properties."""
        node = await self.graph.update_node(
            node_id=node_id,
            properties=properties
        )
        return node is not None

    async def get_evidence_for_proposal(self, proposal_id: str) -> List[GraphNode]:
        """
        Fetch all evidence nodes linked to a proposal via SUPPORTS edges.

        Evidence edges point: evidence --SUPPORTS--> proposal
        So we query edges where target_id=proposal_id, edge_type=SUPPORTS.
        """
        edges = await self.graph.get_edges(
            target_id=proposal_id,
            edge_type=GraphEdgeType.SUPPORTS
        )
        evidence_nodes = []
        for edge in edges:
            node = await self.graph.get_node(edge.source_id)
            if node and node.node_type == GraphNodeType.EVIDENCE:
                evidence_nodes.append(node)
        return evidence_nodes

    async def get_edges(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        edge_type: Optional[GraphEdgeType] = None
    ) -> List[GraphEdge]:
        """Convenience passthrough to graph port get_edges."""
        return await self.graph.get_edges(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type
        )

    async def list_decisions(
        self,
        workspace_id: str,
        limit: int = 10
    ) -> List[GraphNode]:
        """List recent decisions in a workspace."""
        nodes = await self.graph.find_nodes(
            node_type=GraphNodeType.DECISION,
            properties={"workspace_id": workspace_id},
            limit=limit
        )
        # Sort by decided_at desc
        nodes.sort(
            key=lambda n: n.properties.get("decided_at", ""),
            reverse=True
        )
        return nodes

    async def list_proposals(
        self,
        workspace_id: str,
        limit: int = 50
    ) -> List[GraphNode]:
        """List proposals in a workspace/session context."""
        nodes = await self.graph.find_nodes(
            node_type=GraphNodeType.PROPOSAL,
            properties={"workspace_id": workspace_id},
            limit=limit
        )
        nodes.sort(
            key=lambda n: n.properties.get("created_at", ""),
            reverse=True
        )
        return nodes

    async def get_decision_provenance(
        self,
        decision_id: str,
        depth: int = 3
    ) -> SubgraphResult:
        """
        Get full provenance chain for a decision.
        
        Includes: approver, evidence, sources, previous decisions.
        """
        return await self.graph.get_subgraph(
            center_id=decision_id,
            radius=depth,
            edge_types=[
                GraphEdgeType.SUPPORTS,
                GraphEdgeType.APPROVED_BY,
                GraphEdgeType.DERIVES_FROM,
                GraphEdgeType.SUPERSEDES,
            ]
        )

    # ========== Impact Analysis ==========

    async def analyze_impact(
        self,
        source_id: str,
        max_depth: int = 5
    ) -> Dict[str, Any]:
        """
        Analyze impact if a source changes.
        
        Returns affected evidence, decisions, and users.
        """
        descendants = await self.graph.get_descendants(
            node_id=source_id,
            depth=max_depth,
            edge_types=[GraphEdgeType.DERIVES_FROM, GraphEdgeType.SUPPORTS]
        )
        
        affected_evidence = []
        affected_decisions = []
        affected_users = set()
        
        for node in descendants:
            if node.node_type == GraphNodeType.EVIDENCE:
                affected_evidence.append(node.node_id)
            elif node.node_type == GraphNodeType.DECISION:
                affected_decisions.append(node.node_id)
                # Find approver
                edges = await self.graph.get_edges(
                    source_id=node.node_id,
                    edge_type=GraphEdgeType.APPROVED_BY
                )
                for edge in edges:
                    affected_users.add(edge.target_id)
        
        return {
            "source_id": source_id,
            "affected_evidence_count": len(affected_evidence),
            "affected_evidence": affected_evidence,
            "affected_decision_count": len(affected_decisions),
            "affected_decisions": affected_decisions,
            "affected_user_count": len(affected_users),
            "affected_users": list(affected_users)
        }

    # ========== Pattern Discovery ==========

    async def find_similar_decisions(
        self,
        decision_id: str,
        max_results: int = 10
    ) -> List[GraphNode]:
        """
        Find decisions with similar patterns.
        
        Similarity based on:
        - Same evidence types
        - Same source dependencies
        - Similar approval patterns
        """
        return await self.graph.find_similar_patterns(
            node_id=decision_id,
            max_results=max_results
        )

    async def search_nodes(
        self,
        query: str,
        node_type: Optional[GraphNodeType] = None,
        limit: int = 10
    ) -> List[GraphNode]:
        """
        Search for nodes matching a text query.
        """
        return await self.graph.search_nodes(
            query=query,
            node_type=node_type,
            limit=limit
        )

    async def get_workspace_topology(
        self,
        workspace_id: str
    ) -> Dict[str, Any]:
        """
        Get topology summary for a workspace.
        """
        # Find all nodes in workspace
        nodes = await self.graph.find_nodes(
            properties={"workspace_id": workspace_id}
        )
        
        node_counts = {}
        for node in nodes:
            node_type = node.node_type.value
            node_counts[node_type] = node_counts.get(node_type, 0) + 1
        
        # Find connected components
        components = await self.graph.find_connected_components(workspace_id)
        
        return {
            "workspace_id": workspace_id,
            "total_nodes": len(nodes),
            "node_counts": node_counts,
            "component_count": len(components),
            "largest_component_size": max(len(c) for c in components) if components else 0
        }

    async def get_adr_graph(self, workspace_id: str) -> Dict[str, List[Any]]:
        """
        Get the full ADR graph for visualization.
        Returns all Decision nodes and their connecting edges.
        """
        # Nodes
        nodes = await self.graph.find_nodes(
            node_type=GraphNodeType.DECISION,
            properties={"workspace_id": workspace_id},
            limit=100
        )
        
        # Edges
        # Ideally we'd have a bulk edge fetch, but for now we iterate
        node_ids = {n.node_id for n in nodes}
        edges = []
        
        for node in nodes:
            out_edges = await self.graph.get_edges(source_id=node.node_id)
            for edge in out_edges:
                # Include edges that connect two decisions
                if edge.target_id in node_ids and edge.edge_type in [
                    GraphEdgeType.SUPERSEDES, 
                    GraphEdgeType.DEPENDS_ON, 
                    GraphEdgeType.DERIVES_FROM,
                    GraphEdgeType.RELATED_TO
                ]:
                    edges.append(edge)
        
        return {
            "nodes": [
                {
                    "node_id": n.node_id,
                    "node_type": n.node_type.value,
                    "label": n.properties.get("title", "Untitled"),
                    "properties": n.properties
                }
                for n in nodes
            ],
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "edge_type": e.edge_type.value
                }
                for e in edges
            ]
        }

    # ========== Helper Methods ==========

    def _edg_type_to_graph_type(self, edg_type: str) -> GraphNodeType:
        """Convert EDG node type to graph node type."""
        mapping = {
            "source": GraphNodeType.SOURCE,
            "evidence": GraphNodeType.EVIDENCE,
            "decision": GraphNodeType.DECISION,
        }
        return mapping.get(edg_type, GraphNodeType.SOURCE)

    def _edg_edge_to_graph_edge(self, edg_edge: str) -> GraphEdgeType:
        """Convert EDG edge type to graph edge type."""
        mapping = {
            "derives_from": GraphEdgeType.DERIVES_FROM,
            "validates": GraphEdgeType.SUPPORTS,
            "supports": GraphEdgeType.SUPPORTS,
            "invalidates": GraphEdgeType.CONTRADICTS,
        }
        return mapping.get(edg_edge, GraphEdgeType.DEPENDS_ON)
