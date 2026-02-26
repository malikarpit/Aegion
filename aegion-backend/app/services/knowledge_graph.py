"""
Aegion Knowledge Graph Service — Phase 6.

PostgreSQL-backed knowledge graph with pgvector semantic search.
Wraps the existing PostgresKnowledgeGraph adapter (from Phase 3)
and adds a higher-level domain interface used by API layers.

Embedding model: all-MiniLM-L6-v2 (384-dim, ~80MB, CPU-friendly).
Lazy-loaded on first use to avoid blocking startup.

SQL functions required (migration 20260409000002_graph_functions.sql):
  - get_graph_neighbors(node_id, workspace_id, depth)
  - match_knowledge_nodes(embedding, threshold, count, workspace_id)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..db.supabase_client import get_supabase_client
from ..core.logging import logger

# Lazy singleton — loaded on first use to avoid blocking startup
_embedder = None


def _get_embedder():
    """Lazy-load sentence-transformers embedder."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("sentence-transformers embedder loaded (all-MiniLM-L6-v2, 384-dim)")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed — semantic search disabled. "
                "Install with: pip install sentence-transformers"
            )
            _embedder = None
    return _embedder


class KnowledgeGraphService:
    """
    High-level knowledge graph service backed by Supabase PostgreSQL.

    Provides:
    - Node/concept/decision insertion with auto-embedding
    - Edge relationship creation
    - Semantic similarity search (pgvector cosine)
    - Graph traversal up to N hops (recursive CTE via Supabase RPC)
    """

    def __init__(self) -> None:
        self._client = get_supabase_client()

    # ──────────────────────────────────────────────
    # Node operations
    # ──────────────────────────────────────────────

    async def add_concept(
        self,
        workspace_id: str,
        label: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add a generic concept node with embedding."""
        return await self._add_node(workspace_id, "concept", label, properties or {})

    async def add_decision(
        self,
        workspace_id: str,
        decision_id: str,
        title: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add a decision node linked to an existing decision record."""
        props = {"decision_id": decision_id, **(context or {})}
        return await self._add_node(workspace_id, "decision", title, props)

    async def add_proposal(
        self,
        workspace_id: str,
        proposal_id: str,
        title: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add a proposal node."""
        props = {"proposal_id": proposal_id, **(context or {})}
        return await self._add_node(workspace_id, "proposal", title, props)

    async def _add_node(
        self,
        workspace_id: str,
        node_type: str,
        label: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Internal: insert a node with optional embedding."""
        embedding: Optional[List[float]] = None
        embedder = _get_embedder()
        if embedder:
            embedding = embedder.encode(label).tolist()

        row: Dict[str, Any] = {
            "workspace_id": workspace_id,
            "node_type": node_type,
            "label": label,
            "properties": properties,
        }
        if embedding is not None:
            row["embedding"] = embedding

        result = self._client.table("knowledge_nodes").insert(row).execute()
        if result.data:
            return result.data[0]
        raise RuntimeError(f"Failed to insert knowledge node: {label}")

    # ──────────────────────────────────────────────
    # Edge operations
    # ──────────────────────────────────────────────

    async def link(
        self,
        workspace_id: str,
        source_id: str,
        target_id: str,
        relationship: str,
        weight: float = 1.0,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a directed edge between two nodes."""
        row = {
            "workspace_id": workspace_id,
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": relationship,
            "weight": weight,
            "properties": properties or {},
        }
        result = self._client.table("knowledge_edges").insert(row).execute()
        if result.data:
            return result.data[0]
        raise RuntimeError(f"Failed to insert edge {source_id} →{relationship}→ {target_id}")

    # ──────────────────────────────────────────────
    # Semantic search
    # ──────────────────────────────────────────────

    async def search_similar(
        self,
        workspace_id: str,
        query: str,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Find semantically similar nodes using pgvector cosine similarity.

        Returns results sorted by similarity descending.
        Falls back to label-based text search if embedder is unavailable.
        """
        embedder = _get_embedder()
        if embedder:
            embedding = embedder.encode(query).tolist()
            result = self._client.rpc(
                "match_knowledge_nodes",
                {
                    "query_embedding": embedding,
                    "match_threshold": threshold,
                    "match_count": limit,
                    "p_workspace_id": workspace_id,
                },
            ).execute()
            return result.data or []
        else:
            # Fallback: text ILIKE search on label
            logger.warning("Embedder unavailable — falling back to label text search")
            result = (
                self._client.table("knowledge_nodes")
                .select("id, label, node_type, properties")
                .eq("workspace_id", workspace_id)
                .ilike("label", f"%{query}%")
                .limit(limit)
                .execute()
            )
            return result.data or []

    # ──────────────────────────────────────────────
    # Graph traversal
    # ──────────────────────────────────────────────

    async def get_neighbors(
        self,
        workspace_id: str,
        node_id: str,
        depth: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Get connected nodes up to N hops using the recursive CTE RPC.

        Requires get_graph_neighbors() SQL function
        (migration 20260409000002_graph_functions.sql).
        """
        result = self._client.rpc(
            "get_graph_neighbors",
            {
                "p_node_id": node_id,
                "p_workspace_id": workspace_id,
                "p_depth": depth,
            },
        ).execute()
        return result.data or []

    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single node by id."""
        result = (
            self._client.table("knowledge_nodes")
            .select("*")
            .eq("id", node_id)
            .single()
            .execute()
        )
        return result.data

    async def list_nodes(
        self,
        workspace_id: str,
        node_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List nodes in a workspace, optionally filtered by type."""
        q = (
            self._client.table("knowledge_nodes")
            .select("id, label, node_type, properties, created_at")
            .eq("workspace_id", workspace_id)
        )
        if node_type:
            q = q.eq("node_type", node_type)
        result = q.limit(limit).execute()
        return result.data or []


# ──────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────

_knowledge_graph: Optional[KnowledgeGraphService] = None


def get_knowledge_graph() -> KnowledgeGraphService:
    """Get the application-wide knowledge graph service singleton."""
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = KnowledgeGraphService()
    return _knowledge_graph
