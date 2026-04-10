"""
Neo4j Knowledge Graph Adapter.

Production-ready implementation of KnowledgeGraphPort using Neo4j.

Enhancements:
- Schema initialization with uniqueness constraints and indexes
- APOC triggers for immutability enforcement on Decision/Evidence nodes
- Transactional governance: single-transaction proposal → decision flow
- Optimistic concurrency via version properties
- Full-text search index

Dependencies: neo4j (pip install neo4j)
"""

from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone
import uuid
import os

from ..ports.knowledge_graph import (
    KnowledgeGraphPort,
    GraphNode,
    GraphEdge,
    GraphNodeType,
    GraphEdgeType,
    PathResult,
    SubgraphResult
)
from ..core.logging import logger


# Node types that must never be mutated once created
IMMUTABLE_NODE_TYPES = frozenset({"decision", "evidence"})


class Neo4jKnowledgeGraph(KnowledgeGraphPort):
    """
    Neo4j implementation of the KnowledgeGraphPort.
    
    Requires Neo4j 4.x+ and the neo4j Python driver.
    
    Configuration via environment variables:
    - NEO4J_URI: bolt://localhost:7687
    - NEO4J_USER: neo4j
    - NEO4J_PASSWORD: password
    """
    
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
        database: str = "neo4j"
    ):
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver = None
    
    # ========== Lifecycle ==========
    
    async def connect(self) -> None:
        """Establish connection to Neo4j and initialize schema."""
        try:
            from neo4j import AsyncGraphDatabase
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password)
            )
            # Verify connection
            async with self._driver.session(database=self._database) as session:
                await session.run("RETURN 1")
            logger.info(f"Connected to Neo4j at {self._uri}")
            
            # Initialize schema (constraints, indexes, immutability triggers)
            await self._initialize_schema()
        except ImportError:
            raise ImportError(
                "neo4j package not installed. Run: pip install neo4j"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    async def _initialize_schema(self) -> None:
        """
        Create constraints, indexes, and APOC immutability triggers.
        
        Idempotent — safe to call on every startup.
        """
        async with self._driver.session(database=self._database) as session:
            # ── Uniqueness constraints ──
            constraints = [
                "CREATE CONSTRAINT node_id_unique IF NOT EXISTS "
                "FOR (n:decision) REQUIRE n.node_id IS UNIQUE",
                "CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS "
                "FOR (n:evidence) REQUIRE n.node_id IS UNIQUE",
                "CREATE CONSTRAINT proposal_id_unique IF NOT EXISTS "
                "FOR (n:proposal) REQUIRE n.node_id IS UNIQUE",
                "CREATE CONSTRAINT session_id_unique IF NOT EXISTS "
                "FOR (n:session) REQUIRE n.node_id IS UNIQUE",
            ]
            for cypher in constraints:
                try:
                    await session.run(cypher)
                except Exception as e:
                    logger.debug(f"Constraint may already exist: {e}")
            
            # ── Composite indexes for common queries ──
            indexes = [
                "CREATE INDEX node_workspace IF NOT EXISTS "
                "FOR (n:decision) ON (n.workspace_id)",
                "CREATE INDEX proposal_workspace IF NOT EXISTS "
                "FOR (n:proposal) ON (n.workspace_id)",
                "CREATE INDEX node_type_idx IF NOT EXISTS "
                "FOR (n:decision) ON (n.node_type, n.workspace_id)",
            ]
            for cypher in indexes:
                try:
                    await session.run(cypher)
                except Exception as e:
                    logger.debug(f"Index may already exist: {e}")
            
            # ── Full-text search index ──
            try:
                await session.run(
                    "CREATE FULLTEXT INDEX node_search IF NOT EXISTS "
                    "FOR (n:decision|evidence|proposal) "
                    "ON EACH [n.title, n.description, n.content]"
                )
            except Exception as e:
                logger.debug(f"Fulltext index may already exist: {e}")
            
            # ── APOC immutability triggers ──
            # Prevent SET/UPDATE on Decision and Evidence nodes
            for node_type in IMMUTABLE_NODE_TYPES:
                try:
                    trigger_name = f"immutable_{node_type}"
                    # Remove old trigger if exists, then re-add
                    await session.run(
                        "CALL apoc.trigger.remove($name)",
                        name=trigger_name,
                    )
                except Exception:
                    pass  # Trigger didn't exist
                
                try:
                    await session.run(
                        """
                        CALL apoc.trigger.add($name,
                          'UNWIND $assignedNodeProperties AS prop
                           WITH prop
                           WHERE prop.key <> "version"
                             AND ANY(lbl IN labels(prop.node)
                                     WHERE lbl = $label)
                             AND prop.node.created_at IS NOT NULL
                             AND prop.old IS NOT NULL
                           CALL apoc.util.validate(
                             true,
                             "Immutable " + $label + " node cannot be modified",
                             [0]
                           )
                           RETURN null',
                          {phase: 'before'}
                        )
                        """,
                        name=trigger_name,
                        label=node_type,
                    )
                    logger.info(
                        f"APOC immutability trigger installed for '{node_type}' nodes"
                    )
                except Exception as e:
                    logger.warning(
                        f"Could not install APOC trigger for '{node_type}' "
                        f"(APOC may not be available): {e}"
                    )
            
            logger.info("Neo4j schema initialization complete")
    
    async def disconnect(self) -> None:
        """Close connection to Neo4j."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Disconnected from Neo4j")
    
    async def health_check(self) -> bool:
        """Check if connection is healthy."""
        if not self._driver:
            return False
        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run("RETURN 1")
                await result.single()
            return True
        except Exception:
            return False
    
    # ========== Node Operations ==========
    
    async def add_node(
        self,
        node_type: GraphNodeType,
        node_id: str,
        properties: Dict[str, Any],
        labels: Optional[Set[str]] = None
    ) -> GraphNode:
        """Add a node to Neo4j with version tracking."""
        labels = labels or set()
        labels.add(node_type.value)
        
        # Serialize complex properties
        serialized_props = self._serialize_properties(properties)
        serialized_props["node_id"] = node_id
        serialized_props["node_type"] = node_type.value
        serialized_props["created_at"] = datetime.now(timezone.utc).isoformat()
        serialized_props["version"] = 1  # Optimistic concurrency
        
        label_str = ":".join(sorted(labels))
        
        async with self._driver.session(database=self._database) as session:
            query = f"""
            CREATE (n:{label_str} $props)
            RETURN n
            """
            result = await session.run(query, props=serialized_props)
            record = await result.single()
        
        return GraphNode(
            node_id=node_id,
            node_type=node_type,
            properties=properties,
            labels=labels,
            created_at=datetime.now(timezone.utc)
        )
    
    async def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID from Neo4j."""
        async with self._driver.session(database=self._database) as session:
            query = """
            MATCH (n {node_id: $node_id})
            RETURN n, labels(n) as labels
            """
            result = await session.run(query, node_id=node_id)
            record = await result.single()
            
            if not record:
                return None
            
            node_data = dict(record["n"])
            labels = set(record["labels"])
            
            return GraphNode(
                node_id=node_data.pop("node_id"),
                node_type=GraphNodeType(node_data.pop("node_type")),
                properties=node_data,
                labels=labels,
                created_at=datetime.fromisoformat(
                    node_data.pop("created_at", datetime.now(timezone.utc).isoformat())
                )
            )
    
    async def update_node(
        self,
        node_id: str,
        properties: Dict[str, Any],
        expected_version: Optional[int] = None
    ) -> Optional[GraphNode]:
        """
        Update node properties with optimistic concurrency.
        
        If expected_version is given, the update only succeeds when
        the current version matches — otherwise raises ValueError.
        Immutable node types (decision, evidence) are rejected.
        """
        serialized_props = self._serialize_properties(properties)
        serialized_props["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        async with self._driver.session(database=self._database) as session:
            # Check immutability at application layer (belt-and-suspenders)
            check = await session.run(
                "MATCH (n {node_id: $node_id}) RETURN n.node_type AS t",
                node_id=node_id,
            )
            rec = await check.single()
            if rec and rec["t"] in IMMUTABLE_NODE_TYPES:
                raise ValueError(
                    f"Cannot update immutable {rec['t']} node {node_id}"
                )
            
            if expected_version is not None:
                # Optimistic concurrency: CAS on version
                query = """
                MATCH (n {node_id: $node_id})
                WHERE n.version = $expected_version
                SET n += $props, n.version = $expected_version + 1
                RETURN n, labels(n) as labels
                """
                result = await session.run(
                    query,
                    node_id=node_id,
                    props=serialized_props,
                    expected_version=expected_version,
                )
            else:
                query = """
                MATCH (n {node_id: $node_id})
                SET n += $props, n.version = coalesce(n.version, 0) + 1
                RETURN n, labels(n) as labels
                """
                result = await session.run(
                    query, node_id=node_id, props=serialized_props
                )
            
            record = await result.single()
            if not record:
                if expected_version is not None:
                    raise ValueError(
                        f"Optimistic concurrency conflict on node {node_id}: "
                        f"expected version {expected_version}"
                    )
                return None
            
            return await self.get_node(node_id)
    
    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and its edges."""
        async with self._driver.session(database=self._database) as session:
            query = """
            MATCH (n {node_id: $node_id})
            DETACH DELETE n
            RETURN count(n) as deleted
            """
            result = await session.run(query, node_id=node_id)
            record = await result.single()
            return record["deleted"] > 0
    
    async def find_nodes(
        self,
        node_type: Optional[GraphNodeType] = None,
        labels: Optional[Set[str]] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[GraphNode]:
        """Find nodes matching criteria."""
        conditions = []
        params = {"limit": limit}
        
        if node_type:
            conditions.append("n.node_type = $node_type")
            params["node_type"] = node_type.value
        
        if properties:
            for key, value in properties.items():
                param_name = f"prop_{key}"
                conditions.append(f"n.{key} = ${param_name}")
                params[param_name] = value
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        label_match = f":{list(labels)[0]}" if labels else ""
        
        async with self._driver.session(database=self._database) as session:
            query = f"""
            MATCH (n{label_match})
            {where_clause}
            RETURN n, labels(n) as labels
            LIMIT $limit
            """
            result = await session.run(query, **params)
            records = await result.data()
            
            nodes = []
            for record in records:
                node_data = dict(record["n"])
                nodes.append(GraphNode(
                    node_id=node_data.pop("node_id"),
                    node_type=GraphNodeType(node_data.pop("node_type")),
                    properties=node_data,
                    labels=set(record["labels"]),
                    created_at=datetime.fromisoformat(
                        node_data.pop("created_at", datetime.now(timezone.utc).isoformat())
                    )
                ))
            return nodes
    
    # ========== Edge Operations ==========
    
    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: GraphEdgeType,
        properties: Optional[Dict[str, Any]] = None,
        weight: float = 1.0
    ) -> GraphEdge:
        """Add an edge between nodes."""
        properties = properties or {}
        edge_id = str(uuid.uuid4())
        
        serialized_props = self._serialize_properties(properties)
        serialized_props["edge_id"] = edge_id
        serialized_props["weight"] = weight
        serialized_props["created_at"] = datetime.now(timezone.utc).isoformat()
        
        async with self._driver.session(database=self._database) as session:
            query = f"""
            MATCH (a {{node_id: $source_id}})
            MATCH (b {{node_id: $target_id}})
            CREATE (a)-[r:{edge_type.value} $props]->(b)
            RETURN r
            """
            result = await session.run(
                query,
                source_id=source_id,
                target_id=target_id,
                props=serialized_props
            )
            await result.single()
        
        return GraphEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            properties=properties,
            weight=weight,
            created_at=datetime.now(timezone.utc)
        )
    
    async def get_edge(self, edge_id: str) -> Optional[GraphEdge]:
        """Get an edge by ID."""
        async with self._driver.session(database=self._database) as session:
            query = """
            MATCH (a)-[r {edge_id: $edge_id}]->(b)
            RETURN r, type(r) as edge_type, a.node_id as source, b.node_id as target
            """
            result = await session.run(query, edge_id=edge_id)
            record = await result.single()
            
            if not record:
                return None
            
            edge_data = dict(record["r"])
            return GraphEdge(
                edge_id=edge_data.pop("edge_id"),
                source_id=record["source"],
                target_id=record["target"],
                edge_type=GraphEdgeType(record["edge_type"]),
                properties=edge_data,
                weight=edge_data.pop("weight", 1.0),
                created_at=datetime.fromisoformat(
                    edge_data.pop("created_at", datetime.now(timezone.utc).isoformat())
                )
            )
    
    async def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        async with self._driver.session(database=self._database) as session:
            query = """
            MATCH ()-[r {edge_id: $edge_id}]->()
            DELETE r
            RETURN count(r) as deleted
            """
            result = await session.run(query, edge_id=edge_id)
            record = await result.single()
            return record["deleted"] > 0
    
    async def get_edges(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        edge_type: Optional[GraphEdgeType] = None
    ) -> List[GraphEdge]:
        """Get edges matching criteria."""
        conditions = []
        params = {}
        
        if source_id:
            conditions.append("a.node_id = $source_id")
            params["source_id"] = source_id
        if target_id:
            conditions.append("b.node_id = $target_id")
            params["target_id"] = target_id
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        edge_pattern = f":{edge_type.value}" if edge_type else ""
        
        async with self._driver.session(database=self._database) as session:
            query = f"""
            MATCH (a)-[r{edge_pattern}]->(b)
            {where_clause}
            RETURN r, type(r) as edge_type, a.node_id as source, b.node_id as target
            """
            result = await session.run(query, **params)
            records = await result.data()
            
            edges = []
            for record in records:
                edge_data = dict(record["r"])
                edges.append(GraphEdge(
                    edge_id=edge_data.pop("edge_id"),
                    source_id=record["source"],
                    target_id=record["target"],
                    edge_type=GraphEdgeType(record["edge_type"]),
                    properties=edge_data,
                    weight=edge_data.pop("weight", 1.0),
                    created_at=datetime.fromisoformat(
                        edge_data.pop("created_at", datetime.now(timezone.utc).isoformat())
                    )
                ))
            return edges
    
    # ========== Traversal Operations ==========
    
    async def find_path(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 10,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> Optional[PathResult]:
        """Find shortest path between two nodes."""
        edge_pattern = ""
        if edge_types:
            type_str = "|".join(e.value for e in edge_types)
            edge_pattern = f":{type_str}"
        
        async with self._driver.session(database=self._database) as session:
            query = f"""
            MATCH path = shortestPath(
                (a {{node_id: $from_id}})-[r{edge_pattern}*..{max_depth}]->(b {{node_id: $to_id}})
            )
            RETURN nodes(path) as nodes, relationships(path) as rels
            """
            result = await session.run(query, from_id=from_id, to_id=to_id)
            record = await result.single()
            
            if not record:
                return None
            
            # Convert Neo4j nodes/relationships to our models
            nodes = []
            for n in record["nodes"]:
                node_data = dict(n)
                nodes.append(GraphNode(
                    node_id=node_data.pop("node_id"),
                    node_type=GraphNodeType(node_data.pop("node_type")),
                    properties=node_data,
                    labels=set(n.labels)
                ))
            
            edges = []
            total_weight = 0.0
            for r in record["rels"]:
                edge_data = dict(r)
                weight = edge_data.pop("weight", 1.0)
                total_weight += weight
                edges.append(GraphEdge(
                    edge_id=edge_data.pop("edge_id"),
                    source_id=r.start_node["node_id"],
                    target_id=r.end_node["node_id"],
                    edge_type=GraphEdgeType(r.type),
                    properties=edge_data,
                    weight=weight
                ))
            
            return PathResult(
                nodes=nodes,
                edges=edges,
                total_weight=total_weight,
                path_length=len(edges)
            )
    
    async def get_ancestors(
        self,
        node_id: str,
        depth: int = 3,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> List[GraphNode]:
        """Get upstream/ancestor nodes."""
        edge_pattern = ""
        if edge_types:
            type_str = "|".join(e.value for e in edge_types)
            edge_pattern = f":{type_str}"
        
        async with self._driver.session(database=self._database) as session:
            query = f"""
            MATCH (n {{node_id: $node_id}})<-[r{edge_pattern}*1..{depth}]-(ancestor)
            RETURN DISTINCT ancestor, labels(ancestor) as labels
            """
            result = await session.run(query, node_id=node_id)
            records = await result.data()
            
            return self._records_to_nodes(records, "ancestor")
    
    async def get_descendants(
        self,
        node_id: str,
        depth: int = 3,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> List[GraphNode]:
        """Get downstream/descendant nodes."""
        edge_pattern = ""
        if edge_types:
            type_str = "|".join(e.value for e in edge_types)
            edge_pattern = f":{type_str}"
        
        async with self._driver.session(database=self._database) as session:
            query = f"""
            MATCH (n {{node_id: $node_id}})-[r{edge_pattern}*1..{depth}]->(descendant)
            RETURN DISTINCT descendant, labels(descendant) as labels
            """
            result = await session.run(query, node_id=node_id)
            records = await result.data()
            
            return self._records_to_nodes(records, "descendant")
    
    async def get_subgraph(
        self,
        center_id: str,
        radius: int = 2,
        edge_types: Optional[List[GraphEdgeType]] = None
    ) -> SubgraphResult:
        """Get subgraph around a node."""
        edge_pattern = ""
        if edge_types:
            type_str = "|".join(e.value for e in edge_types)
            edge_pattern = f":{type_str}"
        
        async with self._driver.session(database=self._database) as session:
            query = f"""
            MATCH (center {{node_id: $center_id}})
            CALL apoc.path.subgraphAll(center, {{
                maxLevel: $radius,
                relationshipFilter: '{edge_pattern.lstrip(":")}'
            }})
            YIELD nodes, relationships
            RETURN nodes, relationships
            """
            try:
                result = await session.run(query, center_id=center_id, radius=radius)
                record = await result.single()
            except Exception:
                # Fallback without APOC
                query = f"""
                MATCH path = (center {{node_id: $center_id}})-[r{edge_pattern}*0..{radius}]-(connected)
                WITH collect(DISTINCT connected) + center as allNodes, collect(DISTINCT r) as allRels
                RETURN allNodes as nodes, [rel IN allRels | rel] as relationships
                """
                result = await session.run(query, center_id=center_id)
                record = await result.single()
            
            if not record:
                return SubgraphResult(
                    nodes=[],
                    edges=[],
                    center_node_id=center_id,
                    radius=radius
                )
            
            nodes = []
            for n in record["nodes"]:
                node_data = dict(n)
                nodes.append(GraphNode(
                    node_id=node_data.pop("node_id"),
                    node_type=GraphNodeType(node_data.pop("node_type", "decision")),
                    properties=node_data,
                    labels=set(n.labels) if hasattr(n, 'labels') else set()
                ))
            
            edges = []
            for r in record["relationships"] or []:
                edge_data = dict(r)
                edges.append(GraphEdge(
                    edge_id=edge_data.pop("edge_id", str(uuid.uuid4())),
                    source_id=r.start_node["node_id"] if hasattr(r, 'start_node') else "",
                    target_id=r.end_node["node_id"] if hasattr(r, 'end_node') else "",
                    edge_type=GraphEdgeType(r.type) if hasattr(r, 'type') else GraphEdgeType.DEPENDS_ON,
                    properties=edge_data,
                    weight=edge_data.pop("weight", 1.0)
                ))
            
            return SubgraphResult(
                nodes=nodes,
                edges=edges,
                center_node_id=center_id,
                radius=radius
            )
    
    # ========== Analysis Operations ==========
    
    async def find_connected_components(
        self,
        workspace_id: Optional[str] = None
    ) -> List[List[str]]:
        """Find connected components in the graph."""
        where_clause = ""
        params = {}
        if workspace_id:
            where_clause = "WHERE n.workspace_id = $workspace_id"
            params["workspace_id"] = workspace_id
        
        async with self._driver.session(database=self._database) as session:
            query = f"""
            CALL gds.wcc.stream({{
                nodeQuery: 'MATCH (n) {where_clause} RETURN id(n) as id',
                relationshipQuery: 'MATCH (a)-[r]->(b) RETURN id(a) as source, id(b) as target'
            }})
            YIELD nodeId, componentId
            WITH componentId, collect(gds.util.asNode(nodeId).node_id) as nodes
            RETURN nodes ORDER BY size(nodes) DESC
            """
            try:
                result = await session.run(query, **params)
                records = await result.data()
                return [record["nodes"] for record in records]
            except Exception:
                # Fallback if GDS not available
                return []
    
    async def get_node_degree(
        self,
        node_id: str,
        direction: str = "both"
    ) -> int:
        """Get the degree (edge count) of a node."""
        if direction == "in":
            pattern = "<-[r]-"
        elif direction == "out":
            pattern = "-[r]->"
        else:
            pattern = "-[r]-"
        
        async with self._driver.session(database=self._database) as session:
            query = f"""
            MATCH (n {{node_id: $node_id}}){pattern}()
            RETURN count(r) as degree
            """
            result = await session.run(query, node_id=node_id)
            record = await result.single()
            return record["degree"] if record else 0
    
    async def find_similar_patterns(
        self,
        node_id: str,
        max_results: int = 10
    ) -> List[GraphNode]:
        """Find nodes with similar connection patterns."""
        async with self._driver.session(database=self._database) as session:
            # Find nodes with similar edge types and counts
            query = """
            MATCH (n {node_id: $node_id})-[r]->()
            WITH n, collect(type(r)) as edgeTypes, count(r) as edgeCount
            MATCH (other)-[r2]->()
            WHERE other <> n
            WITH other, collect(type(r2)) as otherTypes, count(r2) as otherCount, edgeTypes, edgeCount
            WHERE abs(otherCount - edgeCount) < 3
            RETURN other, labels(other) as labels
            ORDER BY size([x IN edgeTypes WHERE x IN otherTypes]) DESC
            LIMIT $limit
            """
            result = await session.run(query, node_id=node_id, limit=max_results)
            records = await result.data()
            
            return self._records_to_nodes(records, "other")
    
    # ========== Advanced Graph Algorithms ==========
    
    async def calculate_pagerank(
        self,
        workspace_id: Optional[str] = None,
        damping_factor: float = 0.85,
        max_iterations: int = 20
    ) -> Dict[str, float]:
        """
        Calculate PageRank scores for all nodes.
        
        Returns dict of node_id -> pagerank score.
        Higher scores indicate more influential nodes.
        """
        where_clause = ""
        params = {"damping": damping_factor, "iterations": max_iterations}
        if workspace_id:
            where_clause = "WHERE n.workspace_id = $workspace_id"
            params["workspace_id"] = workspace_id
        
        async with self._driver.session(database=self._database) as session:
            # Try Graph Data Science library first
            try:
                query = f"""
                CALL gds.pageRank.stream({{
                    nodeQuery: 'MATCH (n) {where_clause} RETURN id(n) as id',
                    relationshipQuery: 'MATCH (a)-[r]->(b) RETURN id(a) as source, id(b) as target',
                    dampingFactor: $damping,
                    maxIterations: $iterations
                }})
                YIELD nodeId, score
                RETURN gds.util.asNode(nodeId).node_id as node_id, score
                ORDER BY score DESC
                """
                result = await session.run(query, **params)
                records = await result.data()
                return {r["node_id"]: r["score"] for r in records}
            except Exception:
                # Fallback: simple approximation using in-degree
                query = f"""
                MATCH (n) {where_clause}
                OPTIONAL MATCH (n)<-[r]-()
                RETURN n.node_id as node_id, count(r) as in_degree
                ORDER BY in_degree DESC
                """
                result = await session.run(query, **params)
                records = await result.data()
                
                # Normalize to 0-1 range
                max_degree = max((r["in_degree"] for r in records), default=1) or 1
                return {
                    r["node_id"]: r["in_degree"] / max_degree 
                    for r in records
                }
    
    async def detect_communities(
        self,
        workspace_id: Optional[str] = None,
        algorithm: str = "louvain"
    ) -> List[List[str]]:
        """
        Detect communities/clusters in the graph.
        
        Returns list of communities, each a list of node IDs.
        """
        where_clause = ""
        params = {}
        if workspace_id:
            where_clause = "WHERE n.workspace_id = $workspace_id"
            params["workspace_id"] = workspace_id
        
        async with self._driver.session(database=self._database) as session:
            try:
                # Try Louvain community detection
                query = f"""
                CALL gds.louvain.stream({{
                    nodeQuery: 'MATCH (n) {where_clause} RETURN id(n) as id',
                    relationshipQuery: 'MATCH (a)-[r]-(b) RETURN id(a) as source, id(b) as target'
                }})
                YIELD nodeId, communityId
                WITH communityId, collect(gds.util.asNode(nodeId).node_id) as members
                RETURN members ORDER BY size(members) DESC
                """
                result = await session.run(query, **params)
                records = await result.data()
                return [r["members"] for r in records]
            except Exception:
                # Fallback: use weakly connected components
                return await self.find_connected_components(workspace_id)
    
    async def calculate_betweenness_centrality(
        self,
        workspace_id: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Calculate betweenness centrality - nodes on many shortest paths.
        
        High betweenness = important bridge between parts of the graph.
        """
        where_clause = ""
        params = {"limit": top_k}
        if workspace_id:
            where_clause = "WHERE n.workspace_id = $workspace_id"
            params["workspace_id"] = workspace_id
        
        async with self._driver.session(database=self._database) as session:
            try:
                query = f"""
                CALL gds.betweenness.stream({{
                    nodeQuery: 'MATCH (n) {where_clause} RETURN id(n) as id',
                    relationshipQuery: 'MATCH (a)-[r]->(b) RETURN id(a) as source, id(b) as target'
                }})
                YIELD nodeId, score
                RETURN gds.util.asNode(nodeId).node_id as node_id, score
                ORDER BY score DESC
                LIMIT $limit
                """
                result = await session.run(query, **params)
                records = await result.data()
                return [{"node_id": r["node_id"], "centrality": r["score"]} for r in records]
            except Exception:
                # Fallback: degree centrality approximation
                query = f"""
                MATCH (n) {where_clause}
                OPTIONAL MATCH (n)-[r]-()
                RETURN n.node_id as node_id, count(r) as degree
                ORDER BY degree DESC
                LIMIT $limit
                """
                result = await session.run(query, **params)
                records = await result.data()
                return [{"node_id": r["node_id"], "centrality": float(r["degree"])} for r in records]
    
    async def find_influential_decisions(
        self,
        workspace_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find most influential decisions based on combined metrics.
        
        Combines PageRank, degree, and downstream impact.
        """
        async with self._driver.session(database=self._database) as session:
            where_clause = ""
            params = {"limit": limit}
            if workspace_id:
                where_clause = "WHERE d.workspace_id = $workspace_id"
                params["workspace_id"] = workspace_id
            
            query = f"""
            MATCH (d:decision) {where_clause}
            OPTIONAL MATCH (d)<-[in_r]-()
            OPTIONAL MATCH (d)-[out_r]->()
            OPTIONAL MATCH path = (d)-[*1..3]->(downstream)
            WITH d, 
                 count(DISTINCT in_r) as in_degree,
                 count(DISTINCT out_r) as out_degree,
                 count(DISTINCT downstream) as downstream_count
            RETURN d.node_id as node_id,
                   d as properties,
                   in_degree,
                   out_degree,
                   downstream_count,
                   (in_degree * 2 + out_degree + downstream_count * 0.5) as influence_score
            ORDER BY influence_score DESC
            LIMIT $limit
            """
            result = await session.run(query, **params)
            records = await result.data()
            
            return [
                {
                    "node_id": r["node_id"],
                    "in_degree": r["in_degree"],
                    "out_degree": r["out_degree"],
                    "downstream_impact": r["downstream_count"],
                    "influence_score": r["influence_score"],
                }
                for r in records
            ]
    
    async def find_decision_lineage(
        self,
        node_id: str,
        direction: str = "both",
        max_depth: int = 5
    ) -> Dict[str, Any]:
        """
        Get full decision lineage (ancestors and/or descendants).
        
        Useful for understanding the origin and impact of decisions.
        """
        ancestors = []
        descendants = []
        
        if direction in ("both", "up"):
            ancestors = await self.get_ancestors(node_id, max_depth)
        
        if direction in ("both", "down"):
            descendants = await self.get_descendants(node_id, max_depth)
        
        return {
            "node_id": node_id,
            "ancestors": [
                {"node_id": n.node_id, "type": n.node_type.value}
                for n in ancestors
            ],
            "descendants": [
                {"node_id": n.node_id, "type": n.node_type.value}
                for n in descendants
            ],
            "total_lineage_size": len(ancestors) + len(descendants) + 1
        }
    
    # ========== Bulk Operations ==========
    
    async def bulk_add_nodes(
        self,
        nodes: List[Dict[str, Any]]
    ) -> List[GraphNode]:
        """Add multiple nodes in a single transaction."""
        async with self._driver.session(database=self._database) as session:
            async with session.begin_transaction() as tx:
                created_nodes = []
                for node_data in nodes:
                    node_type = GraphNodeType(node_data.get("node_type", "decision"))
                    node_id = node_data["node_id"]
                    props = self._serialize_properties(node_data.get("properties", {}))
                    props["node_id"] = node_id
                    props["node_type"] = node_type.value
                    props["created_at"] = datetime.now(timezone.utc).isoformat()
                    props["version"] = 1
                    
                    labels_set = set(node_data.get("labels", []))
                    labels_set.add(node_type.value)
                    label_str = ":".join(sorted(labels_set))
                    
                    await tx.run(f"CREATE (n:{label_str} $props)", props=props)
                    created_nodes.append(GraphNode(
                        node_id=node_id,
                        node_type=node_type,
                        properties=node_data.get("properties", {}),
                        labels=labels_set,
                        created_at=datetime.now(timezone.utc),
                    ))
                await tx.commit()
                return created_nodes
    
    async def bulk_add_edges(
        self,
        edges: List[Dict[str, Any]]
    ) -> List[GraphEdge]:
        """Add multiple edges in a single transaction."""
        async with self._driver.session(database=self._database) as session:
            async with session.begin_transaction() as tx:
                created_edges = []
                for edge_data in edges:
                    edge_type = GraphEdgeType(edge_data["edge_type"])
                    edge_id = str(uuid.uuid4())
                    props = self._serialize_properties(edge_data.get("properties", {}))
                    props["edge_id"] = edge_id
                    props["weight"] = edge_data.get("weight", 1.0)
                    props["created_at"] = datetime.now(timezone.utc).isoformat()
                    
                    await tx.run(
                        f"""
                        MATCH (a {{node_id: $src}})
                        MATCH (b {{node_id: $tgt}})
                        CREATE (a)-[r:{edge_type.value} $props]->(b)
                        """,
                        src=edge_data["source_id"],
                        tgt=edge_data["target_id"],
                        props=props,
                    )
                    created_edges.append(GraphEdge(
                        edge_id=edge_id,
                        source_id=edge_data["source_id"],
                        target_id=edge_data["target_id"],
                        edge_type=edge_type,
                        properties=edge_data.get("properties", {}),
                        weight=edge_data.get("weight", 1.0),
                        created_at=datetime.now(timezone.utc),
                    ))
                await tx.commit()
                return created_edges
    
    # ========== Full-Text Search ==========
    
    async def search_nodes(
        self,
        query: str,
        node_type: Optional[GraphNodeType] = None,
        limit: int = 10
    ) -> List[GraphNode]:
        """Full-text search using Neo4j fulltext index."""
        async with self._driver.session(database=self._database) as session:
            try:
                cypher = """
                CALL db.index.fulltext.queryNodes('node_search', $query)
                YIELD node, score
                """
                params: Dict[str, Any] = {"query": query, "limit": limit}
                
                if node_type:
                    cypher += "WHERE node.node_type = $node_type\n"
                    params["node_type"] = node_type.value
                
                cypher += """
                RETURN node AS n, labels(node) AS labels, score
                ORDER BY score DESC
                LIMIT $limit
                """
                result = await session.run(cypher, **params)
                records = await result.data()
                return self._records_to_nodes(records, "n")
            except Exception:
                # Fallback: CONTAINS search on title property
                where = "WHERE n.title CONTAINS $query"
                if node_type:
                    where += " AND n.node_type = $node_type"
                cypher = f"""
                MATCH (n) {where}
                RETURN n, labels(n) AS labels
                LIMIT $limit
                """
                params = {"query": query, "limit": limit}
                if node_type:
                    params["node_type"] = node_type.value
                result = await session.run(cypher, **params)
                records = await result.data()
                return self._records_to_nodes(records, "n")
    
    # ========== Transactional Governance ==========
    
    async def approve_proposal_tx(
        self,
        proposal_id: str,
        decision_id: str,
        approver_id: str,
        evidence_ids: List[str],
        decision_properties: Dict[str, Any],
    ) -> GraphNode:
        """
        Atomically approve a proposal — single transaction:
        
        1. Verify proposal exists and is in 'pending' status
        2. Verify all evidence nodes exist
        3. Create immutable Decision node
        4. Create APPROVED_BY edge (decision ← approver)
        5. Create SUPPORTS edges (decision ← evidence)
        6. Update proposal status to 'approved'
        
        If ANY step fails → entire transaction rolls back.
        """
        now = datetime.now(timezone.utc).isoformat()
        decision_props = self._serialize_properties(decision_properties)
        decision_props.update({
            "node_id": decision_id,
            "node_type": "decision",
            "created_at": now,
            "version": 1,
            "proposal_id": proposal_id,
            "approver_id": approver_id,
        })
        
        async with self._driver.session(database=self._database) as session:
            async with session.begin_transaction() as tx:
                # 1. Verify proposal state
                result = await tx.run(
                    """
                    MATCH (p:proposal {node_id: $pid})
                    RETURN p.status AS status, p.version AS version
                    """,
                    pid=proposal_id,
                )
                rec = await result.single()
                if not rec:
                    raise ValueError(f"Proposal {proposal_id} not found")
                if rec["status"] not in ("pending", "open", None):
                    raise ValueError(
                        f"Proposal {proposal_id} is '{rec['status']}', cannot approve"
                    )
                
                # 2. Verify evidence existence
                if evidence_ids:
                    result = await tx.run(
                        """
                        UNWIND $eids AS eid
                        OPTIONAL MATCH (e:evidence {node_id: eid})
                        RETURN eid, e IS NOT NULL AS found
                        """,
                        eids=evidence_ids,
                    )
                    records = await result.data()
                    missing = [r["eid"] for r in records if not r["found"]]
                    if missing:
                        raise ValueError(
                            f"Evidence nodes not found: {missing}"
                        )
                
                # 3. Create Decision node
                await tx.run(
                    "CREATE (d:decision $props)",
                    props=decision_props,
                )
                
                # 4. APPROVED_BY edge
                await tx.run(
                    """
                    MATCH (d:decision {node_id: $did})
                    MATCH (u {node_id: $uid})
                    CREATE (d)-[:approved_by {created_at: $now, edge_id: $eid}]->(u)
                    """,
                    did=decision_id,
                    uid=approver_id,
                    now=now,
                    eid=str(uuid.uuid4()),
                )
                
                # 5. SUPPORTS edges from evidence
                for eid in evidence_ids:
                    await tx.run(
                        """
                        MATCH (d:decision {node_id: $did})
                        MATCH (e:evidence {node_id: $eid})
                        CREATE (e)-[:supports {created_at: $now, edge_id: $edge_id}]->(d)
                        """,
                        did=decision_id,
                        eid=eid,
                        now=now,
                        edge_id=str(uuid.uuid4()),
                    )
                
                # 6. Update proposal status (optimistic concurrency)
                proposal_version = rec["version"] or 0
                result = await tx.run(
                    """
                    MATCH (p:proposal {node_id: $pid, version: $v})
                    SET p.status = 'approved',
                        p.approved_at = $now,
                        p.decision_id = $did,
                        p.version = $v + 1
                    RETURN p
                    """,
                    pid=proposal_id,
                    v=proposal_version,
                    now=now,
                    did=decision_id,
                )
                rec = await result.single()
                if not rec:
                    raise ValueError(
                        f"Concurrent modification on proposal {proposal_id}"
                    )
                
                await tx.commit()
        
        logger.info(
            f"Proposal {proposal_id} approved as decision {decision_id} "
            f"with {len(evidence_ids)} evidence nodes (transaction committed)"
        )
        return await self.get_node(decision_id)
    
    # ========== Graph Statistics ==========
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get graph-level statistics for health checks and monitoring."""
        async with self._driver.session(database=self._database) as session:
            result = await session.run("""
            MATCH (n)
            WITH count(n) AS node_count
            OPTIONAL MATCH ()-[r]->()
            RETURN node_count, count(r) AS edge_count
            """)
            rec = await result.single()
            
            # Per-type breakdown
            type_result = await session.run("""
            MATCH (n)
            RETURN n.node_type AS node_type, count(n) AS count
            ORDER BY count DESC
            """)
            type_data = await type_result.data()
            
            return {
                "total_nodes": rec["node_count"] if rec else 0,
                "total_edges": rec["edge_count"] if rec else 0,
                "nodes_by_type": {
                    r["node_type"]: r["count"] for r in type_data
                },
                "backend": "neo4j",
                "database": self._database,
                "uri": self._uri,
            }
    
    # ========== Helpers ==========
    
    def _serialize_properties(self, props: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize complex types for Neo4j storage."""
        result = {}
        for key, value in props.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, (set, frozenset)):
                result[key] = list(value)
            elif isinstance(value, dict):
                result[key] = str(value)  # Neo4j doesn't support nested maps
            else:
                result[key] = value
        return result
    
    def _records_to_nodes(
        self,
        records: List[Dict[str, Any]],
        node_key: str
    ) -> List[GraphNode]:
        """Convert Neo4j records to GraphNode list."""
        nodes = []
        for record in records:
            node_data = dict(record[node_key])
            nodes.append(GraphNode(
                node_id=node_data.pop("node_id", "unknown"),
                node_type=GraphNodeType(node_data.pop("node_type", "decision")),
                properties=node_data,
                labels=set(record.get("labels", [])),
                created_at=datetime.fromisoformat(
                    node_data.pop("created_at", datetime.now(timezone.utc).isoformat())
                )
            ))
        return nodes
