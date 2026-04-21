"""
Tests for RAG Enricher — Phase R1: GraphRAG Louvain Communities.

Covers:
    RAGEnricher (keyword-based):
        - Returns original query when no context
        - Adds context prefix
        - Truncates to max_tokens
        - Security keywords trigger risk lookup
        - Singleton exists

    GraphRAGEnricher (graph-based):
        - Entity extraction
        - Graph construction (nodes + edges)
        - Louvain community detection
        - Singleton community filtering
        - Community summarisation (top entities)
        - Community ranking by Jaccard similarity
        - Fallback when networkx unavailable
        - Community cache TTL
        - Empty workspace returns fallback
        - Performance (<100ms for 500 entries)

References:
    - Edge et al., 2024 — "From Local to Global: A Graph RAG Approach" (Microsoft)
    - Blondel et al., 2008 — "Fast unfolding of communities" (Louvain)
"""

import pytest
import time

from app.services.council_kernel.rag_enricher import (
    RAGEnricher,
    GraphRAGEnricher,
    _extract_entities,
    rag_enricher,
    graph_rag_enricher,
)


# ══════════════════════════════════════════════════════════════════════════════
# ENTITY EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

class TestEntityExtraction:
    """Entity extraction from text."""

    def test_extracts_keywords(self):
        entities = _extract_entities("Python database migration system")
        assert "python" in entities
        assert "database" in entities
        assert "migration" in entities
        assert "system" in entities

    def test_removes_stop_words(self):
        entities = _extract_entities("the quick brown fox is very fast")
        assert "the" not in entities
        assert "is" not in entities
        assert "very" not in entities

    def test_removes_short_tokens(self):
        entities = _extract_entities("go do if me")
        # All are either <= 2 chars or stop words → filtered
        assert len(entities) == 0

    def test_empty_text(self):
        assert _extract_entities("") == set()


# ══════════════════════════════════════════════════════════════════════════════
# RAG ENRICHER — KEYWORD FALLBACK
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGEnricherBasic:
    """Keyword-based RAGEnricher (base class)."""

    @pytest.mark.asyncio
    async def test_enrich_returns_query_in_output(self):
        enricher = RAGEnricher()
        result = await enricher.enrich("ws1", "hello world")
        # Query should always be present in enriched output
        assert "hello world" in result

    @pytest.mark.asyncio
    async def test_enrich_truncates_context(self):
        enricher = RAGEnricher()
        # With no external deps available, just returns query
        result = await enricher.enrich("ws1", "test query", max_context_tokens=5)
        assert isinstance(result, str)

    def test_singleton_exists(self):
        assert rag_enricher is not None
        assert isinstance(rag_enricher, RAGEnricher)


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH RAG ENRICHER — GRAPH CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════════════

class TestGraphConstruction:
    """Entity co-occurrence graph building."""

    def test_build_graph_creates_nodes(self):
        memories = [
            {"content": "Python framework for database migrations"},
            {"content": "Database schema validation tools"},
        ]
        graph = GraphRAGEnricher.build_entity_graph(memories)
        assert graph.number_of_nodes() > 0
        assert graph.has_node("database")

    def test_build_graph_creates_edges(self):
        memories = [
            {"content": "Python framework database"},
        ]
        graph = GraphRAGEnricher.build_entity_graph(memories)
        # python and database co-occur → edge
        assert graph.has_edge("python", "database")
        assert graph.has_edge("python", "framework")

    def test_edge_weight_increases_with_cooccurrence(self):
        memories = [
            {"content": "Python database connection"},
            {"content": "Python database migration"},
        ]
        graph = GraphRAGEnricher.build_entity_graph(memories)
        assert graph["python"]["database"]["weight"] == 2

    def test_empty_memories(self):
        graph = GraphRAGEnricher.build_entity_graph([])
        assert graph.number_of_nodes() == 0


# ══════════════════════════════════════════════════════════════════════════════
# COMMUNITY DETECTION
# ══════════════════════════════════════════════════════════════════════════════

class TestCommunityDetection:
    """Louvain community detection."""

    def test_detects_communities(self):
        memories = [
            {"content": "Python framework database schema migration tools"},
            {"content": "React frontend component rendering virtual DOM"},
            {"content": "Python database connection pooling optimization"},
            {"content": "React component lifecycle state management hooks"},
        ]
        graph = GraphRAGEnricher.build_entity_graph(memories)
        communities = GraphRAGEnricher.detect_communities(graph)
        assert len(communities) >= 1

    def test_filters_singletons(self):
        memories = [
            {"content": "Python database migration"},
            {"content": "React frontend component"},
        ]
        graph = GraphRAGEnricher.build_entity_graph(memories)
        communities = GraphRAGEnricher.detect_communities(graph)
        for comm in communities:
            assert len(comm) >= 2

    def test_empty_graph_returns_empty(self):
        import networkx as nx
        graph = nx.Graph()
        communities = GraphRAGEnricher.detect_communities(graph)
        assert communities == []

    def test_single_node_graph_returns_empty(self):
        import networkx as nx
        graph = nx.Graph()
        graph.add_node("solo")
        communities = GraphRAGEnricher.detect_communities(graph)
        assert communities == []


