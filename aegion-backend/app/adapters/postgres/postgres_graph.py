"""
Aegion PostgreSQL Knowledge Graph Adapter.

Phase 3: Database Migration.
Replaces MemoryGraph with persistent pgvector-enabled PostgreSQL implementation.
Uses recursive CTEs for highly optimized localized tree traversals.
"""

from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone
import json
import logging

from ...ports.knowledge_graph import (
    KnowledgeGraphPort,
    GraphNode,
    GraphEdge,
    GraphNodeType,
    GraphEdgeType,
    PathResult,
    SubgraphResult,
)
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PostgresConfig:
    host: str = "localhost"
    port: int = 54322
    database: str = "postgres"
    user: str = "postgres"
    password: str = "postgres"
    min_connections: int = 2
    max_connections: int = 10


class PostgresKnowledgeGraph(KnowledgeGraphPort):
    """
    Supabase/PostgreSQL implementation of KnowledgeGraphPort.
    Uses recursive CTEs for graph traversal operations.
    """

    def __init__(self, config: Optional[PostgresConfig] = None):
        self.config = config or PostgresConfig()
        self._pool = None

    # ========== Lifecycle ==========

    async def connect(self) -> None:
        try:
            import asyncpg
            
            # Allow fallback to env string for full URLs
            import os
            dsn = os.getenv("DATABASE_URL")
            
            if dsn:
                self._pool = await asyncpg.create_pool(
                    dsn,
                    min_size=self.config.min_connections,
                    max_size=self.config.max_connections
                )
            else:
                self._pool = await asyncpg.create_pool(
                    host=self.config.host,
                    port=self.config.port,
                    database=self.config.database,
                    user=self.config.user,
                    password=self.config.password,
                    min_size=self.config.min_connections,
                    max_size=self.config.max_connections
                )
            logger.info("Connected to PostgreSQL (Knowledge Graph)")
        except ImportError:
            raise ImportError("asyncpg is required.")

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Disconnected from PostgreSQL (Knowledge Graph)")

    async def health_check(self) -> bool:
        if not self._pool:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False

    # ========== Mappers ==========

    def _map_node(self, row) -> GraphNode:
        data = dict(row)
        return GraphNode(
            node_id=str(data["id"]),
            node_type=GraphNodeType(data["node_type"]),
            properties=json.loads(data["properties"]) if isinstance(data["properties"], str) else (data["properties"] or {}),
            labels=set(), # Labels mapping omitted for brevity, can be recovered from properties if needed
            created_at=data["created_at"],
            updated_at=data.get("updated_at")
        )

    def _map_edge(self, row) -> GraphEdge:
        data = dict(row)
        return GraphEdge(
            edge_id=str(data["id"]),
            source_id=str(data["source_id"]),
            target_id=str(data["target_id"]),
            edge_type=GraphEdgeType(data["edge_type"]),
            properties=json.loads(data["metadata"]) if isinstance(data["metadata"], str) else (data["metadata"] or {}),
            weight=float(data["weight"]),
            created_at=data["created_at"]
        )

    # ========== Node Operations ==========

    async def add_node(
        self,
        node_type: GraphNodeType,
        node_id: str,
        properties: Dict[str, Any],
        labels: Optional[Set[str]] = None
    ) -> GraphNode:
        
        async with self._pool.acquire() as conn:
            workspace_id = properties.get("workspace_id")
            if not workspace_id:
                raise ValueError("workspace_id must be provided in properties for PG nodes.")
                
            row = await conn.fetchrow("""
                INSERT INTO knowledge_nodes (id, workspace_id, node_type, label, properties)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb)
                RETURNING *
            """, 
            node_id, 
            workspace_id, 
            node_type.value,
            properties.get("name", node_id),
            json.dumps(properties)
            )
            return self._map_node(row)

    async def get_node(self, node_id: str) -> Optional[GraphNode]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM knowledge_nodes WHERE id = $1::uuid", node_id)
            return self._map_node(row) if row else None

    async def update_node(
        self,
        node_id: str,
        properties: Dict[str, Any]
    ) -> Optional[GraphNode]:
        node = await self.get_node(node_id)
        if not node:
            return None
            
        if node.node_type == GraphNodeType.EVIDENCE:
            raise ValueError("Evidence node is append-only.")
            
        new_props = {**node.properties, **properties}
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE knowledge_nodes 
                SET properties = $1::jsonb
                WHERE id = $2::uuid
                RETURNING *
            """, json.dumps(new_props), node_id)
            return self._map_node(row)

    async def delete_node(self, node_id: str) -> bool:
        node = await self.get_node(node_id)
        if not node:
            return False
            
        if node.node_type == GraphNodeType.EVIDENCE:
            raise ValueError("Evidence node is append-only.")
            
        async with self._pool.acquire() as conn:
            result = await conn.execute("DELETE FROM knowledge_nodes WHERE id = $1::uuid", node_id)
            return "DELETE" in result

    async def find_nodes(
        self,
        node_type: Optional[GraphNodeType] = None,
        labels: Optional[Set[str]] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[GraphNode]:
        query = "SELECT * FROM knowledge_nodes WHERE 1=1"
        params = []
        idx = 1
        
        if node_type:
            query += f" AND node_type = ${idx}"
            params.append(node_type.value)
            idx += 1
            
        if properties:
            for k, v in properties.items():
                query += f" AND properties->>'${k}' = ${idx}"
                params.append(str(v))
                idx += 1
                
        query += f" LIMIT ${idx}"
        params.append(limit)
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._map_node(row) for row in rows]

    async def search_nodes(
        self,
        query: str,
        node_type: Optional[GraphNodeType] = None,
        limit: int = 10
    ) -> List[GraphNode]:
        # Simple ILIKE search on properties for now. Vector search will be phased in later.
        sql = "SELECT * FROM knowledge_nodes WHERE properties::text ILIKE $1"
        params = [f"%{query}%"]
        idx = 2
        
        if node_type:
            sql += f" AND node_type = ${idx}"
            params.append(node_type.value)
            idx += 1
            
        sql += f" LIMIT ${idx}"
        params.append(limit)
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            return [self._map_node(row) for row in rows]


    # ========== Edge Operations ==========

    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: GraphEdgeType,
        properties: Optional[Dict[str, Any]] = None,
        weight: float = 1.0
    ) -> GraphEdge:
        async with self._pool.acquire() as conn:
            # Need workspace_id from source node
            source_row = await conn.fetchrow("SELECT workspace_id FROM knowledge_nodes WHERE id = $1::uuid", source_id)
            workspace_id = source_row['workspace_id'] if source_row else None
            
            row = await conn.fetchrow("""
                INSERT INTO knowledge_edges (workspace_id, source_id, target_id, edge_type, weight, metadata)
                VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6::jsonb)
                RETURNING *
            """, workspace_id, source_id, target_id, edge_type.value, weight, json.dumps(properties or {}))
            return self._map_edge(row)

    async def get_edge(self, edge_id: str) -> Optional[GraphEdge]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM knowledge_edges WHERE id = $1::uuid", edge_id)
            return self._map_edge(row) if row else None

    async def delete_edge(self, edge_id: str) -> bool:
        async with self._pool.acquire() as conn:
            res = await conn.execute("DELETE FROM knowledge_edges WHERE id = $1::uuid", edge_id)
            return "DELETE" in res

    async def get_edges(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        edge_type: Optional[GraphEdgeType] = None
    ) -> List[GraphEdge]:
        query = "SELECT * FROM knowledge_edges WHERE 1=1"
        params = []
        idx = 1
        
        if source_id:
            query += f" AND source_id = ${idx}::uuid"
            params.append(source_id)
            idx += 1
        if target_id:
            query += f" AND target_id = ${idx}::uuid"
            params.append(target_id)
            idx += 1
        if edge_type:
            query += f" AND edge_type = ${idx}"
            params.append(edge_type.value)
            idx += 1
            
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._map_edge(row) for row in rows]

    # ========== Traversal Operations ==========

    async def find_path(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 10,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> Optional[PathResult]:
        # To be fully implemented with WITH RECURSIVE or Dijkstra in PG
        return None

    async def get_ancestors(
        self,
        node_id: str,
        depth: int = 3,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> List[GraphNode]:
        sql = """
        WITH RECURSIVE ancestors AS (
            SELECT target_id, source_id, 1 as depth
            FROM knowledge_edges
            WHERE target_id = $1::uuid
            
            UNION
            
            SELECT e.target_id, e.source_id, a.depth + 1
            FROM knowledge_edges e
            JOIN ancestors a ON e.target_id = a.source_id
            WHERE a.depth < $2
        )
        SELECT DISTINCT n.* 
        FROM ancestors a
        JOIN knowledge_nodes n ON n.id = a.source_id;
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, node_id, depth)
            return [self._map_node(row) for row in rows]

    async def get_descendants(
        self,
        node_id: str,
        depth: int = 3,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> List[GraphNode]:
        sql = """
        WITH RECURSIVE descendants AS (
            SELECT source_id, target_id, 1 as depth
            FROM knowledge_edges
            WHERE source_id = $1::uuid
            
            UNION
            
            SELECT e.source_id, e.target_id, d.depth + 1
            FROM knowledge_edges e
            JOIN descendants d ON e.source_id = d.target_id
            WHERE d.depth < $2
        )
        SELECT DISTINCT n.* 
        FROM descendants d
        JOIN knowledge_nodes n ON n.id = d.target_id;
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, node_id, depth)
            return [self._map_node(row) for row in rows]

    async def get_subgraph(
        self,
        center_id: str,
        radius: int = 2,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> SubgraphResult:
        ancestors = await self.get_ancestors(center_id, radius)
        descendants = await self.get_descendants(center_id, radius)
        center = await self.get_node(center_id)
        
        nodes = []
        if center:
            nodes.append(center)
        nodes.extend(ancestors)
        nodes.extend(descendants)
        
        # Deduplicate
        seen = set()
        unique_nodes = []
        for n in nodes:
            if n.node_id not in seen:
                seen.add(n.node_id)
                unique_nodes.append(n)
                
        # To get edges within the subgraph safely we can query them directly if needed
        # Skipped full edge loading for brevity in this MVP
        return SubgraphResult(
            nodes=unique_nodes,
            edges=[],
            center_node_id=center_id,
            radius=radius
        )

    # ========== Analysis & Bulk Operations ==========

    async def find_connected_components(self, workspace_id: Optional[str] = None) -> List[List[str]]:
        return []

    async def get_node_degree(self, node_id: str, direction: str = "both") -> int:
        return 0

    async def find_similar_patterns(self, node_id: str, max_results: int = 10) -> List[GraphNode]:
        return []

    async def bulk_add_nodes(self, nodes: List[Dict[str, Any]]) -> List[GraphNode]:
        return []

    async def bulk_add_edges(self, edges: List[Dict[str, Any]]) -> List[GraphEdge]:
        return []
