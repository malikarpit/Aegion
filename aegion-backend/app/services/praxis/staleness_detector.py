"""
Aegion Staleness Detector Service.

Detects when evidence becomes stale due to upstream source changes.

Doctrine: "If source Y changed after Evidence E was collected, E is stale."
Stale evidence cannot be used to support decisions.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

from ...contracts.dependency_node import (
    DependencyNode, NodeType, StalenessReport
)
from ...contracts.evidence import Evidence
from ...core.logging import logger
from .dependency_graph import ExecutionDependencyGraph


class StalenessDetector:
    """
    Detects stale evidence based on dependency changes.
    
    Implements the governance rule:
    "If source Y changed after Evidence E was collected, E is stale."
    
    Integrates with:
    - ExecutionDependencyGraph: For dependency tracking
    - ArchonGates: To block approval of stale evidence
    """
    
    def __init__(self, edg: ExecutionDependencyGraph):
        """
        Initialize the staleness detector.
        
        Args:
            edg: The Execution Dependency Graph instance
        """
        self.edg = edg
    
    async def check_evidence_freshness(
        self,
        evidence_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if evidence is fresh (not stale).
        
        Args:
            evidence_id: ID of evidence to check
            
        Returns:
            Tuple of (is_fresh, stale_reason)
            - (True, None) if evidence is fresh
            - (False, reason) if evidence is stale
        """
        node_id = f"evd-{evidence_id[:12]}"
        node = await self.edg.get_node(node_id)
        
        if not node:
            # Node not in graph - assume fresh (legacy evidence)
            return True, None
        
        if node.is_stale:
            return False, node.stale_reason
        
        # Check all upstream dependencies
        dependencies = await self.edg.get_dependencies(
            node_id,
            node_types=[NodeType.SOURCE]
        )
        
        for dep in dependencies:
            if dep.is_stale:
                return False, f"Upstream source {dep.source_path} is stale"
        
        return True, None
    
    async def invalidate_downstream(
        self,
        changed_source_id: str,
        new_content_hash: str
    ) -> List[str]:
        """
        Invalidate all downstream evidence when a source changes.
        
        Args:
            changed_source_id: ID of the changed source node
            new_content_hash: New content hash of the source
            
        Returns:
            List of invalidated evidence IDs
        """
        report = await self.edg.propagate_staleness(
            source_node_id=changed_source_id,
            new_content_hash=new_content_hash,
            reason="Source file content changed"
        )
        
        return report.invalidated_evidence
    
    async def get_invalidation_cascade(
        self,
        source_id: str
    ) -> Dict[str, List[str]]:
        """
        Get the potential invalidation cascade for a source.
        Shows what would happen if this source changed.
        
        Args:
            source_id: ID of source to analyze
            
        Returns:
            Dict mapping decision IDs to lists of affected evidence IDs
        """
        # Get all evidence that depends on this source
        evidence_nodes = await self.edg.get_dependents(
            source_id,
            node_types=[NodeType.EVIDENCE]
        )
        
        # For each evidence, find decisions that use it
        cascade: Dict[str, List[str]] = {}
        
        for evidence_node in evidence_nodes:
            # Get decisions that depend on this evidence
            decision_nodes = await self.edg.get_dependents(
                evidence_node.node_id,
                node_types=[NodeType.DECISION]
            )
            
            for decision_node in decision_nodes:
                if decision_node.node_id not in cascade:
                    cascade[decision_node.node_id] = []
                cascade[decision_node.node_id].append(evidence_node.node_id)
        
        return cascade
    
    async def get_stale_evidence_for_workspace(
        self,
        workspace_id: str
    ) -> List[DependencyNode]:
        """
        Get all stale evidence in a workspace.
        
        Args:
            workspace_id: Workspace to query
            
        Returns:
            List of stale evidence nodes
        """
        return await self.edg.get_stale_nodes(
            workspace_id,
            node_types=[NodeType.EVIDENCE]
        )
    
    async def validate_evidence_for_approval(
        self,
        evidence_ids: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that all evidence is fresh for approval.
        
        Args:
            evidence_ids: List of evidence IDs to validate
            
        Returns:
            Tuple of (all_fresh, list_of_stale_reasons)
        """
        stale_reasons = []
        
        for evidence_id in evidence_ids:
            is_fresh, reason = await self.check_evidence_freshness(evidence_id)
            if not is_fresh:
                stale_reasons.append(f"{evidence_id}: {reason}")
        
        all_fresh = len(stale_reasons) == 0
        return all_fresh, stale_reasons
    
    async def refresh_evidence(
        self,
        evidence_id: str,
        new_content_hash: str
    ) -> bool:
        """
        Mark evidence as refreshed (no longer stale).
        
        This should be called after new test results are collected.
        
        Args:
            evidence_id: ID of evidence to refresh
            new_content_hash: New content hash of the evidence
            
        Returns:
            True if successfully refreshed
        """
        node_id = f"evd-{evidence_id[:12]}"
        old_node = await self.edg.get_node(node_id)
        
        if not old_node:
            return False
        
        # Create fresh node
        fresh_node = DependencyNode(
            node_id=old_node.node_id,
            node_type=old_node.node_type,
            content_hash=new_content_hash,
            source_type=old_node.source_type,
            source_path=old_node.source_path,
            workspace_id=old_node.workspace_id,
            dependencies=old_node.dependencies,
            dependents=old_node.dependents,
            is_stale=False,
            stale_reason=None,
            stale_since=None,
            created_at=old_node.created_at,
            last_validated_at=datetime.now(timezone.utc),
            metadata=old_node.metadata
        )
        
        # Update in graph
        self.edg._nodes[node_id] = fresh_node
        
        logger.audit(
            action="EVIDENCE_REFRESHED",
            actor="praxis",
            target=evidence_id,
            justification="Evidence re-evaluated with fresh results",
            metadata={"new_content_hash": new_content_hash}
        )
        
        return True
