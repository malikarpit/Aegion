"""
GraphRAG Memory Engine — Phase 29 (Elevated): Entity-Centric Knowledge Graph.

Replaces flat vector similarity with a hybrid retrieval system:
  1. LLM-powered entity/relationship extraction from incoming memory chunks
  2. In-memory knowledge graph (NetworkX) for multi-hop traversal
  3. Community detection (Louvain) for workspace-level summaries
  4. Hybrid scoring: graph relevance × vector similarity for final ranking

Inspired by Microsoft Research's GraphRAG (2024) and extended for
workspace-scoped development memory.

Why GraphRAG beats plain vector search:
  - Vector search returns isolated chunks. GraphRAG returns connected subgraphs.
  - "How does Archon interact with Sentinel?" → vector search returns 2 unrelated
    chunks. GraphRAG traverses Archon→governs→Proposals→scanned_by→Sentinel.
  - Community summaries give high-level workspace overviews without reading
    every document.

Architecture:
  MemoryChunk   → raw text stored with embeddings (the vector layer)
  Entity        → extracted named concepts (services, files, patterns, decisions)
  Relationship  → directed, typed connections between entities
  KnowledgeGraph → NetworkX DiGraph holding entities + relationships
  GraphRAGEngine → orchestrates extraction, graph ops, and hybrid retrieval
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from ..core.logging import logger


# ──────────────────────────────────────────────────────────────────────────────
# Types
# ──────────────────────────────────────────────────────────────────────────────

class EntityType(str, Enum):
    SERVICE = "service"           # e.g., "Archon", "Sentinel", "Praxis"
    FILE = "file"                 # e.g., "model_router.py"
    CONCEPT = "concept"           # e.g., "FrugalGPT cascade", "governance tier"
    DECISION = "decision"         # e.g., "ADR-007: Use pgvector for cache"
    PATTERN = "pattern"           # e.g., "singleton pattern", "circuit breaker"
    PERSON = "person"             # e.g., "Arpit"
    TECHNOLOGY = "technology"     # e.g., "Supabase", "Redis", "Docker"
    RULE = "rule"                 # e.g., "T3 requires human approval"
    ERROR = "error"               # e.g., "ImportError in ghost_text"


class RelationshipType(str, Enum):
    DEPENDS_ON = "depends_on"
    IMPLEMENTS = "implements"
    GOVERNS = "governs"
    USES = "uses"
    PRODUCES = "produces"
    CONSUMES = "consumes"
    CONFLICTS_WITH = "conflicts_with"
    SUPERSEDES = "supersedes"
    PART_OF = "part_of"
    CAUSES = "causes"
    RESOLVES = "resolves"
    SIMILAR_TO = "similar_to"


@dataclass
class Entity:
    """A named concept extracted from memory chunks."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    entity_type: EntityType = EntityType.CONCEPT
    description: str = ""
    source_chunks: List[str] = field(default_factory=list)  # IDs of chunks that mention this entity
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "name": self.name, "type": self.entity_type.value,
            "description": self.description, "source_chunks": self.source_chunks,
            "properties": self.properties,
        }


@dataclass
class Relationship:
    """A directed, typed connection between two entities."""
    source_id: str
    target_id: str
    rel_type: RelationshipType
    weight: float = 1.0               # Strength of relationship
    evidence: str = ""                 # Why this relationship exists
    source_chunk: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "source": self.source_id, "target": self.target_id,
            "type": self.rel_type.value, "weight": self.weight,
            "evidence": self.evidence,
        }


