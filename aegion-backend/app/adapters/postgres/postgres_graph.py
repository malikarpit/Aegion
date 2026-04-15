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
                query += f" AND properties->>'{k}' = ${idx}"
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
        """BFS path-finding using recursive CTE."""
        edge_filter = ""
        params: list = [from_id, to_id, max_depth]
        if edge_types:
            placeholders = ", ".join(f"${i+4}" for i in range(len(edge_types)))
            edge_filter = f"AND e.edge_type IN ({placeholders})"
            params.extend(et.value for et in edge_types)

        sql = f"""
        WITH RECURSIVE bfs AS (
            SELECT
                e.source_id,
                e.target_id,
                ARRAY[e.source_id] AS path,
                1 AS depth
            FROM knowledge_edges e
            WHERE e.source_id = $1::uuid {edge_filter}

            UNION ALL

            SELECT
                e.source_id,
                e.target_id,
                b.path || e.source_id,
                b.depth + 1
            FROM knowledge_edges e
            JOIN bfs b ON e.source_id = b.target_id
            WHERE b.depth < $3
              AND NOT (e.source_id = ANY(b.path))  -- cycle prevention
              {edge_filter}
        )
        SELECT path || target_id AS full_path
        FROM bfs
        WHERE target_id = $2::uuid
        ORDER BY depth
        LIMIT 1;
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, *params)
            if not row:
                return None
            path_ids = [str(uid) for uid in row["full_path"]]
            # Fetch actual nodes on the path
            nodes = []
            for nid in path_ids:
                node = await self.get_node(nid)
                if node:
                    nodes.append(node)
            # Fetch edges between consecutive path nodes
            edges = []
            for i in range(len(path_ids) - 1):
                edge_rows = await self.get_edges(source_id=path_ids[i], target_id=path_ids[i+1])
                edges.extend(edge_rows)
            return PathResult(nodes=nodes, edges=edges, total_weight=float(len(edges)))

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
                
        # Load edges between subgraph nodes
        subgraph_edges: List[GraphEdge] = []
        if unique_nodes:
            node_ids = [n.node_id for n in unique_nodes]
            # Use separate placeholders for source_id IN and target_id IN
            src_placeholders = ", ".join(f"${i+1}::uuid" for i in range(len(node_ids)))
            tgt_placeholders = ", ".join(f"${i+1+len(node_ids)}::uuid" for i in range(len(node_ids)))
            sql = f"""
                SELECT * FROM knowledge_edges
                WHERE source_id IN ({src_placeholders})
                  AND target_id IN ({tgt_placeholders})
            """
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *node_ids, *node_ids)
                subgraph_edges = [self._map_edge(row) for row in rows]

        return SubgraphResult(
            nodes=unique_nodes,
            edges=subgraph_edges,
            center_node_id=center_id,
            radius=radius
        )

    # ========== Analysis & Bulk Operations ==========

    async def find_connected_components(self, workspace_id: Optional[str] = None) -> List[List[str]]:
        """Find connected components using union-find via SQL."""
        ws_filter = ""
        params: list = []
        if workspace_id:
            ws_filter = "WHERE workspace_id = $1::uuid"
            params.append(workspace_id)

        sql = f"""
        WITH RECURSIVE
        all_nodes AS (
            SELECT id FROM knowledge_nodes {ws_filter}
        ),
        all_pairs AS (
            SELECT source_id AS a, target_id AS b FROM knowledge_edges
            UNION
            SELECT target_id AS a, source_id AS b FROM knowledge_edges
        ),
        component_walk AS (
            SELECT id AS node_id, id AS component_root
            FROM all_nodes

            UNION

            SELECT p.b, c.component_root
            FROM component_walk c
            JOIN all_pairs p ON p.a = c.node_id
            WHERE p.b != c.component_root
        )
        SELECT component_root, array_agg(DISTINCT node_id::text) AS members
        FROM component_walk
        GROUP BY component_root;
        """
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
                return [list(row["members"]) for row in rows]
        except Exception as e:
            # Fallback: simpler approach if recursive CTE has issues
            logger.warning(f"find_connected_components CTE failed, using simple fallback: {e}")
            async with self._pool.acquire() as conn:
                ws_sql = f"SELECT id::text FROM knowledge_nodes {ws_filter}"
                node_rows = await conn.fetch(ws_sql, *params)
                # Return each node as its own component (conservative fallback)
                return [[row["id"]] for row in node_rows]

    async def get_node_degree(self, node_id: str, direction: str = "both") -> int:
        """Count edges connected to a node."""
        if direction == "out":
            sql = "SELECT COUNT(*) FROM knowledge_edges WHERE source_id = $1::uuid"
        elif direction == "in":
            sql = "SELECT COUNT(*) FROM knowledge_edges WHERE target_id = $1::uuid"
        else:
            sql = "SELECT COUNT(*) FROM knowledge_edges WHERE source_id = $1::uuid OR target_id = $1::uuid"

        async with self._pool.acquire() as conn:
            count = await conn.fetchval(sql, node_id)
            return count or 0

    async def find_similar_patterns(self, node_id: str, max_results: int = 10) -> List[GraphNode]:
        """
        Find nodes with similar properties via text search.
        TODO(Phase 95): Replace ILIKE with pgvector cosine similarity
        when CodeBERT embeddings are available.
        """
        # Get the source node's properties for search terms
        source = await self.get_node(node_id)
        if not source:
            return []

        # Extract key terms from source node properties
        search_text = json.dumps(source.properties)
        # Use the node's name or first meaningful property value
        search_term = source.properties.get("name", source.properties.get("title", ""))
        if not search_term:
            return []

        sql = """
            SELECT * FROM knowledge_nodes
            WHERE id != $1::uuid
              AND node_type = $2
              AND properties::text ILIKE $3
            LIMIT $4
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, node_id, source.node_type.value, f"%{search_term}%", max_results)
            return [self._map_node(row) for row in rows]

    async def bulk_add_nodes(self, nodes: List[Dict[str, Any]]) -> List[GraphNode]:
        """Batch insert nodes with ON CONFLICT DO NOTHING."""
        if not nodes:
            return []

        results: List[GraphNode] = []
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for node_data in nodes:
                    node_id = node_data.get("node_id", node_data.get("id"))
                    node_type = node_data.get("node_type", "concept")
                    properties = node_data.get("properties", {})
                    workspace_id = properties.get("workspace_id", node_data.get("workspace_id"))

                    if not workspace_id:
                        logger.warning(f"Skipping node {node_id}: missing workspace_id")
                        continue

                    row = await conn.fetchrow("""
                        INSERT INTO knowledge_nodes (id, workspace_id, node_type, label, properties)
                        VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb)
                        ON CONFLICT (id) DO NOTHING
                        RETURNING *
                    """,
                        node_id,
                        workspace_id,
                        node_type if isinstance(node_type, str) else node_type.value,
                        properties.get("name", str(node_id)),
                        json.dumps(properties)
                    )
                    if row:
                        results.append(self._map_node(row))
        return results

    async def bulk_add_edges(self, edges: List[Dict[str, Any]]) -> List[GraphEdge]:
        """Batch insert edges with ON CONFLICT DO NOTHING."""
        if not edges:
            return []

        results: List[GraphEdge] = []
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for edge_data in edges:
                    source_id = edge_data.get("source_id")
                    target_id = edge_data.get("target_id")
                    edge_type = edge_data.get("edge_type", "relates_to")
                    weight = edge_data.get("weight", 1.0)
                    metadata = edge_data.get("properties", edge_data.get("metadata", {}))

                    # Look up workspace from source node
                    ws_row = await conn.fetchrow(
                        "SELECT workspace_id FROM knowledge_nodes WHERE id = $1::uuid",
                        source_id
                    )
                    workspace_id = ws_row["workspace_id"] if ws_row else None

                    row = await conn.fetchrow("""
                        INSERT INTO knowledge_edges (workspace_id, source_id, target_id, edge_type, weight, metadata)
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6::jsonb)
                        ON CONFLICT DO NOTHING
                        RETURNING *
                    """,
                        workspace_id,
                        source_id,
                        target_id,
                        edge_type if isinstance(edge_type, str) else edge_type.value,
                        weight,
                        json.dumps(metadata)
                    )
                    if row:
                        results.append(self._map_edge(row))
        return results

    # ========== Statistics & Export ==========

    async def get_statistics(self) -> Dict[str, Any]:
        """Return graph-level statistics."""
        async with self._pool.acquire() as conn:
            node_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes")
            edge_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_edges")
            type_counts = await conn.fetch(
                "SELECT node_type, COUNT(*) as cnt FROM knowledge_nodes GROUP BY node_type"
            )
            return {
                "total_nodes": node_count or 0,
                "total_edges": edge_count or 0,
                "nodes_by_type": {row["node_type"]: row["cnt"] for row in type_counts},
            }

    async def export_snapshot(self) -> Dict[str, Any]:
        """Export entire graph as JSON-serializable dict (for backup/migration)."""
        async with self._pool.acquire() as conn:
            node_rows = await conn.fetch("SELECT * FROM knowledge_nodes")
            edge_rows = await conn.fetch("SELECT * FROM knowledge_edges")
        return {
            "nodes": {str(r["id"]): dict(r) for r in node_rows},
            "edges": {str(r["id"]): dict(r) for r in edge_rows},
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    async def import_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Import graph from snapshot dict (no-op for postgres — use SQL migrations)."""
        logger.info("import_snapshot called on PostgresKnowledgeGraph — skipping (use SQL migrations)")
