"""
Evidence Manager — Phase 17 (Elevated): Contextual Evidence for Council Decisions.

Gathers relevant evidence from 6 sources:
  1. Knowledge graph — similar past decisions (Noesis graph)
  2. Timeline events — recent workspace activity
  3. Risk signals  — active unresolved risks
  4. ADRs          — Architecture Decision Records
  5. GraphRAG memory — multi-hop entity-aware workspace knowledge (NEW)
  6. Community summaries — high-level workspace entity clusters (NEW)

Sources 5 & 6 are the critical upgrade: they connect the council to the
full GraphRAG knowledge graph built by memory_engine.py, giving models
awareness of entity relationships across the entire codebase.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...core.logging import logger


class EvidenceManager:
    """
    Gather and attach evidence for council decisions.

    Usage:
        ev = EvidenceManager()
        evidence = await ev.gather_evidence(workspace_id, "Should we add Redis?")
        # Pass evidence as context to CouncilEngine.consult()
    """

    def _client(self):
        from ...db.supabase_client import get_supabase_client
        return get_supabase_client()

    async def gather_evidence(
        self,
        workspace_id: str,
        query: str,
        limit_each: int = 10,
    ) -> Dict[str, Any]:
        """
        Gather all relevant evidence for a workspace query.

        Returns:
            similar_decisions:   Semantically similar past decisions (knowledge graph)
            recent_events:       Latest N timeline events
            active_risks:        Unresolved risk signals
            past_adrs:           Recent Architecture Decision Records
            memory_recall:       GraphRAG hybrid retrieval results (entities + text)
            community_context:   High-level workspace entity clusters
        """
        client = self._client()

        # 1. Semantic search — similar past decisions (Noesis KG)
        similar_decisions: List[Dict] = []
        try:
            from ...services.knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
            similar_decisions = await kg.search_similar(
                workspace_id, query, limit=limit_each
            )
        except Exception as exc:
            logger.warning(f"Knowledge graph search failed (non-fatal): {exc}")

        # 2. Timeline events — most recent
        recent_events: List[Dict] = []
        try:
            result = (
                client.table("timeline_events")
                .select("*")
                .eq("workspace_id", workspace_id)
                .order("timestamp", desc=True)
                .limit(limit_each * 2)
                .execute()
            )
            recent_events = result.data or []
        except Exception as exc:
            logger.warning(f"Timeline events fetch failed (non-fatal): {exc}")

        # 3. Active risk signals
        active_risks: List[Dict] = []
        try:
            result = (
                client.table("risk_signals")
                .select("*")
                .eq("workspace_id", workspace_id)
                .eq("resolved", False)
                .order("created_at", desc=True)
                .limit(limit_each)
                .execute()
            )
            active_risks = result.data or []
        except Exception as exc:
            logger.warning(f"Risk signals fetch failed (non-fatal): {exc}")

        # 4. Past ADRs
        past_adrs: List[Dict] = []
        try:
            result = (
                client.table("adrs")
                .select("*")
                .eq("workspace_id", workspace_id)
                .order("created_at", desc=True)
                .limit(limit_each)
                .execute()
            )
            past_adrs = result.data or []
        except Exception as exc:
            logger.warning(f"ADRs fetch failed (non-fatal): {exc}")

        # 5. GraphRAG memory recall — multi-hop entity-aware retrieval
        memory_recall: List[Dict] = []
        try:
            from ...services.memory_engine import get_memory_engine
            mem = get_memory_engine()
            recall_results = await mem.recall(workspace_id, query, limit=limit_each)
            memory_recall = recall_results
        except Exception as exc:
            logger.warning(f"GraphRAG memory recall failed (non-fatal): {exc}")

        # 6. Community summaries — high-level workspace knowledge clusters
        community_context: List[Dict] = []
        try:
            from ...services.memory_engine import get_memory_engine
            mem = get_memory_engine()
            community_context = await mem.graph_rag.get_community_summaries(workspace_id)
        except Exception as exc:
            logger.warning(f"Community summaries failed (non-fatal): {exc}")

        return {
            "similar_decisions": similar_decisions,
            "recent_events": recent_events,
            "active_risks": active_risks,
            "past_adrs": past_adrs,
            "memory_recall": memory_recall,
            "community_context": community_context,
        }

    async def attach_evidence(
        self,
        decision_id: str,
        evidence: Dict[str, Any],
    ) -> bool:
        """Attach gathered evidence to an existing decision record."""
        try:
            self._client().table("decisions").update(
                {"evidence": evidence}
            ).eq("id", decision_id).execute()
            return True
        except Exception as exc:
            logger.warning(f"Evidence attachment failed: {exc}")
            return False

    def format_for_prompt(self, evidence: Dict[str, Any]) -> str:
        """
        Convert evidence dict into a prompt-friendly context block.

        Injects into the council engine prompt so models have workspace context.
        """
        sections = []

        # GraphRAG memory — most valuable, show first
        if evidence.get("memory_recall"):
            items = []
            for r in evidence["memory_recall"][:8]:
                source_tag = f"[{r.get('source', 'unknown')}]"
                entities_tag = ""
                if r.get("entities"):
                    entities_tag = f" (entities: {', '.join(r['entities'][:4])})"
                content = r.get("content", "")[:200]
                items.append(f"  • {source_tag}{entities_tag} {content}")
            sections.append(f"Workspace Memory (GraphRAG):\n" + "\n".join(items))

        # Community summaries — high-level architecture understanding
        if evidence.get("community_context"):
            items = []
            for c in evidence["community_context"][:5]:
                key_entities = ", ".join(c.get("key_entities", [])[:4])
                count = c.get("entity_count", 0)
                items.append(f"  • Cluster ({count} entities): {key_entities}")
            sections.append(f"Architecture Clusters:\n" + "\n".join(items))

        if evidence.get("similar_decisions"):
            items = "\n".join(
                f"  • {d.get('label', 'Unknown')} ({d.get('node_type', '')})"
                for d in evidence["similar_decisions"][:5]
            )
            sections.append(f"Similar past decisions:\n{items}")

        if evidence.get("active_risks"):
            items = "\n".join(
                f"  • [{r.get('severity', '?').upper()}] {r.get('description', '')}"
                for r in evidence["active_risks"][:5]
            )
            sections.append(f"Active unresolved risks:\n{items}")

        if evidence.get("past_adrs"):
            items = "\n".join(
                f"  • [{a.get('status', '?')}] {a.get('title', '')}"
                for a in evidence["past_adrs"][:5]
            )
            sections.append(f"Architecture Decision Records:\n{items}")

        return "\n\n".join(sections) if sections else ""


# Singleton
_evidence_manager: Optional[EvidenceManager] = None


def get_evidence_manager() -> EvidenceManager:
    global _evidence_manager
    if _evidence_manager is None:
        _evidence_manager = EvidenceManager()
    return _evidence_manager
