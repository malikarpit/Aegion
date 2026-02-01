"""
Aegion Data Contracts - Dependency Node.

Execution Dependency Graph (EDG) contracts for tracking
dependencies between sources, evidence, and decisions.

Doctrine: "Test X is invalid because source Y changed."
All evidence has traceable dependencies to its sources.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class NodeType(str, Enum):
    """Type of node in the Execution Dependency Graph."""
    SOURCE = "source"       # File, config, or external resource
    EVIDENCE = "evidence"   # Test result, metric, snapshot
    DECISION = "decision"   # Approved decision backed by evidence
    ARTIFACT = "artifact"   # Session artifact or ADR


class EdgeType(str, Enum):
    """Type of edge/relationship in the EDG."""
    DERIVES_FROM = "derives_from"   # Target derives from source
    VALIDATES = "validates"         # Target validates source
    SUPPORTS = "supports"           # Target supports source (evidence -> decision)
    INVALIDATES = "invalidates"     # Target invalidates source
    DEPENDS_ON = "depends_on"       # Generic dependency


class SourceType(str, Enum):
    """Type of source node (for SOURCE NodeType)."""
    FILE = "file"                   # Source code file
    CONFIG = "config"               # Configuration file
    EXTERNAL = "external"           # External API/resource
    DEPENDENCY = "dependency"       # Package dependency
    ENVIRONMENT = "environment"     # Environment variable or setting


class DependencyNode(BaseModel):
    """
    A node in the Execution Dependency Graph.
    Represents a source, evidence, or decision.
    
    Doctrine: All nodes are content-addressable via their content_hash.
    This enables staleness detection when content changes.
    """
    # Identity
    node_id: str = Field(..., description="Unique node identifier")
    node_type: NodeType = Field(..., description="Type of node")
    
    # Content addressing
    content_hash: str = Field(..., description="SHA-256 hash of node content")
    
    # Source-specific (for SOURCE nodes)
    source_type: Optional[SourceType] = Field(None, description="Type of source")
    source_path: Optional[str] = Field(None, description="Path or URI to source")
    
    # Workspace context
    workspace_id: str = Field(..., description="Workspace this node belongs to")
    
    # Relationships (stored as IDs, graph service resolves)
    dependencies: List[str] = Field(
        default_factory=list,
        description="IDs of upstream nodes this depends on"
    )
    dependents: List[str] = Field(
        default_factory=list,
        description="IDs of downstream nodes that depend on this"
    )
    
    # Staleness tracking
    is_stale: bool = Field(default=False, description="Is this node stale?")
    stale_reason: Optional[str] = Field(None, description="Why is this stale?")
    stale_since: Optional[datetime] = Field(None, description="When it became stale")
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_validated_at: Optional[datetime] = Field(
        None, description="Last time content hash was verified current"
    )
    
    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional node-specific metadata"
    )
    
    model_config = ConfigDict(frozen=True)


class DependencyEdge(BaseModel):
    """
    An edge in the Execution Dependency Graph.
    Represents a relationship between two nodes.
    
    Edges are directional: source -> target
    """
    # Identity
    edge_id: str = Field(..., description="Unique edge identifier")
    
    # Relationship
    source_id: str = Field(..., description="ID of upstream/source node")
    target_id: str = Field(..., description="ID of downstream/target node")
    edge_type: EdgeType = Field(..., description="Type of relationship")
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional edge-specific metadata"
    )
    
    model_config = ConfigDict(frozen=True)


class StalenessReport(BaseModel):
    """
    Report on staleness propagation results.
    Returned when a source changes and downstream nodes are invalidated.
    """
    # Trigger
    trigger_node_id: str = Field(..., description="Node that triggered staleness")
    trigger_reason: str = Field(..., description="Why staleness was triggered")
    old_hash: str = Field(..., description="Previous content hash")
    new_hash: str = Field(..., description="New content hash")
    
    # Affected nodes
    invalidated_nodes: List[str] = Field(
        default_factory=list,
        description="IDs of nodes marked stale"
    )
    invalidated_evidence: List[str] = Field(
        default_factory=list,
        description="IDs of evidence nodes marked stale"
    )
    affected_decisions: List[str] = Field(
        default_factory=list,
        description="IDs of decisions with stale evidence"
    )
    
    # Timing
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def total_invalidated(self) -> int:
        """Total number of nodes invalidated."""
        return len(self.invalidated_nodes) + len(self.invalidated_evidence)
    
    @property
    def has_affected_decisions(self) -> bool:
        """Are any approved decisions affected?"""
        return len(self.affected_decisions) > 0


class DependencyQuery(BaseModel):
    """
    Query parameters for EDG traversal.
    """
    # Starting point
    start_node_id: str = Field(..., description="Node to start traversal from")
    
    # Direction
    direction: str = Field(
        default="downstream",
        description="'upstream' for dependencies, 'downstream' for dependents"
    )
    
    # Filters
    node_types: Optional[List[NodeType]] = Field(
        None, description="Filter by node types"
    )
    edge_types: Optional[List[EdgeType]] = Field(
        None, description="Filter by edge types"
    )
    include_stale: bool = Field(
        default=True, description="Include stale nodes in results"
    )
    
    # Limits
    max_depth: int = Field(
        default=10, description="Maximum traversal depth"
    )
    max_nodes: int = Field(
        default=100, description="Maximum nodes to return"
    )
