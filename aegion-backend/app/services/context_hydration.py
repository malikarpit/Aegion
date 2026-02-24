"""
Aegion Context Hydration Service.

Injects relevant governance context into new sessions so AI agents
and users start with awareness of current architectural state.

Doctrine: "Begin with understanding, not ignorance."
"""

from typing import List, Dict, Any, Optional
from .noesis.graph_service import GraphService
from ..ports.knowledge_graph import GraphNodeType
from ..core.logging import logger
from .repo_intelligence.service import RepoIntelligenceService


class ContextHydrationService:
    """
    Builds initial session context from the knowledge graph.

    When a new session starts, this service gathers:
    1. Top-ranked approved decisions for the workspace
    2. Active ADRs from governance records
    3. Recent sentinel alerts
    """

    def __init__(self, graph_service: GraphService, repo_service: Optional[RepoIntelligenceService] = None):
        self.graph = graph_service
        self.repo_service = repo_service

    async def hydrate_session_context(
        self,
        workspace_id: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Build initial context payload for a new session.

        Returns a dict with decisions, active ADRs, and sentinel alerts
        ranked by tier and recency.
        """
        # 1. Top-ranked approved decisions (highest tier, most recent first)
        decisions = await self._fetch_top_decisions(workspace_id, limit)

        # 2. Active ADRs (decisions that serve as architectural records)
        active_adrs = await self._fetch_active_adrs(workspace_id, limit)

        # 3. Recent sentinel alerts
        sentinel_alerts = await self._fetch_sentinel_alerts(workspace_id, limit=5)

        # 4. Recent commits / repo intelligence
        recent_commits = await self._fetch_recent_commits(workspace_id, limit=5)

        context = {
            "decisions": decisions,
            "active_adrs": active_adrs,
            "sentinel_alerts": sentinel_alerts,
            "recent_commits": recent_commits,
            "context_summary": (
                f"{len(decisions)} governing decisions, "
                f"{len(active_adrs)} active ADRs, "
                f"{len(sentinel_alerts)} sentinel alerts, "
                f"{len(recent_commits)} recent commits"
            ),
        }

        logger.info(
            f"Context hydration for workspace {workspace_id}: "
            f"{context['context_summary']}"
        )

        return context

    async def _fetch_top_decisions(
        self, workspace_id: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch approved decisions, ranked by tier desc + recency desc."""
        try:
            all_decisions = await self.graph.list_decisions(
                workspace_id=workspace_id,
                limit=limit * 2  # Over-fetch to filter
            )

            # Filter to approved only
            approved = [
                d for d in all_decisions
                if d.properties.get("status") == "approved"
                or d.properties.get("verdict") != "rejected"
            ]

            # Rank by tier (T3 > T2 > T1 > T0), then by decided_at desc
            tier_rank = {"T3": 4, "T2": 3, "T1": 2, "T0": 1}
            approved.sort(
                key=lambda d: (
                    tier_rank.get(d.properties.get("tier", "T0"), 0),
                    d.properties.get("decided_at", ""),
                ),
                reverse=True,
            )

            return [
                {
                    "decision_id": d.node_id,
                    "title": d.properties.get("title", ""),
                    "tier": d.properties.get("tier", "T0"),
                    "summary": d.properties.get("description", ""),
                    "decided_at": d.properties.get("decided_at", ""),
                }
                for d in approved[:limit]
            ]
        except Exception as e:
            logger.warning(f"Failed to fetch decisions for context: {e}")
            return []

    async def _fetch_active_adrs(
        self, workspace_id: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch accepted/active ADRs from the graph."""
        try:
            # ADRs are stored as decision nodes with "adr" label or status=accepted
            all_decisions = await self.graph.list_decisions(
                workspace_id=workspace_id,
                limit=limit * 2
            )

            adrs = [
                d for d in all_decisions
                if "adr" in d.labels
                or d.properties.get("adr_status") == "accepted"
            ]

            return [
                {
                    "adr_id": d.node_id,
                    "title": d.properties.get("title", ""),
                    "status": d.properties.get("adr_status", "accepted"),
                }
                for d in adrs[:limit]
            ]
        except Exception as e:
            logger.warning(f"Failed to fetch ADRs for context: {e}")
            return []

    async def _fetch_sentinel_alerts(
        self, workspace_id: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Fetch recent sentinel alerts from the graph."""
        try:
            alerts = await self.graph.search_nodes(
                query=f"workspace:{workspace_id}",
                node_type=GraphNodeType.SOURCE,  # Alerts stored under SOURCE type
                limit=limit
            )

            # Filter for alert-like nodes
            sentinel_alerts = [
                a for a in alerts
                if "alert" in a.labels or a.properties.get("alert_type")
            ]

            return [
                {
                    "alert_id": a.node_id,
                    "message": a.properties.get("message", ""),
                    "severity": a.properties.get("severity", "info"),
                }
                for a in sentinel_alerts[:limit]
            ]
        except Exception as e:
            logger.warning(f"Failed to fetch sentinel alerts for context: {e}")
            return []

    async def _fetch_recent_commits(
        self, workspace_id: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Fetch recent commits from repo intelligence service."""
        if not self.repo_service:
            return []

        try:
            commits = self.repo_service.get_recent_commits(limit=limit)
            return [
                {
                    "sha": c.sha[:8],
                    "message": c.message[:120],
                    "intent_type": c.intent_type,
                    "changed_files_count": len(c.changed_files),
                    "timestamp": c.timestamp.isoformat() if c.timestamp else "",
                }
                for c in commits
            ]
        except Exception as e:
            logger.warning(f"Failed to fetch recent commits for context: {e}")
            return []
