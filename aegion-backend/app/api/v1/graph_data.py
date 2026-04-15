"""
Aegion API v1 - Graph Visualization Data Endpoints (W2.4).

Provides graph data for frontend visualization:
  - Nodes (entities extracted from knowledge graph)
  - Edges (relationships between entities)
  - Communities (Louvain-detected clusters)

Reference: Edge et al., 2024 — "From Local to Global: A Graph RAG Approach"
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger


router = APIRouter(prefix="/graph", tags=["graph"])


# ========== Response Models ==========

class GraphNode(BaseModel):
    id: str
    label: str
    type: str = "entity"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str = "related"
    weight: float = 1.0


class GraphCommunity(BaseModel):
    id: int
    members: List[str]
    summary: str = ""
    relevance: float = 0.0


class GraphNodesResponse(BaseModel):
    nodes: List[GraphNode]
    total: int


class GraphEdgesResponse(BaseModel):
    edges: List[GraphEdge]
    total: int


class GraphCommunitiesResponse(BaseModel):
    communities: List[GraphCommunity]
    total: int


class GraphOverview(BaseModel):
    """Full graph snapshot for visualization."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    communities: List[GraphCommunity]
    stats: Dict[str, Any] = Field(default_factory=dict)


# ========== Graph Provider Helper ==========

def _get_graph(workspace_id: str):
    """Get the knowledge graph for a workspace.
    
    Raises HTTPException(503) if graph backend is unavailable.
    """
    from ...services.graph_provider import get_shared_graph
    graph = get_shared_graph()  # takes no args — single shared instance
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="Graph backend unavailable. Check GRAPH_BACKEND configuration.",
        )
    return graph


def _get_enricher():
    """Get the GraphRAG enricher for community data."""
    try:
        from ...services.council_kernel.rag_enricher import GraphRAGEnricher
        return GraphRAGEnricher()
    except Exception:
        return None


# ========== Endpoints ==========

@router.get("/nodes", response_model=GraphNodesResponse)
async def get_graph_nodes(
    workspace_id: str = Query(...),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Get nodes from the knowledge graph.
    
    Supports filtering by entity type (e.g., 'decision', 'concept', 'file').
    """
    graph = _get_graph(workspace_id)  # raises 503 if unavailable

    try:
        # Try to get entities from the graph
        raw_nodes = []
        if hasattr(graph, 'get_entities'):
            raw_nodes = await graph.get_entities(
                workspace_id=workspace_id,
                entity_type=entity_type,
                limit=limit,
            )
        elif hasattr(graph, 'search_nodes'):
            raw_nodes = await graph.search_nodes(
                query="*", workspace_id=workspace_id, limit=limit,
            )

        nodes = [
            GraphNode(
                id=n.get("id", n.get("entity_id", str(i))),
                label=n.get("label", n.get("name", n.get("entity_id", "unknown"))),
                type=n.get("type", n.get("entity_type", "entity")),
                metadata={
                    k: v for k, v in n.items()
                    if k not in ("id", "label", "type", "entity_id", "name", "entity_type")
                },
            )
            for i, n in enumerate(raw_nodes[:limit])
        ]
        return GraphNodesResponse(nodes=nodes, total=len(nodes))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Graph nodes query failed: {exc}")
        raise HTTPException(status_code=503, detail=f"Graph query failed: {exc}")


@router.get("/edges", response_model=GraphEdgesResponse)
async def get_graph_edges(
    workspace_id: str = Query(...),
    limit: int = Query(200, ge=1, le=2000),
    user: AuthorityContext = Depends(get_current_user),
):
    """Get edges (relationships) from the knowledge graph."""
    graph = _get_graph(workspace_id)  # raises 503 if unavailable

    try:
        raw_edges = []
        if hasattr(graph, 'get_edges'):
            raw_edges = await graph.get_edges(
                workspace_id=workspace_id, limit=limit,
            )
        elif hasattr(graph, 'get_relationships'):
            raw_edges = await graph.get_relationships(
                workspace_id=workspace_id, limit=limit,
            )

        edges = [
            GraphEdge(
                source=e.get("source", e.get("from", "")),
                target=e.get("target", e.get("to", "")),
                relation=e.get("relation", e.get("type", "related")),
                weight=float(e.get("weight", 1.0)),
            )
            for e in raw_edges[:limit]
        ]
        return GraphEdgesResponse(edges=edges, total=len(edges))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Graph edges query failed: {exc}")
        raise HTTPException(status_code=503, detail=f"Graph query failed: {exc}")


@router.get("/communities", response_model=GraphCommunitiesResponse)
async def get_graph_communities(
    workspace_id: str = Query(...),
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Get Louvain-detected communities from GraphRAG.
    
    Reference: Blondel et al., 2008 — "Fast Unfolding of Communities
               in Large Networks"
    """
    enricher = _get_enricher()
    if not enricher:
        return GraphCommunitiesResponse(communities=[], total=0)

    try:
        # Check if enricher has cached communities
        if hasattr(enricher, '_community_cache') and enricher._community_cache:
            raw_communities = enricher._community_cache
        elif hasattr(enricher, 'detect_communities'):
            raw_communities = enricher.detect_communities(workspace_id)
        else:
            return GraphCommunitiesResponse(communities=[], total=0)

        communities = [
            GraphCommunity(
                id=i,
                members=list(members) if isinstance(members, (set, frozenset)) else members,
                summary=f"Community {i} ({len(members)} members)",
                relevance=0.0,
            )
            for i, members in enumerate(raw_communities)
            if members
        ]
        return GraphCommunitiesResponse(communities=communities, total=len(communities))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Graph communities query failed: {exc}")
        raise HTTPException(status_code=503, detail=f"Graph query failed: {exc}")


@router.get("/overview", response_model=GraphOverview)
async def get_graph_overview(
    workspace_id: str = Query(...),
    node_limit: int = Query(100, ge=1, le=500),
    edge_limit: int = Query(200, ge=1, le=1000),
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Get a complete graph snapshot for visualization.
    
    Combines nodes, edges, and communities in a single call
    for efficient frontend rendering.
    """
    nodes_resp = await get_graph_nodes(
        workspace_id=workspace_id, entity_type=None,
        limit=node_limit, user=user,
    )
    edges_resp = await get_graph_edges(
        workspace_id=workspace_id, limit=edge_limit, user=user,
    )
    communities_resp = await get_graph_communities(
        workspace_id=workspace_id, user=user,
    )

    return GraphOverview(
        nodes=nodes_resp.nodes,
        edges=edges_resp.edges,
        communities=communities_resp.communities,
        stats={
            "total_nodes": nodes_resp.total,
            "total_edges": edges_resp.total,
            "total_communities": communities_resp.total,
        },
    )
