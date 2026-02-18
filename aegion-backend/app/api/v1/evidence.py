"""
Aegion Evidence & EDG API Endpoints.

Phase 3: Evidence snapshots, freshness checking, and EDG queries.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ...contracts.evidence import Evidence, EvidenceClassification
from ...contracts.snapshot import SnapshotType, EvidenceSnapshot
from ...contracts.dependency_node import NodeType, DependencyNode
from ...services.praxis import (
    ExecutionDependencyGraph,
    StalenessDetector,
    SnapshotManager,
)


router = APIRouter(prefix="/evidence", tags=["evidence"])


# ========== Request/Response Models ==========

class FreshnessResponse(BaseModel):
    """Response for evidence freshness check."""
    evidence_id: str
    is_fresh: bool
    stale_reason: Optional[str] = None
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class SnapshotCaptureRequest(BaseModel):
    """Request to capture snapshots for evidence."""
    file_paths: List[str] = Field(default_factory=list)
    capture_output: bool = True
    capture_environment: bool = True
    output_data: Optional[str] = None  # Base64 encoded
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SnapshotListResponse(BaseModel):
    """Response listing snapshots for evidence."""
    evidence_id: str
    input_count: int
    output_count: int
    has_environment: bool
    snapshots: Dict[str, List[Dict[str, Any]]]


class RegisterNodeRequest(BaseModel):
    """Request to register a dependency node."""
    node_type: NodeType
    content_hash: str
    workspace_id: str
    source_path: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DependencyListResponse(BaseModel):
    """Response listing dependencies/dependents."""
    node_id: str
    direction: str  # "upstream" or "downstream"
    nodes: List[Dict[str, Any]]


class StaleNodesResponse(BaseModel):
    """Response listing stale nodes in workspace."""
    workspace_id: str
    stale_count: int
    stale_nodes: List[Dict[str, Any]]


# ========== In-memory instances for demo ==========
# In production, these would be injected via dependency injection

_edg_instances: Dict[str, ExecutionDependencyGraph] = {}
_snapshot_managers: Dict[str, SnapshotManager] = {}


def get_edg(workspace_id: str = "default") -> ExecutionDependencyGraph:
    """Get or create EDG for workspace."""
    if workspace_id not in _edg_instances:
        _edg_instances[workspace_id] = ExecutionDependencyGraph()
    return _edg_instances[workspace_id]


def get_snapshot_manager() -> SnapshotManager:
    """Get snapshot manager."""
    if "default" not in _snapshot_managers:
        _snapshot_managers["default"] = SnapshotManager()
    return _snapshot_managers["default"]


# ========== Evidence Submission ==========

class SubmitEvidenceRequest(BaseModel):
    """Request to submit evidence for a proposal."""
    proposal_id: str
    classification: EvidenceClassification = EvidenceClassification.UNCLASSIFIED
    evidence_type: str = "manual"
    source: str = "human"
    content_hash: str = ""
    summary: str = ""
    analysis_notes: str = ""
    metrics: Dict[str, Any] = Field(default_factory=dict)


@router.post("/submit")
async def submit_evidence(request: SubmitEvidenceRequest):
    """
    Submit evidence for a proposal.

    Creates an evidence node in the knowledge graph and links it
    to the proposal via a SUPPORTS edge. This makes the evidence
    available for governance gate validation during approval.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    from .analytics import _graph_service
    from ...ports.knowledge_graph import GraphNodeType, GraphEdgeType
    from ...core.time import TimeAuthority
    import uuid

    evidence_id = f"ev-{uuid.uuid4().hex[:12]}"
    now = TimeAuthority.now()

    # Store as graph node
    await _graph_service.graph.add_node(
        node_type=GraphNodeType.EVIDENCE,
        node_id=evidence_id,
        properties={
            "evidence_id": evidence_id,
            "proposal_id": request.proposal_id,
            "evidence_type": request.evidence_type,
            "classification": request.classification.value,
            "source": request.source,
            "source_id": "api",
            "collected_at": now,
            "created_at": now,
            "content_hash": request.content_hash,
            "summary": request.summary,
            "analysis_notes": request.analysis_notes,
            "metrics": request.metrics,
        },
        labels={"evidence", request.proposal_id}
    )

    # Link evidence → proposal via SUPPORTS edge
    await _graph_service.graph.add_edge(
        source_id=evidence_id,
        target_id=request.proposal_id,
        edge_type=GraphEdgeType.SUPPORTS,
        properties={"created_at": now}
    )

    return {
        "evidence_id": evidence_id,
        "proposal_id": request.proposal_id,
        "classification": request.classification.value,
    }


# ========== Evidence Freshness Endpoints ==========

@router.get("/{evidence_id}/freshness", response_model=FreshnessResponse)
async def check_evidence_freshness(evidence_id: str, workspace_id: str = "default"):
    """
    Check if evidence is fresh (not stale).
    
    Returns freshness status and reason if stale.
    """
    edg = get_edg(workspace_id)
    detector = StalenessDetector(edg)
    
    is_fresh, stale_reason = await detector.check_evidence_freshness(evidence_id)
    
    return FreshnessResponse(
        evidence_id=evidence_id,
        is_fresh=is_fresh,
        stale_reason=stale_reason
    )


