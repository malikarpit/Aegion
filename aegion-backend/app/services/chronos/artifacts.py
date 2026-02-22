"""
Aegion Chronos Artifacts - Immutable Session Memory.

Implements the immutable session artifact system.
Sessions are distilled into content-addressed artifacts.

Doctrine: "Memory is governed, not generated."
Session artifacts are immutable once created.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
import hashlib
import json

from ...contracts.decision_intent import DecisionIntent
from ...contracts.evidence import Evidence
from ...core.time import TimeAuthority
from ...core.logging import logger


class SessionArtifact(BaseModel):
    """
    Immutable session artifact.
    Created when a session is distilled.
    """
    # Identity
    artifact_id: str = Field(..., description="Content hash of artifact")
    session_id: str = Field(..., description="Original session ID")
    
    # Timing
    session_start: str
    session_end: str
    distilled_at: str = Field(default_factory=TimeAuthority.now)
    
    # Metadata
    owner_id: str
    workspace_id: str
    
    # Content summary
    decision_count: int = 0
    evidence_count: int = 0
    
    # Reasoning captured
    reasoning_phases: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Decisions made (IDs only - full content stored separately)
    decision_ids: List[str] = Field(default_factory=list)
    
    # Evidence collected (hashes only - full content stored separately)
    evidence_hashes: List[str] = Field(default_factory=list)
    
    # Metrics
    context_tokens_consumed: int = 0
    ai_invocations: int = 0
    
    # ADR extraction (for behavior-derived ADRs)
    extracted_adrs: List[str] = Field(default_factory=list)
    
    model_config = ConfigDict(frozen=True)


class ChronosArtifacts:
    """
    Manages immutable session artifacts.
    
    Responsibilities:
    1. Distill sessions into artifacts
    2. Store artifacts content-addressed
    3. Query artifacts by various criteria
    """
    
    def __init__(self, storage_port=None):
        self.storage = storage_port
    
    async def distill_session(
        self,
        session_id: str,
        owner_id: str,
        workspace_id: str,
        session_start: str,
        session_end: str,
        decisions: List[DecisionIntent],
        evidence_list: List[Evidence],
        reasoning_phases: List[Dict[str, Any]],
        metrics: Dict[str, int] = None
    ) -> SessionArtifact:
        """
        Distill a closed session into an immutable artifact.
        
        From Memory Persistence Doctrine:
        - Distillation is irreversible
        - Artifacts are content-addressed
        """
        metrics = metrics or {}
        
        # Collect decision IDs and evidence hashes
        decision_ids = [d.intent_id for d in decisions]
        evidence_hashes = [e.content_hash for e in evidence_list]
        
        # Create artifact content for hashing
        artifact_content = {
            "session_id": session_id,
            "session_start": session_start,
            "session_end": session_end,
            "owner_id": owner_id,
            "decision_ids": sorted(decision_ids),
            "evidence_hashes": sorted(evidence_hashes),
        }
        
        # Compute content hash
        content_bytes = json.dumps(artifact_content, sort_keys=True).encode()
        artifact_id = hashlib.sha256(content_bytes).hexdigest()
        
        # Create immutable artifact
        artifact = SessionArtifact(
            artifact_id=artifact_id,
            session_id=session_id,
            session_start=session_start,
            session_end=session_end,
            owner_id=owner_id,
            workspace_id=workspace_id,
            decision_count=len(decisions),
            evidence_count=len(evidence_list),
            reasoning_phases=reasoning_phases,
            decision_ids=decision_ids,
            evidence_hashes=evidence_hashes,
            context_tokens_consumed=metrics.get("context_tokens", 0),
            ai_invocations=metrics.get("ai_invocations", 0),
        )
        
        # Store artifact
        if self.storage:
            await self.storage.store(
                key=f"artifacts/sessions/{artifact_id}",
                content=artifact.model_dump_json().encode(),
                content_type="application/json"
            )
        
        logger.audit(
            action="SESSION_DISTILLED",
            actor="chronos",
            target=session_id,
            justification=f"Session distilled to artifact {artifact_id}",
            metadata={
                "artifact_id": artifact_id,
                "decision_count": len(decisions),
                "evidence_count": len(evidence_list)
            }
        )
        
        return artifact
    
    async def get_artifact(self, artifact_id: str) -> Optional[SessionArtifact]:
        """Retrieve artifact by ID."""
        if not self.storage:
            return None
        
        content = await self.storage.retrieve(f"artifacts/sessions/{artifact_id}")
        if content:
            return SessionArtifact.model_validate_json(content)
        return None
    
    async def get_artifacts_for_user(
        self, owner_id: str, limit: int = 50
    ) -> List[SessionArtifact]:
        """Get all artifacts for a user."""
        if not self.storage:
            return []
        # Use storage listing if available
        if hasattr(self.storage, 'list_by_owner'):
            raw_list = await self.storage.list_by_owner(owner_id, limit)
            artifacts = []
            for raw in raw_list:
                try:
                    artifacts.append(SessionArtifact.model_validate(raw))
                except Exception:
                    continue
            return artifacts
        return []

    async def get_artifacts_for_workspace(
        self, workspace_id: str, limit: int = 50
    ) -> List[SessionArtifact]:
        """Get all artifacts for a workspace."""
        if not self.storage:
            return []
        if hasattr(self.storage, 'list_by_workspace'):
            raw_list = await self.storage.list_by_workspace(workspace_id, limit)
            artifacts = []
            for raw in raw_list:
                try:
                    artifacts.append(SessionArtifact.model_validate(raw))
                except Exception:
                    continue
            return artifacts
        return []


class DecisionLineage(BaseModel):
    """
    Tracks decision lineage for supersession.
    
    From Supersession Doctrine:
    - Decisions are never edited, only superseded
    - Full lineage is preserved
    """
    decision_id: str
    supersedes_id: Optional[str] = None  # ID of decision this supersedes
    superseded_by_id: Optional[str] = None  # ID of decision that superseded this
    
    # Chain position
    chain_root_id: str  # Original decision in the chain
    chain_position: int = 0  # 0 = original, 1 = first supersession, etc.
    
    # Timing
    created_at: str
    superseded_at: Optional[str] = None


class ChronosSupersession:
    """
    Manages decision supersession.
    
    Doctrine: "Never edit. Only supersede."
    """
    
    async def supersede_decision(
        self,
        original_id: str,
        new_decision: DecisionIntent,
        actor_id: str,
        reason: str
    ) -> tuple[DecisionIntent, DecisionLineage]:
        """
        Supersede an existing decision with a new one.
        The original decision is marked as superseded but NOT modified.
        """
        # Get original lineage
        # Get original lineage to determine root and position
        from ...services.graph_provider import get_shared_graph_service
        _graph_service = get_shared_graph_service()
        
        # We need to find the root of the chain the original decision belongs to
        # Simplest way: traverse up 'SUPERSEDES' edges (reversed) or just check metadata if we trusted it.
        # Stronger way: Graph traversal.
        
        # For this implementation, we'll fetch the lineage of the original decision
        # to find its root and current position.
        existing_lineage = await self.get_lineage_chain(original_id)
        
        if existing_lineage:
            # The last item in the list is the original_id (if get_lineage_chain returns ordered list)
            # Actually get_lineage_chain returns the whole chain.
            # We find the entry for original_id
            current_entry = next((item for item in existing_lineage if item.decision_id == original_id), None)
            if current_entry:
                original_chain_root = current_entry.chain_root_id
                original_position = current_entry.chain_position
            else:
                # Should not happen if original_id exists
                original_chain_root = original_id
                original_position = 0
        else:
            # Fallback if no lineage found (e.g. genesis decision)
            original_chain_root = original_id
            original_position = 0
        
        # Create lineage for new decision
        lineage = DecisionLineage(
            decision_id=new_decision.intent_id,
            supersedes_id=original_id,
            chain_root_id=original_chain_root,
            chain_position=original_position + 1,
            created_at=TimeAuthority.now()
        )
        
        # Mark in new decision's metadata
        new_decision.metadata["supersedes"] = original_id
        new_decision.metadata["chain_position"] = lineage.chain_position
        
        # ── Persist to graph ──
        from ...ports.knowledge_graph import GraphNodeType, GraphEdgeType
        
        # 1. Add new decision node
        await _graph_service.graph.add_node(
            node_type=GraphNodeType.DECISION,
            node_id=new_decision.intent_id,
            properties={
                "title": new_decision.title,
                "tier": new_decision.calculated_tier.value if hasattr(new_decision.calculated_tier, 'value') else str(new_decision.calculated_tier),
                "status": "approved",
                "decided_at": TimeAuthority.now(),
                "supersedes": original_id,
                "chain_position": lineage.chain_position,
                "proposed_by": actor_id,
            }
        )
        
        # 2. Add SUPERSEDES edge (new → original)
        await _graph_service.graph.add_edge(
            source_id=new_decision.intent_id,
            target_id=original_id,
            edge_type=GraphEdgeType.SUPERSEDES,
            properties={
                "reason": reason,
                "actor": actor_id,
                "created_at": TimeAuthority.now(),
            }
        )
        
        # 3. Mark original as superseded (immutable — status only)
        await _graph_service.graph.update_node(
            node_id=original_id,
            properties={
                "status": "superseded",
                "superseded_by": new_decision.intent_id,
                "superseded_at": TimeAuthority.now(),
            }
        )
        
        logger.audit(
            action="DECISION_SUPERSEDED",
            actor=actor_id,
            target=original_id,
            justification=reason,
            metadata={
                "new_decision_id": new_decision.intent_id,
                "chain_position": lineage.chain_position
            }
        )
        
        return new_decision, lineage
    
    async def get_lineage_chain(
        self, decision_id: str
    ) -> List[DecisionLineage]:
        """Get full lineage chain for a decision."""
        # Use existing graph service (dependency injection ideal, import for now)
        from ...services.graph_provider import get_shared_graph_service
        _graph_service = get_shared_graph_service()
        from ...ports.knowledge_graph import GraphEdgeType
        
        # Traverse upstream (superseded_by) and downstream (supersedes)
        # For MVP, we just trace backwards from current decision to root
        # and forwards if possible, or just start from given ID
        
        # 1. Get ancestors (what this supersedes)
        ancestors = await _graph_service.graph.get_ancestors(
            node_id=decision_id,
            depth=10,
            edge_types=[GraphEdgeType.SUPERSEDES]
        )
        
        # 2. Get descendants (what supersedes this)
        descendants = await _graph_service.graph.get_descendants(
            node_id=decision_id,
            depth=10,
            edge_types=[GraphEdgeType.SUPERSEDES]
        )
        
        # Combine all nodes in chain
        chain_nodes = {n.node_id: n for n in ancestors + descendants}
        # Add current node if not present
        if decision_id not in chain_nodes:
            current_node = await _graph_service.graph.get_node(decision_id)
            if current_node:
                chain_nodes[decision_id] = current_node
        
        # Build lineage objects
        # This requires reconstructing the chain order.
        # GraphEdgeType.SUPERSEDES means A -> B (A supersedes B)
        # So "root" is the one being superseded at the bottom of the chain
        
        # Find edges to determining ordering
        all_ids = list(chain_nodes.keys())
        edges = []
        for nid in all_ids:
            node_edges = await _graph_service.graph.get_edges(source_id=nid, edge_type=GraphEdgeType.SUPERSEDES)
            edges.extend(node_edges)
            
        # Map: superseded -> superseder
        superseded_by_map = {e.target_id: e.source_id for e in edges if e.target_id in chain_nodes and e.source_id in chain_nodes}
        # Map: superseder -> superseded
        supersedes_map = {e.source_id: e.target_id for e in edges if e.target_id in chain_nodes and e.source_id in chain_nodes}
        
        # Find root (node not superseding anything in this set?) 
        # Actually root is the original decision, so it is the one NOT superseding anything?
        # A supersedes B. B supersedes C. C is root.
        
        # Find the node that doesn't supersede anything in this set
        root_id = None
        for nid in all_ids:
            if nid not in supersedes_map:
                root_id = nid
                break
                
        if not root_id:
             # Cycle or empty? Fallback to decision_id
             root_id = decision_id
             
        # Traverse up from root
        lineage = []
        current_id = root_id
        position = 0
        
        while current_id:
            node = chain_nodes.get(current_id)
            if not node:
                break
                
            l = DecisionLineage(
                decision_id=current_id,
                supersedes_id=supersedes_map.get(current_id),
                superseded_by_id=superseded_by_map.get(current_id),
                chain_root_id=root_id,
                chain_position=position,
                created_at=node.properties.get("decided_at", node.created_at.isoformat()),
                superseded_at=None 
            )
            
            # If this node is superseded by another, we can try to find when that happened.
            # The 'superseded_at' is effectively the 'created_at' of the *next* node in the chain.
            superseding_id = superseded_by_map.get(current_id)
            if superseding_id:
                superseding_node = chain_nodes.get(superseding_id)
                if superseding_node:
                    l.superseded_at = superseding_node.properties.get("decided_at", superseding_node.created_at.isoformat())
            
            lineage.append(l)
            
            # Move to next (the one that supersedes current)
            current_id = superseded_by_map.get(current_id)
            position += 1
            
        return lineage
