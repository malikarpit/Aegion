"""
Aegion Knowledge Graph Port - Graph Database Abstraction.

Phase 4: Advanced Epistemics
Provides persistent, queryable graph of decisions, evidence, and relationships.

Adapters: Neo4j, ArangoDB (or in-memory for testing)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class GraphNodeType(str, Enum):
    """Types of nodes in the knowledge graph."""
    SOURCE = "source"
    EVIDENCE = "evidence"
    DECISION = "decision"
    PROPOSAL = "proposal"
    SESSION = "session"
    USER = "user"
    WORKSPACE = "workspace"
    REVIEW = "review"


class GraphEdgeType(str, Enum):
    """Types of edges in the knowledge graph."""
    DERIVES_FROM = "derives_from"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    CREATED_BY = "created_by"
    APPROVED_BY = "approved_by"
    REJECTED_BY = "rejected_by"
    REVIEWED_BY = "reviewed_by"
    BELONGS_TO = "belongs_to"
    DEPENDS_ON = "depends_on"
    RELATED_TO = "related_to"


class GraphNode(BaseModel):
    """A node in the knowledge graph."""
    node_id: str = Field(..., description="Unique node identifier")
    node_type: GraphNodeType
    properties: Dict[str, Any] = Field(default_factory=dict)
    labels: Set[str] = Field(default_factory=set)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(frozen=True)


class GraphEdge(BaseModel):
    """An edge in the knowledge graph."""
    edge_id: str = Field(..., description="Unique edge identifier")
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    edge_type: GraphEdgeType
    properties: Dict[str, Any] = Field(default_factory=dict)
    weight: float = Field(default=1.0, description="Edge weight for traversal")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class PathResult(BaseModel):
    """Result of a path query."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    total_weight: float = 0.0
    path_length: int = 0


class SubgraphResult(BaseModel):
    """Result of a subgraph query."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    center_node_id: str
    radius: int


class KnowledgeGraphPort(ABC):
    """
    Abstract interface for graph database operations.
    
    Doctrine: "All knowledge is connected. The graph remembers."
    
    This port enables:
    - Persistent storage of decision/evidence relationships
    - Path queries for provenance tracking
    - Subgraph extraction for impact analysis
    - Pattern matching for similar decisions
    """

    # ========== Node Operations ==========

    @abstractmethod
    async def add_node(
        self,
        node_type: GraphNodeType,
        node_id: str,
        properties: Dict[str, Any],
        labels: Optional[Set[str]] = None
    ) -> GraphNode:
        """
        Add a node to the graph.
        Returns the created node with generated metadata.
        """
        pass

    @abstractmethod
    async def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID. Returns None if not found."""
        pass

    @abstractmethod
    async def update_node(
        self,
        node_id: str,
        properties: Dict[str, Any]
    ) -> Optional[GraphNode]:
        """Update node properties. Returns updated node or None."""
        pass

    @abstractmethod
    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and its edges. Returns True if deleted."""
        pass

    @abstractmethod
    async def find_nodes(
        self,
        node_type: Optional[GraphNodeType] = None,
        labels: Optional[Set[str]] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[GraphNode]:
        """Find nodes matching criteria."""
        pass

    @abstractmethod
    async def search_nodes(
        self,
        query: str,
        node_type: Optional[GraphNodeType] = None,
        limit: int = 10
    ) -> List[GraphNode]:
        """
        Full-text search for nodes.
        On generic graphs, this searches string properties.
        """
        pass

    # ========== Edge Operations ==========

    @abstractmethod
    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: GraphEdgeType,
        properties: Optional[Dict[str, Any]] = None,
        weight: float = 1.0
    ) -> GraphEdge:
        """Add an edge between nodes."""
        pass

    @abstractmethod
    async def get_edge(self, edge_id: str) -> Optional[GraphEdge]:
        """Get an edge by ID."""
        pass

    @abstractmethod
    async def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        pass

    @abstractmethod
    async def get_edges(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        edge_type: Optional[GraphEdgeType] = None
    ) -> List[GraphEdge]:
        """Get edges matching criteria."""
        pass

    # ========== Traversal Operations ==========

    @abstractmethod
    async def find_path(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 10,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> Optional[PathResult]:
        """Find shortest path between two nodes."""
        pass

    @abstractmethod
    async def get_ancestors(
        self,
        node_id: str,
        depth: int = 3,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> List[GraphNode]:
        """Get upstream/ancestor nodes."""
        pass

    @abstractmethod
    async def get_descendants(
        self,
        node_id: str,
        depth: int = 3,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> List[GraphNode]:
        """Get downstream/descendant nodes."""
        pass

    @abstractmethod
    async def get_subgraph(
        self,
        center_id: str,
        radius: int = 2,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> SubgraphResult:
        """Get subgraph around a node."""
        pass

    # ========== Analysis Operations ==========

    @abstractmethod
    async def find_connected_components(
        self,
        workspace_id: Optional[str] = None
    ) -> List[List[str]]:
        """Find connected components in the graph."""
        pass

    @abstractmethod
    async def get_node_degree(
        self,
        node_id: str,
        direction: str = "both"  # "in", "out", "both"
    ) -> int:
        """Get the degree (edge count) of a node."""
        pass

    @abstractmethod
    async def find_similar_patterns(
        self,
        node_id: str,
        max_results: int = 10
    ) -> List[GraphNode]:
        """Find nodes with similar connection patterns."""
        pass

    # ========== Bulk Operations ==========

    @abstractmethod
    async def bulk_add_nodes(
        self,
        nodes: List[Dict[str, Any]]
    ) -> List[GraphNode]:
        """Add multiple nodes in batch."""
        pass

    @abstractmethod
    async def bulk_add_edges(
        self,
        edges: List[Dict[str, Any]]
    ) -> List[GraphEdge]:
        """Add multiple edges in batch."""
        pass

    # ========== Lifecycle ==========

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to graph database."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to graph database."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if connection is healthy."""
        pass