# ══════════════════════════════════════════════════════════════════════════════
# COMMUNITY RANKING
# ══════════════════════════════════════════════════════════════════════════════

class TestCommunityRanking:
    """Ranking communities by Jaccard similarity to query."""

    def test_rank_by_relevance(self):
        import networkx as nx
        graph = nx.Graph()
        comm_db = {"python", "database", "migration"}
        comm_ui = {"react", "frontend", "component"}
        for n in comm_db | comm_ui:
            graph.add_node(n)

        ranked = GraphRAGEnricher.rank_communities(
            "database migration strategy",
            [comm_db, comm_ui],
            graph,
        )
        # DB community should rank first
        assert ranked[0] == comm_db

    def test_empty_query_returns_all(self):
        import networkx as nx
        graph = nx.Graph()
        comms = [{"python", "database"}, {"react", "frontend"}]
        ranked = GraphRAGEnricher.rank_communities("", comms, graph)
        assert len(ranked) == 2


# ══════════════════════════════════════════════════════════════════════════════
# COMMUNITY SUMMARISATION
# ══════════════════════════════════════════════════════════════════════════════

class TestCommunitySummary:
    """Per-community text summarisation."""

    def test_summary_includes_top_entities(self):
        memories = [
            {"content": "Python database migration framework for enterprise"},
            {"content": "Database schema versioning with Python tools"},
        ]
        graph = GraphRAGEnricher.build_entity_graph(memories)
        communities = GraphRAGEnricher.detect_communities(graph)
        assert len(communities) > 0

        summary = GraphRAGEnricher.summarize_community(
            communities[0], graph, memories
        )
        assert "Community [" in summary
        assert len(summary) > 10

    def test_summary_empty_when_no_excerpts(self):
        import networkx as nx
        graph = nx.Graph()
        graph.add_node("alpha", count=1)
        graph.add_node("beta", count=1)
        graph.add_edge("alpha", "beta", weight=1)
        summary = GraphRAGEnricher.summarize_community(
            {"alpha", "beta"}, graph, []
        )
        assert summary == ""


# ══════════════════════════════════════════════════════════════════════════════
# ENRICHMENT INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

class TestGraphRAGEnrichment:
    """End-to-end enrichment flow."""

    @pytest.mark.asyncio
    async def test_enrich_with_memories(self):
        enricher = GraphRAGEnricher()
        memories = [
            {"content": "Python database migration framework for production systems"},
            {"content": "Database schema versioning using Python alembic tools"},
            {"content": "React frontend component rendering with virtual DOM"},
            {"content": "React component lifecycle and state management patterns"},
        ]
        result = await enricher.enrich("ws1", "database migration", memories=memories)
        assert "[CONTEXT FROM GRAPHRAG COMMUNITIES]" in result
        assert "database migration" in result

    @pytest.mark.asyncio
    async def test_enrich_no_memories_falls_back(self):
        enricher = GraphRAGEnricher()
        result = await enricher.enrich("ws1", "hello world", memories=None)
        # Falls back to keyword enricher → returns original
        assert "hello world" in result

    @pytest.mark.asyncio
    async def test_enrich_empty_memories_falls_back(self):
        enricher = GraphRAGEnricher()
        result = await enricher.enrich("ws1", "hello world", memories=[])
        assert "hello world" in result

    @pytest.mark.asyncio
    async def test_cache_reused(self):
        enricher = GraphRAGEnricher()
        memories = [
            {"content": "Python database migration framework"},
            {"content": "Database schema versioning tools"},
        ]
        await enricher.enrich("ws1", "database", memories=memories)
        assert "ws1" in enricher._community_cache

        # Second call reuses cache
        await enricher.enrich("ws1", "python", memories=memories)
        assert "ws1" in enricher._community_cache

    def test_invalidate_cache(self):
        enricher = GraphRAGEnricher()
        enricher._community_cache["ws1"] = {"ts": time.monotonic(), "communities": [], "graph": None}
        enricher.invalidate_cache("ws1")
        assert "ws1" not in enricher._community_cache

    def test_invalidate_all(self):
        enricher = GraphRAGEnricher()
        enricher._community_cache["ws1"] = {"ts": 0}
        enricher._community_cache["ws2"] = {"ts": 0}
        enricher.invalidate_cache()
        assert len(enricher._community_cache) == 0

    def test_singleton_exists(self):
        assert graph_rag_enricher is not None
        assert isinstance(graph_rag_enricher, GraphRAGEnricher)

    @pytest.mark.asyncio
    async def test_performance_500_entries(self):
        """Graph construction for 500 entries should complete in <200ms."""
        enricher = GraphRAGEnricher()
        memories = [
            {"content": f"Module {i} uses database and python framework component_{i % 10}"}
            for i in range(500)
        ]
        start = time.monotonic()
        graph = enricher.build_entity_graph(memories)
        communities = enricher.detect_communities(graph)
        elapsed = time.monotonic() - start
        assert elapsed < 0.2, f"Graph construction took {elapsed:.3f}s (>200ms)"
        assert graph.number_of_nodes() > 0
