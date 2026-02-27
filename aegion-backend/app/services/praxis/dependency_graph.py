"""
Aegion Execution Dependency Graph (EDG) Service.

Manages the dependency graph between sources, evidence, and decisions.

Doctrine: "Test X is invalid because source Y changed."
The EDG tracks these relationships to detect staleness.
"""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone
import hashlib
import uuid

from ...contracts.dependency_node import (
    DependencyNode, DependencyEdge, NodeType, EdgeType, SourceType,
    StalenessReport, DependencyQuery
)
from ...core.logging import logger
from ...core.time import TimeAuthority


class ExecutionDependencyGraph:
    """
    Manages the Execution Dependency Graph (EDG).
    
    The EDG is a directed acyclic graph where:
    - Nodes represent sources (files), evidence, or decisions
    - Edges represent dependencies/relationships
    
    Key operations:
    - add_node: Register a new node
    - add_edge: Create a dependency relationship
    - get_dependencies: Get upstream nodes
    - get_dependents: Get downstream nodes
    - propagate_staleness: Mark downstream nodes as stale when source changes
    """
    
    def __init__(self, database_port=None):
        """
        Initialize the EDG.
        
        Args:
            database_port: Database adapter for persistence (optional for testing)
        """
        self.db = database_port
        # In-memory cache for fast traversal (production would use DB)
        self._nodes: Dict[str, DependencyNode] = {}
        self._edges: Dict[str, DependencyEdge] = {}
        # Adjacency lists for fast graph traversal
        self._dependencies: Dict[str, Set[str]] = {}  # node_id -> upstream node_ids
        self._dependents: Dict[str, Set[str]] = {}    # node_id -> downstream node_ids
    
    async def add_node(self, node: DependencyNode) -> DependencyNode:
        """
        Add a node to the graph.
        
        Args:
            node: The dependency node to add
            
        Returns:
            The added node
        """
        self._nodes[node.node_id] = node
        self._dependencies.setdefault(node.node_id, set())
        self._dependents.setdefault(node.node_id, set())
        
        logger.audit(
            action="EDG_NODE_ADDED",
            actor="praxis",
            target=node.node_id,
            justification=f"Added {node.node_type.value} node",
            metadata={
                "node_type": node.node_type.value,
                "content_hash": node.content_hash,
                "workspace_id": node.workspace_id
            }
        )
        
        return node
    
    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        metadata: Dict[str, Any] = None
    ) -> DependencyEdge:
        """
        Add an edge (dependency relationship) between nodes.
        
        Args:
            source_id: ID of upstream/source node
            target_id: ID of downstream/target node
            edge_type: Type of relationship
            metadata: Optional edge metadata
            
        Returns:
            The created edge
        """
        edge_id = f"edge-{uuid.uuid4().hex[:8]}"
        
        edge = DependencyEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            metadata=metadata or {}
        )
        
        self._edges[edge_id] = edge
        self._dependencies.setdefault(target_id, set()).add(source_id)
        self._dependents.setdefault(source_id, set()).add(target_id)
        
        logger.audit(
            action="EDG_EDGE_ADDED",
            actor="praxis",
            target=edge_id,
            justification=f"Added {edge_type.value} edge: {source_id} -> {target_id}",
            metadata={
                "source_id": source_id,
                "target_id": target_id,
                "edge_type": edge_type.value
            }
        )
        
        return edge
    
    async def get_node(self, node_id: str) -> Optional[DependencyNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)
    
    async def get_dependencies(
        self, 
        node_id: str,
        node_types: List[NodeType] = None,
        max_depth: int = 10
    ) -> List[DependencyNode]:
        """
        Get all upstream dependencies of a node.
        
        Args:
            node_id: Node to get dependencies for
            node_types: Filter by node types (optional)
            max_depth: Maximum traversal depth
            
        Returns:
            List of dependency nodes
        """
        visited = set()
        result = []
        
        def traverse(nid: str, depth: int):
            if depth > max_depth or nid in visited:
                return
            visited.add(nid)
            
            for dep_id in self._dependencies.get(nid, set()):
                dep_node = self._nodes.get(dep_id)
                if dep_node:
                    if node_types is None or dep_node.node_type in node_types:
                        result.append(dep_node)
                    traverse(dep_id, depth + 1)
        
        traverse(node_id, 0)
        return result
    
    async def get_dependents(
        self, 
        node_id: str,
        node_types: List[NodeType] = None,
        max_depth: int = 10
    ) -> List[DependencyNode]:
        """
        Get all downstream dependents of a node.
        
        Args:
            node_id: Node to get dependents for
            node_types: Filter by node types (optional)
            max_depth: Maximum traversal depth
            
        Returns:
            List of dependent nodes
        """
        visited = set()
        result = []
        
        def traverse(nid: str, depth: int):
            if depth > max_depth or nid in visited:
                return
            visited.add(nid)
            
            for dep_id in self._dependents.get(nid, set()):
                dep_node = self._nodes.get(dep_id)
                if dep_node:
                    if node_types is None or dep_node.node_type in node_types:
                        result.append(dep_node)
                    traverse(dep_id, depth + 1)
        
        traverse(node_id, 0)
        return result
    
    async def propagate_staleness(
        self,
        source_node_id: str,
        new_content_hash: str,
        reason: str = "Source content changed"
    ) -> StalenessReport:
        """
        Propagate staleness when a source changes.
        Marks all downstream evidence and decisions as stale.
        
        Args:
            source_node_id: ID of the changed source node
            new_content_hash: New content hash of the source
            reason: Why staleness is being triggered
            
        Returns:
            Report of what was invalidated
        """
        source_node = self._nodes.get(source_node_id)
        if not source_node:
            raise ValueError(f"Node {source_node_id} not found")
        
        old_hash = source_node.content_hash
        
        # Get all downstream nodes
        all_dependents = await self.get_dependents(source_node_id)
        
        invalidated_nodes = []
        invalidated_evidence = []
        affected_decisions = []
        
        now = datetime.now(timezone.utc)
        
        for node in all_dependents:
            if node.is_stale:
                continue  # Already stale
            
            # Create updated node with stale flag
            # Note: Since nodes are frozen, we create a new instance
            stale_node = DependencyNode(
                node_id=node.node_id,
                node_type=node.node_type,
                content_hash=node.content_hash,
                source_type=node.source_type,
                source_path=node.source_path,
                workspace_id=node.workspace_id,
                dependencies=node.dependencies,
                dependents=node.dependents,
                is_stale=True,
                stale_reason=f"Upstream source {source_node_id} changed",
                stale_since=now,
                created_at=node.created_at,
                last_validated_at=node.last_validated_at,
                metadata=node.metadata
            )
            
            self._nodes[node.node_id] = stale_node
            invalidated_nodes.append(node.node_id)
            
            if node.node_type == NodeType.EVIDENCE:
                invalidated_evidence.append(node.node_id)
            elif node.node_type == NodeType.DECISION:
                affected_decisions.append(node.node_id)
        
        report = StalenessReport(
            trigger_node_id=source_node_id,
            trigger_reason=reason,
            old_hash=old_hash,
            new_hash=new_content_hash,
            invalidated_nodes=invalidated_nodes,
            invalidated_evidence=invalidated_evidence,
            affected_decisions=affected_decisions
        )
        
        logger.audit(
            action="STALENESS_PROPAGATED",
            actor="praxis",
            target=source_node_id,
            justification=reason,
            metadata={
                "total_invalidated": report.total_invalidated,
                "affected_decisions": len(affected_decisions)
            }
        )
        
        return report
    
    async def get_stale_nodes(
        self, 
        workspace_id: str,
        node_types: List[NodeType] = None
    ) -> List[DependencyNode]:
        """
        Get all stale nodes in a workspace.
        
        Args:
            workspace_id: Workspace to query
            node_types: Filter by node types (optional)
            
        Returns:
            List of stale nodes
        """
        result = []
        for node in self._nodes.values():
            if node.workspace_id != workspace_id:
                continue
            if not node.is_stale:
                continue
            if node_types and node.node_type not in node_types:
                continue
            result.append(node)
        return result
    
    async def create_source_node(
        self,
        workspace_id: str,
        source_path: str,
        source_type: SourceType,
        content_hash: str,
        metadata: Dict[str, Any] = None
    ) -> DependencyNode:
        """
        Convenience method to create a source node.
        """
        node_id = f"src-{hashlib.sha256(f'{workspace_id}:{source_path}'.encode()).hexdigest()[:12]}"
        
        node = DependencyNode(
            node_id=node_id,
            node_type=NodeType.SOURCE,
            content_hash=content_hash,
            source_type=source_type,
            source_path=source_path,
            workspace_id=workspace_id,
            metadata=metadata or {}
        )
        
        return await self.add_node(node)
    
    async def create_evidence_node(
        self,
        workspace_id: str,
        evidence_id: str,
        content_hash: str,
        source_ids: List[str],
        metadata: Dict[str, Any] = None
    ) -> DependencyNode:
        """
        Convenience method to create an evidence node with dependencies.
        """
        node_id = f"evd-{evidence_id[:12]}"
        
        node = DependencyNode(
            node_id=node_id,
            node_type=NodeType.EVIDENCE,
            content_hash=content_hash,
            workspace_id=workspace_id,
            dependencies=source_ids,
            metadata=metadata or {}
        )
        
        added_node = await self.add_node(node)
        
        # Create edges from sources to this evidence
        for source_id in source_ids:
            await self.add_edge(
                source_id=source_id,
                target_id=node_id,
                edge_type=EdgeType.DERIVES_FROM
            )
        
        return added_node
