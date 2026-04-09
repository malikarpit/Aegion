"""
Aegion Reasoning Query API.

Structured reasoning query endpoints.
Provides typed endpoints for querying decisions, evidence, and reasoning phases
instead of relying on generic memory search.
"""

from fastapi import APIRouter, Depends
from typing import Optional, List
from datetime import datetime, timezone

from ...services.noesis.graph_service import GraphService
from ...ports.knowledge_graph import GraphNodeType, GraphEdgeType
from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger


router = APIRouter(prefix="/reasoning", tags=["reasoning"])


@router.get("/decisions")
async def query_decisions(
    workspace_id: str,
    tier: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 20,
):
    """
    Query decisions with structured filters (tier, status, time range).
    
    Replaces generic queryMemory('decisions') with typed filtering.
    """
    from .analytics import _graph_service

    # Fetch decisions from graph
    all_decisions = await _graph_service.list_decisions(
        workspace_id=workspace_id,
        limit=limit * 3  # Over-fetch for filtering
    )

    results = []
    for d in all_decisions:
        props = d.properties

        # Filter by tier
        if tier and props.get("tier") != tier:
            continue

        # Filter by status
        if status and props.get("status") != status:
            continue

        # Filter by time (since)
        if since:
            decided_at = props.get("decided_at", "")
            if decided_at and decided_at < since:
                continue

        results.append({
            "decision_id": d.node_id,
            "title": props.get("title", ""),
            "tier": props.get("tier", "T0"),
            "status": props.get("status", "approved"),
            "decided_at": props.get("decided_at", ""),
            "description": props.get("description", ""),
            "workspace_id": props.get("workspace_id", workspace_id),
        })

        if len(results) >= limit:
            break

    return {
        "workspace_id": workspace_id,
        "count": len(results),
        "filters": {"tier": tier, "status": status, "since": since},
        "decisions": results,
    }


@router.get("/evidence/{proposal_id}")
async def query_evidence(
    proposal_id: str,
    classification: Optional[str] = None,
):
    """
    Query evidence for a proposal, optionally filtered by classification.
    
    Provides structured access to evidence rather than generic search.
    """
    from .analytics import _graph_service

    evidence_nodes = await _graph_service.get_evidence_for_proposal(proposal_id)

    results = []
    for node in evidence_nodes:
        props = node.properties

        # Filter by classification if specified
        if classification and props.get("classification") != classification:
            continue

        results.append({
            "evidence_id": props.get("evidence_id", node.node_id),
            "proposal_id": proposal_id,
            "classification": props.get("classification", "unclassified"),
            "evidence_type": props.get("evidence_type", "manual"),
            "source": props.get("source", "unknown"),
            "summary": props.get("summary", ""),
            "collected_at": props.get("collected_at", ""),
            "content_hash": props.get("content_hash", ""),
        })

    return {
        "proposal_id": proposal_id,
        "count": len(results),
        "classification_filter": classification,
        "evidence": results,
    }


@router.get("/provenance/{decision_id}")
async def query_provenance(
    decision_id: str,
    depth: int = 3,
):
    """
    Get full provenance chain for a decision.
    Shows the complete audit trail: who proposed, who approved, what evidence supported.
    """
    from .analytics import _graph_service

    provenance = await _graph_service.get_decision_provenance(
        decision_id=decision_id,
        depth=depth
    )

    return {
        "decision_id": decision_id,
        "depth": depth,
        "nodes": [
            {
                "node_id": n.node_id,
                "node_type": n.node_type.value,
                "properties": n.properties,
            }
            for n in provenance.nodes
        ],
        "edges": [
            {
                "source_id": e.source_id,
                "target_id": e.target_id,
                "edge_type": e.edge_type.value,
            }
            for e in provenance.edges
        ],
    }