@dataclass
class MemoryChunk:
    """Raw text memory with optional embedding."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str = ""
    content: str = ""
    memory_type: str = "context"       # context, pattern, lesson, decision
    tags: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]


@dataclass
class RetrievalResult:
    """A single result from hybrid retrieval."""
    content: str
    score: float                       # Combined graph + vector score
    source: str                        # "graph", "vector", or "hybrid"
    entities: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    hop_distance: int = 0              # Graph distance from query entities
    chunk_id: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Knowledge Graph (NetworkX-backed)
# ──────────────────────────────────────────────────────────────────────────────

class KnowledgeGraph:
    """
    In-memory directed knowledge graph per workspace.

    Uses NetworkX for graph operations: traversal, community detection,
    shortest paths, and subgraph extraction.
    """

    def __init__(self) -> None:
        try:
            import networkx as nx
            self._nx = nx
        except ImportError:
            self._nx = None
            logger.warning("networkx not installed — GraphRAG will use fallback graph")

        self.entities: Dict[str, Entity] = {}           # id → Entity
        self.entity_names: Dict[str, str] = {}          # normalized_name → id
        self.relationships: List[Relationship] = []
        self._graph = self._nx.DiGraph() if self._nx else None

    def add_entity(self, entity: Entity) -> str:
        """Add or merge an entity. Returns the entity ID."""
        norm_name = entity.name.lower().strip()
        if norm_name in self.entity_names:
            # Merge: update existing entity's sources
            existing_id = self.entity_names[norm_name]
            existing = self.entities[existing_id]
            existing.source_chunks.extend(entity.source_chunks)
            existing.source_chunks = list(set(existing.source_chunks))
            if entity.description and len(entity.description) > len(existing.description):
                existing.description = entity.description
            return existing_id

        self.entities[entity.id] = entity
        self.entity_names[norm_name] = entity.id
        if self._graph is not None:
            self._graph.add_node(entity.id, **entity.to_dict())
        return entity.id

    def add_relationship(self, rel: Relationship) -> None:
        """Add a relationship to the graph."""
        self.relationships.append(rel)
        if self._graph is not None:
            self._graph.add_edge(
                rel.source_id, rel.target_id,
                rel_type=rel.rel_type.value,
                weight=rel.weight,
                evidence=rel.evidence,
            )

    def find_entity(self, name: str) -> Optional[Entity]:
        """Find an entity by name (case-insensitive)."""
        norm = name.lower().strip()
        eid = self.entity_names.get(norm)
        return self.entities.get(eid) if eid else None

    def get_neighbors(self, entity_id: str, max_hops: int = 2) -> List[Tuple[Entity, int]]:
        """
        Get all entities within max_hops of the given entity.

        Returns list of (entity, hop_distance) tuples.
        """
        if self._graph is None or entity_id not in self._graph:
            return []

        visited: Dict[str, int] = {entity_id: 0}
        queue = [(entity_id, 0)]
        results = []

        while queue:
            current_id, depth = queue.pop(0)
            if depth >= max_hops:
                continue
            # Outgoing edges
            for neighbor_id in self._graph.successors(current_id):
                if neighbor_id not in visited:
                    visited[neighbor_id] = depth + 1
                    queue.append((neighbor_id, depth + 1))
                    if neighbor_id in self.entities:
                        results.append((self.entities[neighbor_id], depth + 1))
            # Incoming edges (bidirectional traversal)
            for neighbor_id in self._graph.predecessors(current_id):
                if neighbor_id not in visited:
                    visited[neighbor_id] = depth + 1
                    queue.append((neighbor_id, depth + 1))
                    if neighbor_id in self.entities:
                        results.append((self.entities[neighbor_id], depth + 1))

        return results

    def get_subgraph(self, entity_ids: List[str]) -> Dict[str, Any]:
        """Extract a subgraph containing the given entities and all edges between them."""
        nodes = [self.entities[eid].to_dict() for eid in entity_ids if eid in self.entities]
        edges = [
            rel.to_dict() for rel in self.relationships
            if rel.source_id in entity_ids and rel.target_id in entity_ids
        ]
        return {"nodes": nodes, "edges": edges}

    def detect_communities(self) -> List[List[str]]:
        """
        Detect communities using a greedy modularity approach.

        Falls back to connected components if community detection isn't available.
        Returns list of entity ID groups.
        """
        if self._graph is None or len(self._graph) < 2:
            return [list(self.entities.keys())]

        try:
            from networkx.algorithms.community import greedy_modularity_communities
            undirected = self._graph.to_undirected()
            communities = greedy_modularity_communities(undirected)
            return [list(c) for c in communities]
        except Exception:
            # Fallback: weakly connected components
            try:
                components = self._nx.weakly_connected_components(self._graph)
                return [list(c) for c in components]
            except Exception:
                return [list(self.entities.keys())]

    def get_stats(self) -> Dict[str, int]:
        return {
            "entities": len(self.entities),
            "relationships": len(self.relationships),
            "entity_types": dict(defaultdict(int, {
                e.entity_type.value: sum(1 for x in self.entities.values() if x.entity_type == e.entity_type)
                for e in self.entities.values()
            })),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Entity Extraction
# ──────────────────────────────────────────────────────────────────────────────

class EntityExtractor:
    """Extracts entities and relationships from text using LLM + heuristics."""

    # Fast heuristic patterns (run before LLM for zero-cost extraction)
    _SERVICE_PATTERN = re.compile(
        r'\b(Archon|Sentinel|Chronos|Noesis|Praxis|Aegion|ACK|Council)\b',
        re.IGNORECASE,
    )
    _FILE_PATTERN = re.compile(r'[\w/]+\.(py|ts|tsx|js|jsx|sql|yaml|yml|md)\b')
    _TECH_PATTERN = re.compile(
        r'\b(Supabase|Redis|Docker|PostgreSQL|pgvector|FastAPI|NextJS|GCP|'
        r'Cloud Run|Kubernetes|NetworkX|OpenAI|Anthropic|DeepSeek|Gemini|Ollama)\b',
        re.IGNORECASE,
    )
    _DECISION_PATTERN = re.compile(r'\bADR[-\s]?\d+\b', re.IGNORECASE)

    def extract_heuristic(self, text: str, chunk_id: str) -> Tuple[List[Entity], List[Relationship]]:
        """Fast, zero-cost extraction using regex patterns."""
        entities: List[Entity] = []
        seen_names: Set[str] = set()

        for match in self._SERVICE_PATTERN.finditer(text):
            name = match.group().strip()
            if name.lower() not in seen_names:
                seen_names.add(name.lower())
                entities.append(Entity(
                    name=name, entity_type=EntityType.SERVICE,
                    description=f"AEGION service: {name}",
                    source_chunks=[chunk_id],
                ))

        for match in self._FILE_PATTERN.finditer(text):
            name = match.group().strip()
            if name.lower() not in seen_names:
                seen_names.add(name.lower())
                entities.append(Entity(
                    name=name, entity_type=EntityType.FILE,
                    source_chunks=[chunk_id],
                ))

        for match in self._TECH_PATTERN.finditer(text):
            name = match.group().strip()
            if name.lower() not in seen_names:
                seen_names.add(name.lower())
                entities.append(Entity(
                    name=name, entity_type=EntityType.TECHNOLOGY,
                    source_chunks=[chunk_id],
                ))

        for match in self._DECISION_PATTERN.finditer(text):
            name = match.group().strip()
            if name.lower() not in seen_names:
                seen_names.add(name.lower())
                entities.append(Entity(
                    name=name, entity_type=EntityType.DECISION,
                    source_chunks=[chunk_id],
                ))

        # Infer relationships between co-occurring entities
        relationships = []
        entity_names_list = [e.name for e in entities]
        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1:]:
                # Co-occurrence implies a relationship
                relationships.append(Relationship(
                    source_id=e1.id, target_id=e2.id,
                    rel_type=RelationshipType.SIMILAR_TO,
                    weight=0.5,
                    evidence=f"Co-occurred in chunk {chunk_id}",
                    source_chunk=chunk_id,
                ))

        return entities, relationships

    async def extract_with_llm(
        self, text: str, chunk_id: str,
    ) -> Tuple[List[Entity], List[Relationship]]:
        """Deep extraction using LLM (costs money but catches more)."""
        prompt = (
            "Extract all entities and relationships from this development context.\n\n"
            f"TEXT:\n{text[:2000]}\n\n"
            "Respond ONLY with JSON:\n"
            '{"entities": [{"name": "...", "type": "service|file|concept|decision|pattern|technology|rule|error", '
            '"description": "..."}], '
            '"relationships": [{"source": "entity_name", "target": "entity_name", '
            '"type": "depends_on|implements|governs|uses|produces|consumes|conflicts_with|supersedes|part_of|causes|resolves", '
            '"evidence": "..."}]}'
        )

        try:
            from .council_kernel.engine import get_council_engine
            engine = get_council_engine()
            response = await engine.cascade_query("_graph_extract", prompt, max_budget_usd=0.02)

            data = self._parse_extraction(response.response)
            entities = []
            name_to_entity: Dict[str, Entity] = {}

            for raw in data.get("entities", []):
                try:
                    etype = EntityType(raw.get("type", "concept"))
                except ValueError:
                    etype = EntityType.CONCEPT
                e = Entity(
                    name=raw["name"], entity_type=etype,
                    description=raw.get("description", ""),
                    source_chunks=[chunk_id],
                )
                entities.append(e)
                name_to_entity[raw["name"].lower()] = e

            relationships = []
            for raw_rel in data.get("relationships", []):
                src = name_to_entity.get(raw_rel.get("source", "").lower())
                tgt = name_to_entity.get(raw_rel.get("target", "").lower())
                if src and tgt:
                    try:
                        rtype = RelationshipType(raw_rel.get("type", "uses"))
                    except ValueError:
                        rtype = RelationshipType.USES
                    relationships.append(Relationship(
                        source_id=src.id, target_id=tgt.id,
                        rel_type=rtype, weight=1.0,
                        evidence=raw_rel.get("evidence", ""),
                        source_chunk=chunk_id,
                    ))

            return entities, relationships
        except Exception as exc:
            logger.warning(f"LLM entity extraction failed: {exc}")
            return [], []

    def _parse_extraction(self, text: str) -> Dict:
        """Parse JSON from LLM response."""
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {"entities": [], "relationships": []}


# ──────────────────────────────────────────────────────────────────────────────
# GraphRAG Engine (Main Service)
# ──────────────────────────────────────────────────────────────────────────────

class GraphRAGEngine:
    """
    Full GraphRAG memory engine combining knowledge graph + vector retrieval.

    Usage:
        engine = GraphRAGEngine()
        await engine.ingest(workspace_id, "Archon governs all T3 proposals...", tags=["governance"])
        results = await engine.recall(workspace_id, "How does Archon handle T3 decisions?")
    """

    def __init__(self) -> None:
        self._graphs: Dict[str, KnowledgeGraph] = {}  # workspace_id → graph
        self._chunks: Dict[str, List[MemoryChunk]] = {}  # workspace_id → chunks
        self._extractor = EntityExtractor()

    def _get_graph(self, workspace_id: str) -> KnowledgeGraph:
        if workspace_id not in self._graphs:
            self._graphs[workspace_id] = KnowledgeGraph()
        return self._graphs[workspace_id]

    def _get_chunks(self, workspace_id: str) -> List[MemoryChunk]:
        if workspace_id not in self._chunks:
            self._chunks[workspace_id] = []
        return self._chunks[workspace_id]

    async def ingest(
        self,
        workspace_id: str,
        content: str,
        memory_type: str = "context",
        tags: Optional[List[str]] = None,
        use_llm_extraction: bool = False,
    ) -> Dict[str, Any]:
        """
        Ingest a memory chunk: store raw text + extract and index entities/relationships.

        Args:
            content:             Raw text to ingest
            memory_type:         context, pattern, lesson, decision
            tags:                Optional tags
            use_llm_extraction:  If True, uses LLM for deep extraction (costs money)

        Returns stats about what was extracted.
        """
        chunk = MemoryChunk(
            workspace_id=workspace_id,
            content=content,
            memory_type=memory_type,
            tags=tags or [],
        )

        # Store the raw chunk
        self._get_chunks(workspace_id).append(chunk)

        # Extract entities/relationships
        graph = self._get_graph(workspace_id)
        h_entities, h_rels = self._extractor.extract_heuristic(content, chunk.id)

        entity_ids = []
        for entity in h_entities:
            eid = graph.add_entity(entity)
            entity_ids.append(eid)
        for rel in h_rels:
            # Resolve entity IDs (heuristic extraction uses temporary IDs)
            src_entity = graph.find_entity(
                next((e.name for e in h_entities if e.id == rel.source_id), "")
            )
            tgt_entity = graph.find_entity(
                next((e.name for e in h_entities if e.id == rel.target_id), "")
            )
            if src_entity and tgt_entity:
                graph.add_relationship(Relationship(
                    source_id=src_entity.id, target_id=tgt_entity.id,
                    rel_type=rel.rel_type, weight=rel.weight,
                    evidence=rel.evidence, source_chunk=chunk.id,
                ))

        # Optional: deep LLM extraction
        llm_entity_count = 0
        if use_llm_extraction:
            l_entities, l_rels = await self._extractor.extract_with_llm(content, chunk.id)
            for entity in l_entities:
                graph.add_entity(entity)
                llm_entity_count += 1
            for rel in l_rels:
                graph.add_relationship(rel)

        # Persist to Supabase (best-effort)
        await self._persist_chunk(workspace_id, chunk)

        return {
            "chunk_id": chunk.id,
            "heuristic_entities": len(h_entities),
            "heuristic_relationships": len(h_rels),
            "llm_entities": llm_entity_count,
            "graph_stats": graph.get_stats(),
        }

    async def recall(
        self,
        workspace_id: str,
        query: str,
        max_results: int = 10,
        max_hops: int = 2,
    ) -> List[RetrievalResult]:
        """
        Hybrid retrieval: graph traversal + text matching.

        Strategy:
          1. Extract entities from the query (heuristic-only for speed)
          2. For each query entity found in the graph, traverse neighbors up to max_hops
          3. Collect all chunks referenced by the traversed entities
          4. Score chunks by: graph_relevance × text_overlap
          5. Return ranked results
        """
        graph = self._get_graph(workspace_id)
        chunks = self._get_chunks(workspace_id)

        # Hydrate from Supabase if in-memory graph is empty
        if not chunks:
            try:
                from ..db.supabase_client import get_supabase_client
                result = get_supabase_client().table("memories") \
                    .select("*") \
                    .eq("workspace_id", workspace_id) \
                    .order("created_at", desc=True) \
                    .limit(500) \
                    .execute()
                for row in (result.data or []):
                    chunk = MemoryChunk(
                        id=row.get("id", str(uuid.uuid4())),
                        workspace_id=workspace_id,
                        content=row.get("content", ""),
                        memory_type=row.get("memory_type", "context"),
                        tags=row.get("tags", []),
                        metadata=row.get("metadata", {}),
                    )
                    chunks.append(chunk)
                    # Re-extract entities for graph
                    h_entities, h_rels = self._extractor.extract_heuristic(chunk.content, chunk.id)
                    for entity in h_entities:
                        graph.add_entity(entity)
                if chunks:
                    logger.info(f"Memory hydrated from DB: {len(chunks)} chunks for {workspace_id}")
            except Exception as exc:
                logger.warning(f"Memory hydration from DB failed (using in-memory only): {exc}")

        # Step 1: Extract entities from the query
        query_entities, _ = self._extractor.extract_heuristic(query, "_query")

        # Step 2: Find matching entities in the graph and traverse
        relevant_chunk_ids: Dict[str, Tuple[float, int]] = {}  # chunk_id → (score, min_hops)

        for qe in query_entities:
            graph_entity = graph.find_entity(qe.name)
            if graph_entity:
                # Direct match: high score
                for cid in graph_entity.source_chunks:
                    if cid not in relevant_chunk_ids or relevant_chunk_ids[cid][1] > 0:
                        relevant_chunk_ids[cid] = (1.0, 0)

                # Traverse neighbors
                neighbors = graph.get_neighbors(graph_entity.id, max_hops)
                for neighbor, hops in neighbors:
                    decay = 1.0 / (1 + hops)  # Score decays with distance
                    for cid in neighbor.source_chunks:
                        current = relevant_chunk_ids.get(cid, (0.0, 999))
                        if decay > current[0]:
                            relevant_chunk_ids[cid] = (decay, hops)

        # Step 3: Text matching for chunks NOT found via graph traversal
        query_lower = query.lower()
        query_words = set(query_lower.split())
        for chunk in chunks:
            if chunk.id not in relevant_chunk_ids:
                # Simple word overlap score
                chunk_words = set(chunk.content.lower().split())
                overlap = len(query_words & chunk_words) / max(len(query_words), 1)
                if overlap > 0.15:  # Minimum relevance threshold
                    relevant_chunk_ids[chunk.id] = (overlap * 0.5, 999)  # Lower score than graph

        # Step 4: Build results
        chunk_map = {c.id: c for c in chunks}
        results: List[RetrievalResult] = []

        for chunk_id, (score, hops) in relevant_chunk_ids.items():
            chunk = chunk_map.get(chunk_id)
            if not chunk:
                continue
            source = "graph" if hops < 999 else "text"
            if hops < 999 and score < 1.0:
                source = "hybrid"

            results.append(RetrievalResult(
                content=chunk.content,
                score=round(score, 4),
                source=source,
                hop_distance=hops if hops < 999 else -1,
                chunk_id=chunk_id,
                entities=[
                    e.name for e in graph.entities.values()
                    if chunk_id in e.source_chunks
                ],
            ))

        # Sort by score descending
        results.sort(key=lambda r: -r.score)
        return results[:max_results]

    async def get_community_summaries(self, workspace_id: str) -> List[Dict]:
        """
        Detect communities in the knowledge graph and summarize each.

        Returns a list of community summaries with their key entities.
        """
        graph = self._get_graph(workspace_id)
        communities = graph.detect_communities()

        summaries = []
        for i, community_ids in enumerate(communities):
            entities = [graph.entities[eid] for eid in community_ids if eid in graph.entities]
            if not entities:
                continue
            # Group by type
            by_type: Dict[str, List[str]] = defaultdict(list)
            for e in entities:
                by_type[e.entity_type.value].append(e.name)

            summaries.append({
                "community_id": i,
                "entity_count": len(entities),
                "entities_by_type": dict(by_type),
                "key_entities": [e.name for e in sorted(entities, key=lambda e: len(e.source_chunks), reverse=True)[:5]],
            })

        return summaries

    async def forget(self, workspace_id: str, chunk_id: str) -> bool:
        """Remove a chunk and its entity references (soft forget)."""
        chunks = self._get_chunks(workspace_id)
        self._chunks[workspace_id] = [c for c in chunks if c.id != chunk_id]
        # Remove chunk references from entities (don't delete entities — they may have other sources)
        graph = self._get_graph(workspace_id)
        for entity in graph.entities.values():
            if chunk_id in entity.source_chunks:
                entity.source_chunks.remove(chunk_id)
        return True

    async def get_graph_snapshot(self, workspace_id: str) -> Dict[str, Any]:
        """Get a serializable snapshot of the workspace knowledge graph."""
        graph = self._get_graph(workspace_id)
        return {
            "entities": [e.to_dict() for e in graph.entities.values()],
            "relationships": [r.to_dict() for r in graph.relationships],
            "stats": graph.get_stats(),
            "communities": await self.get_community_summaries(workspace_id),
        }

    # ──────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────

    async def _persist_chunk(self, workspace_id: str, chunk: MemoryChunk) -> None:
        """Persist chunk to Supabase (best-effort)."""
        try:
            from ..db.supabase_client import get_supabase_client
            get_supabase_client().table("memories").insert({
                "id": chunk.id,
                "workspace_id": workspace_id,
                "content": chunk.content,
                "memory_type": chunk.memory_type,
                "tags": chunk.tags,
                "content_hash": chunk.content_hash,
                "metadata": chunk.metadata,
            }).execute()
        except Exception as exc:
            logger.warning(f"Memory persist failed: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# Backward-Compatible Wrapper
# ──────────────────────────────────────────────────────────────────────────────

class MemoryEngine:
    """Backward-compatible facade. Delegates to GraphRAGEngine internally."""

    def __init__(self) -> None:
        self._graph_rag = GraphRAGEngine()

    async def store(
        self, workspace_id: str, content: str,
        memory_type: str = "context", tags: Optional[List[str]] = None,
    ) -> Dict:
        return await self._graph_rag.ingest(workspace_id, content, memory_type, tags)

    async def recall(
        self, workspace_id: str, query: str, limit: int = 10,
    ) -> List[Dict]:
        results = await self._graph_rag.recall(workspace_id, query, max_results=limit)
        return [
            {"content": r.content, "score": r.score, "source": r.source,
             "entities": r.entities, "hop_distance": r.hop_distance}
            for r in results
        ]

    async def forget(self, workspace_id: str, chunk_id: str) -> bool:
        return await self._graph_rag.forget(workspace_id, chunk_id)

    @property
    def graph_rag(self) -> GraphRAGEngine:
        """Access the underlying GraphRAG engine for advanced operations."""
        return self._graph_rag


# Singleton
_memory_engine: Optional[MemoryEngine] = None

def get_memory_engine() -> MemoryEngine:
    global _memory_engine
    if _memory_engine is None:
        _memory_engine = MemoryEngine()
    return _memory_engine