# ========== Snapshot Endpoints ==========

@router.get("/{evidence_id}/snapshots", response_model=SnapshotListResponse)
async def list_evidence_snapshots(evidence_id: str):
    """
    List all snapshots for a piece of evidence.
    """
    manager = get_snapshot_manager()
    snapshots = await manager.get_snapshots_for_evidence(evidence_id)
    
    return SnapshotListResponse(
        evidence_id=evidence_id,
        input_count=len(snapshots.get(SnapshotType.INPUT, [])),
        output_count=len(snapshots.get(SnapshotType.OUTPUT, [])),
        has_environment=len(snapshots.get(SnapshotType.ENVIRONMENT, [])) > 0,
        snapshots={
            "input": [s.model_dump() for s in snapshots.get(SnapshotType.INPUT, [])],
            "output": [s.model_dump() for s in snapshots.get(SnapshotType.OUTPUT, [])],
            "environment": [s.model_dump() for s in snapshots.get(SnapshotType.ENVIRONMENT, [])]
        }
    )


@router.post("/{evidence_id}/snapshots")
async def capture_evidence_snapshots(
    evidence_id: str,
    request: SnapshotCaptureRequest
):
    """
    Capture snapshots for evidence.
    
    Captures input files, output data, and/or environment.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    manager = get_snapshot_manager()
    captured = []
    
    # Capture input files
    if request.file_paths:
        snapshot = await manager.capture_input_snapshot(
            evidence_id=evidence_id,
            file_paths=request.file_paths,
            metadata=request.metadata
        )
        captured.append({"type": "input", "snapshot_id": snapshot.snapshot_id})
    
    # Capture output
    if request.capture_output and request.output_data:
        import base64
        output_bytes = base64.b64decode(request.output_data)
        snapshot = await manager.capture_output_snapshot(
            evidence_id=evidence_id,
            output_data=output_bytes,
            metadata=request.metadata
        )
        captured.append({"type": "output", "snapshot_id": snapshot.snapshot_id})
    
    # Capture environment
    if request.capture_environment:
        snapshot = await manager.capture_environment_snapshot(
            evidence_id=evidence_id,
            metadata=request.metadata
        )
        captured.append({"type": "environment", "snapshot_id": snapshot.snapshot_id})
    
    return {
        "evidence_id": evidence_id,
        "captured_count": len(captured),
        "snapshots": captured
    }


# ========== EDG Router ==========

edg_router = APIRouter(prefix="/edg", tags=["edg"])


@edg_router.post("/nodes")
async def register_dependency_node(request: RegisterNodeRequest):
    """
    Register a new dependency node in the EDG.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    edg = get_edg(request.workspace_id)
    
    node = DependencyNode(
        node_id=f"node-{datetime.now(timezone.utc).timestamp()}",
        node_type=request.node_type,
        content_hash=request.content_hash,
        workspace_id=request.workspace_id,
        source_path=request.source_path,
        dependencies=request.dependencies,
        metadata=request.metadata
    )
    
    added = await edg.add_node(node)
    
    return {
        "node_id": added.node_id,
        "node_type": added.node_type.value,
        "content_hash": added.content_hash
    }


@edg_router.get("/nodes/{node_id}/dependencies", response_model=DependencyListResponse)
async def get_node_dependencies(node_id: str, workspace_id: str = "default"):
    """
    Get upstream dependencies of a node.
    """
    edg = get_edg(workspace_id)
    deps = await edg.get_dependencies(node_id)
    
    return DependencyListResponse(
        node_id=node_id,
        direction="upstream",
        nodes=[{
            "node_id": n.node_id,
            "node_type": n.node_type.value,
            "is_stale": n.is_stale
        } for n in deps]
    )


@edg_router.get("/nodes/{node_id}/dependents", response_model=DependencyListResponse)
async def get_node_dependents(node_id: str, workspace_id: str = "default"):
    """
    Get downstream dependents of a node.
    """
    edg = get_edg(workspace_id)
    deps = await edg.get_dependents(node_id)
    
    return DependencyListResponse(
        node_id=node_id,
        direction="downstream",
        nodes=[{
            "node_id": n.node_id,
            "node_type": n.node_type.value,
            "is_stale": n.is_stale
        } for n in deps]
    )


@edg_router.get("/stale", response_model=StaleNodesResponse)
async def list_stale_nodes(workspace_id: str = "default"):
    """
    List all stale nodes in a workspace.
    """
    edg = get_edg(workspace_id)
    stale = await edg.get_stale_nodes(workspace_id)
    
    return StaleNodesResponse(
        workspace_id=workspace_id,
        stale_count=len(stale),
        stale_nodes=[{
            "node_id": n.node_id,
            "node_type": n.node_type.value,
            "stale_reason": n.stale_reason,
            "stale_since": n.stale_since.isoformat() if n.stale_since else None
        } for n in stale]
    )
