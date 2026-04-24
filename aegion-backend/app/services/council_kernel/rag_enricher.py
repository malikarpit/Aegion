"""
RAG Enricher — Phase 83: Inject relevant workspace knowledge before council execution.

Pulls the top-3 memories, top-3 past decisions, and active risk signals from the
workspace knowledge base and prepends them as structured context. Informed models
produce shorter, more accurate responses with fewer debate rounds.

Expected savings: 20-35% by reducing response length and required rounds.

GraphRAG Extension:
    When networkx is available, builds an entity co-occurrence graph from workspace
    knowledge, detects communities using the Louvain algorithm, and ranks community
    summaries by query-keyword overlap (Jaccard similarity).

    Reference: Edge et al., 2024 — "From Local to Global: A Graph RAG Approach
               to Query-Focused Summarization" (Microsoft Research)
    Reference: Trivedi et al., 2017 — "Know-Evolve: Deep Temporal Reasoning
               for Dynamic Knowledge Graphs" (Georgia Tech)
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

MAX_CONTEXT_TOKENS_DEFAULT: int = 500
SECURITY_KEYWORDS = ("security", "risk", "vulnerability", "auth", "exploit", "cve", "injection")

# Stop words excluded from entity extraction
_STOP_WORDS: Set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "up", "down", "and", "but", "or", "nor",
    "not", "so", "yet", "both", "either", "neither", "each", "every",
    "all", "any", "few", "more", "most", "other", "some", "such", "no",
    "only", "own", "same", "than", "too", "very", "just", "because",
    "if", "then", "else", "when", "while", "how", "what", "which",
    "who", "whom", "this", "that", "these", "those", "it", "its", "i",
    "me", "my", "we", "our", "you", "your", "he", "him", "his", "she",
    "her", "they", "them", "their", "about", "also", "use", "using",
}

# Minimum word length for an entity
_MIN_ENTITY_LEN = 3


class RAGEnricher:
    """
    Enriches a council prompt with compact workspace knowledge.

    Usage in engine.py (Step 0.9):
        query = await rag_enricher.enrich(workspace_id, query,
                                          max_context_tokens=config.rag_max_context_tokens)
    """

    async def enrich(
        self,
        workspace_id: str,
        query: str,
        max_context_tokens: int = MAX_CONTEXT_TOKENS_DEFAULT,
    ) -> str:
        """
        Build a RAG-enriched prompt string.

        Args:
            workspace_id:       Workspace to pull knowledge from.
            query:              Original query.
            max_context_tokens: Rough token cap for the prepended context block.

        Returns:
            Enriched prompt string, or the original query if no context found.
        """
        sections = []

        # 1. Recent memories
        try:
            from ..memory_engine import get_memory_engine
            memory = get_memory_engine()
            memories = await memory.recall(workspace_id, query, limit=3)
            if memories:
                mem_text = "\n".join(
                    f"- {m.get('content', '')[:150]}" for m in memories
                )
                sections.append(f"**Relevant workspace knowledge:**\n{mem_text}")
        except Exception:
            pass  # Memory engine unavailable — non-fatal

        # 2. Similar past decisions from knowledge graph
        try:
            from ..knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
            similar = await kg.search_similar(workspace_id, query, limit=3)
            if similar:
                dec_text = "\n".join(
                    f"- {s.get('title', 'Decision')}: {s.get('content', '')[:150]}"
                    for s in similar
                )
                sections.append(f"**Related past decisions:**\n{dec_text}")
        except Exception:
            pass  # Knowledge graph unavailable — non-fatal

        # 3. Active risk signals (only for security-related queries)
        if any(kw in query.lower() for kw in SECURITY_KEYWORDS):
            try:
                from ...db.supabase_client import get_supabase_client
                client = get_supabase_client()
                risks = (
                    client.table("risk_signals")
                    .select("severity,description")
                    .eq("workspace_id", workspace_id)
                    .eq("resolved", False)
                    .limit(5)
                    .execute()
                )
                if risks.data:
                    risk_text = "\n".join(
                        f"- [{r['severity']}] {r['description']}"
                        for r in risks.data
                    )
                    sections.append(f"**Active risk signals:**\n{risk_text}")
            except Exception:
                pass  # DB unavailable — non-fatal

        if not sections:
            return query  # Nothing to add; return original

        # Enforce rough token cap by truncating the context block
        context = "\n\n".join(sections)
        context_words = context.split()
        if len(context_words) > max_context_tokens:
            context = " ".join(context_words[:max_context_tokens]) + "..."

        return (
            "[CONTEXT FROM WORKSPACE KNOWLEDGE]\n"
            f"{context}\n\n"
            "[USER QUERY]\n"
            f"{query}\n\n"
            "Use the context above to inform your response. "
            "Cite relevant knowledge where applicable."
        )


# Module-level singleton
rag_enricher = RAGEnricher()


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH-RAG ENRICHER — Edge et al. 2024 (Microsoft Research)
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_entities(text: str) -> Set[str]:
    """
    Extract candidate entities from text via tokenisation + stop-word removal.

    Heuristic approach (no external NLP dependency):
        1. Lowercase, strip punctuation
        2. Split on whitespace
        3. Drop stop-words and short tokens
    """
    tokens = re.findall(r"[a-z][a-z0-9_]+", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) >= _MIN_ENTITY_LEN}


class GraphRAGEnricher:
    """
    Graph-based RAG using Louvain community detection.

    Reference: Edge et al., 2024 — "From Local to Global: A Graph RAG Approach"

    Workflow:
        1. Build entity co-occurrence graph from workspace memories
        2. Detect communities using Louvain algorithm (networkx)
        3. Generate per-community summaries (cached with TTL)
        4. On query: rank communities by Jaccard similarity → inject top-3

    Falls back to keyword-based ``RAGEnricher`` when networkx is unavailable.
    """

    CACHE_TTL_S: float = 300.0  # 5 minutes

    def __init__(self) -> None:
        self._community_cache: Dict[str, Dict[str, Any]] = {}  # workspace_id → cache entry
        self._keyword_fallback = RAGEnricher()

    # ── Public API ──────────────────────────────────────────────────────

    async def enrich(
        self,
        workspace_id: str,
        query: str,
        memories: Optional[List[Dict[str, Any]]] = None,
        max_context_tokens: int = MAX_CONTEXT_TOKENS_DEFAULT,
    ) -> str:
        """
        Enrich *query* with community-summarised context from *memories*.

        Args:
            workspace_id:       Workspace identifier.
            query:              The raw user query.
            memories:           Pre-fetched memory dicts ``[{"content": …}, …]``.
                                If ``None``, delegates to the keyword fallback.
            max_context_tokens: Rough word-level cap for the context block.

        Returns:
            Enriched prompt string.
        """
        try:
            import networkx as nx  # noqa: F401 — availability check
        except ImportError:
            # networkx missing → graceful keyword fallback
            return await self._keyword_fallback.enrich(workspace_id, query, max_context_tokens)

        if not memories:
            return await self._keyword_fallback.enrich(workspace_id, query, max_context_tokens)

        # Check community cache
        cache = self._community_cache.get(workspace_id)
        if cache and (time.monotonic() - cache["ts"]) < self.CACHE_TTL_S:
            communities = cache["communities"]
            graph = cache["graph"]
        else:
            graph = self.build_entity_graph(memories)
            communities = self.detect_communities(graph)
            self._community_cache[workspace_id] = {
                "communities": communities,
                "graph": graph,
                "ts": time.monotonic(),
            }

        if not communities:
            return await self._keyword_fallback.enrich(workspace_id, query, max_context_tokens)

        # Rank communities by relevance to query
        ranked = self.rank_communities(query, communities, graph)
        summaries = [
            self.summarize_community(comm, graph, memories)
            for comm in ranked[:3]
        ]
        summaries = [s for s in summaries if s]  # drop empties

        if not summaries:
            return await self._keyword_fallback.enrich(workspace_id, query, max_context_tokens)

        context = "\n\n".join(summaries)
        context_words = context.split()
        if len(context_words) > max_context_tokens:
            context = " ".join(context_words[:max_context_tokens]) + "..."

        return (
            "[CONTEXT FROM GRAPHRAG COMMUNITIES]\n"
            f"{context}\n\n"
            "[USER QUERY]\n"
            f"{query}\n\n"
            "Use the community context above to inform your response. "
            "Cite relevant knowledge where applicable."
        )

    # ── Graph Construction ──────────────────────────────────────────────

    @staticmethod
    def build_entity_graph(memories: List[Dict[str, Any]]) -> Any:
        """
        Build an entity co-occurrence graph.

        Nodes   = entities (keywords extracted from each memory entry).
        Edges   = co-occurrence in the same memory entry.
        Weights = number of entries where both entities appear.
        """
        import networkx as nx

        graph = nx.Graph()
        for mem in memories:
            text = mem.get("content", "") or ""
            entities = _extract_entities(text)
            entity_list = sorted(entities)  # deterministic iteration
            for ent in entity_list:
                if not graph.has_node(ent):
                    graph.add_node(ent, count=0)
                graph.nodes[ent]["count"] += 1

            # Add edges between all co-occurring pairs
            for i, e1 in enumerate(entity_list):
                for e2 in entity_list[i + 1:]:
                    if graph.has_edge(e1, e2):
                        graph[e1][e2]["weight"] += 1
                    else:
                        graph.add_edge(e1, e2, weight=1)

        return graph

    # ── Community Detection ─────────────────────────────────────────────

    @staticmethod
    def detect_communities(graph: Any) -> List[Set[str]]:
        """
        Detect communities using the Louvain algorithm.

        Reference: Blondel et al., 2008 — networkx.community.louvain_communities

        Filters out singleton communities (< 2 members) as noise.
        """
        import networkx as nx

        if graph.number_of_nodes() < 2:
            return []

        try:
            communities = nx.community.louvain_communities(
                graph, resolution=1.0, seed=42,
            )
        except Exception:
            # Fallback: connected components if louvain unavailable
            communities = list(nx.connected_components(graph))

        # Filter singletons
        return [c for c in communities if len(c) >= 2]

    # ── Community Ranking ───────────────────────────────────────────────

    @staticmethod
    def rank_communities(
        query: str,
        communities: List[Set[str]],
        graph: Any,
    ) -> List[Set[str]]:
        """
        Rank communities by Jaccard similarity between query keywords
        and the community's entity set.
        """
        query_entities = _extract_entities(query)
        if not query_entities:
            return communities  # return all if query has no extractable entities

        scored: List[Tuple[float, Set[str]]] = []
        for comm in communities:
            intersection = len(query_entities & comm)
            union = len(query_entities | comm)
            jaccard = intersection / max(union, 1)
            scored.append((jaccard, comm))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [comm for _, comm in scored]

    # ── Community Summarisation ─────────────────────────────────────────

    @staticmethod
    def summarize_community(
        community: Set[str],
        graph: Any,
        memories: List[Dict[str, Any]],
    ) -> str:
        """
        Generate a textual summary for a community.

        Strategy:
            1. Pick top-5 entities by degree centrality within community
            2. Collect memory entries that mention any community entity
            3. Format as: "Community about {entities}: {entry excerpts}"
        """
        import networkx as nx

        # Top entities by degree
        sub = graph.subgraph(community)
        centrality = nx.degree_centrality(sub)
        top_entities = sorted(centrality, key=centrality.get, reverse=True)[:5]

        # Collect relevant memory excerpts
        excerpts: List[str] = []
        for mem in memories:
            text = mem.get("content", "") or ""
            mem_entities = _extract_entities(text)
            if mem_entities & community:
                excerpts.append(text[:150])
            if len(excerpts) >= 3:
                break

        if not excerpts:
            return ""

        entity_label = ", ".join(top_entities)
        excerpt_text = "\n".join(f"  - {e}" for e in excerpts)
        return f"**Community [{entity_label}]:**\n{excerpt_text}"

    # ── Cache Management ────────────────────────────────────────────────

    def invalidate_cache(self, workspace_id: Optional[str] = None) -> None:
        """Clear community cache (all or per-workspace)."""
        if workspace_id:
            self._community_cache.pop(workspace_id, None)
        else:
            self._community_cache.clear()


# Module-level singletons
graph_rag_enricher = GraphRAGEnricher()
