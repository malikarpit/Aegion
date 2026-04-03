"""
Temporal Council Memory — Phase 49: Historical Decision Context.

"Last time we debated X, the outcome was Y."

Provides 3 capabilities:
  1. Decision Recall — find similar past decisions for context
  2. Outcome Tracking — correlate decisions with downstream results
  3. Pattern Learning — track council accuracy by decision type

Uses existing Supabase tables (decisions, timeline_events, risk_signals).
No new tables needed.

Gated by WorkspaceCouncilConfig.temporal_memory_enabled (default: off).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...core.logging import logger


@dataclass
class PastDecision:
    """A historical decision relevant to the current query."""
    decision_id: str
    title: str
    verdict: str
    consensus_score: float
    created_at: str
    relevance_score: float  # How similar to current query
    outcome: Optional[str] = None  # If we tracked the outcome
    outcome_quality: Optional[float] = None  # 0.0=bad, 1.0=good


@dataclass
class AccuracyReport:
    """Council accuracy for a specific decision type."""
    decision_type: str
    total_decisions: int
    outcomes_tracked: int
    avg_outcome_quality: float
    best_pattern: str  # What the council does well
    worst_pattern: str  # What the council does poorly
    recommendation: str  # Advice for current debate


class TemporalMemory:
    """
    Historical decision context for the council.

    Usage:
        memory = TemporalMemory(top_k=3, outcome_window_days=30)
        past = await memory.recall_similar_decisions("ws-123", "Should we migrate to Redis?")
        accuracy = await memory.get_council_accuracy("ws-123", "database")
    """

    def __init__(
        self,
        top_k: int = 3,
        outcome_window_days: int = 30,
    ):
        self.top_k = top_k
        self.outcome_window_days = outcome_window_days

    def _client(self):
        from ...db.supabase_client import get_supabase_client
        return get_supabase_client()

    async def recall_similar_decisions(
        self,
        workspace_id: str,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[PastDecision]:
        """
        Find the most similar past decisions for a given query.

        Uses keyword extraction + concept matching against the decisions table.
        """
        k = top_k or self.top_k

        try:
            # Get all decisions for this workspace
            result = self._client().table("decisions").select(
                "id,title,verdict,evidence,created_at"
            ).eq("workspace_id", workspace_id).order(
                "created_at", desc=True
            ).limit(100).execute()

            decisions = result.data or []
        except Exception as exc:
            logger.warning(f"Temporal memory recall failed: {exc}")
            return []

        if not decisions:
            return []

        # Extract concepts from query
        query_concepts = self._extract_concepts(query)

        # Score each past decision by relevance
        scored = []
        for d in decisions:
            title = d.get("title", "")
            title_concepts = self._extract_concepts(title)

            # Jaccard similarity on concept sets
            if not query_concepts or not title_concepts:
                relevance = 0.0
            else:
                intersection = len(query_concepts & title_concepts)
                union = len(query_concepts | title_concepts)
                relevance = intersection / max(union, 1)

            if relevance > 0.05:  # Minimum relevance threshold
                evidence = d.get("evidence") or {}
                consensus = evidence.get("consensus_score", 0.5) if isinstance(evidence, dict) else 0.5

                scored.append(PastDecision(
                    decision_id=d["id"],
                    title=title,
                    verdict=d.get("verdict", "unknown"),
                    consensus_score=consensus,
                    created_at=d.get("created_at", ""),
                    relevance_score=round(relevance, 3),
                ))

        # Sort by relevance, return top_k
        scored.sort(key=lambda x: x.relevance_score, reverse=True)

        # Enrich top results with outcome data
        top_results = scored[:k]
        for decision in top_results:
            outcome = await self._get_outcome(workspace_id, decision)
            if outcome:
                decision.outcome = outcome["description"]
                decision.outcome_quality = outcome["quality"]

        return top_results

    async def track_outcome(
        self,
        workspace_id: str,
        decision_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Check what happened after a decision was made.

        Looks at timeline_events and risk_signals in the window after the decision.
        """
        try:
            # Get the decision timestamp
            result = self._client().table("decisions").select(
                "created_at,verdict,title"
            ).eq("id", decision_id).single().execute()

            if not result.data:
                return None

            decision_time = result.data["created_at"]
            decision_dt = datetime.fromisoformat(decision_time.replace("Z", "+00:00"))
            window_end = (decision_dt + timedelta(days=self.outcome_window_days)).isoformat()

            # Look for related events after the decision
            events = self._client().table("timeline_events").select(
                "event_type,payload,timestamp"
            ).eq("workspace_id", workspace_id).gte(
                "timestamp", decision_time
            ).lte("timestamp", window_end).execute()

            event_data = events.data or []

            # Look for new risks after the decision
            risks = self._client().table("risk_signals").select(
                "severity,description,resolved"
            ).eq("workspace_id", workspace_id).gte(
                "created_at", decision_time
            ).lte("created_at", window_end).execute()

            risk_data = risks.data or []

            # Compute outcome quality
            quality = self._compute_outcome_quality(
                result.data["verdict"], event_data, risk_data
            )

            return {
                "decision_id": decision_id,
                "title": result.data.get("title"),
                "verdict": result.data.get("verdict"),
                "events_after": len(event_data),
                "risks_after": len(risk_data),
                "quality": quality,
                "description": self._describe_outcome(
                    result.data["verdict"], event_data, risk_data, quality
                ),
            }

        except Exception as exc:
            logger.warning(f"Outcome tracking failed: {exc}")
            return None

    async def get_council_accuracy(
        self,
        workspace_id: str,
        decision_type: Optional[str] = None,
    ) -> AccuracyReport:
        """
        Track council accuracy for a specific type of decision.

        Returns patterns about what the council gets right vs wrong.
        """
        try:
            query = self._client().table("decisions").select(
                "id,title,verdict,evidence,created_at"
            ).eq("workspace_id", workspace_id)

            result = query.order("created_at", desc=True).limit(50).execute()
            decisions = result.data or []
        except Exception:
            decisions = []

        if not decisions:
            return AccuracyReport(
                decision_type=decision_type or "all",
                total_decisions=0,
                outcomes_tracked=0,
                avg_outcome_quality=0.0,
                best_pattern="Insufficient data",
                worst_pattern="Insufficient data",
                recommendation="Need more decisions to analyze patterns.",
            )

        # Filter by type if specified
        if decision_type:
            type_concepts = self._extract_concepts(decision_type)
            decisions = [
                d for d in decisions
                if len(type_concepts & self._extract_concepts(d.get("title", ""))) > 0
            ]

        # Categorize by verdict and check outcomes
        approved = [d for d in decisions if d.get("verdict") in ("approved", "approve")]
        rejected = [d for d in decisions if d.get("verdict") in ("rejected", "reject")]

        approval_rate = len(approved) / max(len(decisions), 1)

        # Determine patterns
        best_pattern = "Council is well-calibrated" if 0.3 < approval_rate < 0.7 else (
            "Council approves most proposals" if approval_rate > 0.7 else
            "Council rejects most proposals"
        )

        worst_pattern = (
            "Council may be rubber-stamping" if approval_rate > 0.85 else
            "Council may be overly conservative" if approval_rate < 0.20 else
            "No concerning patterns detected"
        )

        recommendation = ""
        if approval_rate > 0.85:
            recommendation = "⚠️ Historically, the council approves most proposals. Apply extra scrutiny."
        elif approval_rate < 0.20:
            recommendation = "⚠️ Historically, the council rejects most proposals. Consider if this is too conservative."
        else:
            recommendation = "Council has a balanced approval rate. Historical patterns look healthy."

        return AccuracyReport(
            decision_type=decision_type or "all",
            total_decisions=len(decisions),
            outcomes_tracked=0,  # Will be filled when outcome tracking matures
            avg_outcome_quality=0.0,
            best_pattern=best_pattern,
            worst_pattern=worst_pattern,
            recommendation=recommendation,
        )

    def format_for_prompt(self, past_decisions: List[PastDecision]) -> str:
        """Format past decisions as a prompt block for the council."""
        if not past_decisions:
            return ""

        lines = ["HISTORICAL CONTEXT — Similar Past Decisions:"]
        for i, d in enumerate(past_decisions, 1):
            lines.append(f"  {i}. \"{d.title}\" → {d.verdict} (consensus: {d.consensus_score:.0%})")
            if d.outcome:
                lines.append(f"     Outcome: {d.outcome} (quality: {d.outcome_quality:.0%})")

        lines.append("")
        lines.append("Consider these past decisions when forming your position.")
        return "\n".join(lines)

    # ═══════════════════════════════════════════
    # Internal helpers
    # ═══════════════════════════════════════════

    def _extract_concepts(self, text: str) -> set:
        """
        Extract key concepts from text for similarity matching.

        E9: Extended with 2-gram extraction for compound technical terms.
        """
        import re as _re
        text_lower = text.lower()

        concepts = set()

        # Technology terms (single words)
        tech_terms = _re.findall(
            r'\b(?:redis|postgres(?:ql)?|mongodb|kafka|docker|kubernetes|k8s|graphql|'
            r'rest|grpc|fastapi|django|react|next\.?js|vue|angular|firebase|supabase|'
            r'aws|gcp|azure|s3|lambda|cloudrun|oauth|jwt|mTLS|websocket|sse|'
            r'microservice|monolith|cqrs|event.?sourc|saga|circuit.?break|'
            r'sentinel|archon|chronos|praxis|noesis|graphrag|pgvector|'
            r'sql|nosql|cache|index|migration|schema|api|endpoint|'
            r'security|auth|encrypt|ssl|tls|cors|csrf|xss|injection|'
            r'deploy|ci.?cd|pipeline|container|helm|terraform)\b',
            text_lower,
        )
        concepts.update(tech_terms)

        # PascalCase names
        pascal = _re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', text)
        concepts.update(w.lower() for w in pascal)

        # Action concepts
        actions = _re.findall(
            r'\b(migrat|replac|add|remov|upgrad|refactor|implement|integrat|deploy|'
            r'deprecat|adopt|switch)\w*\b',
            text_lower,
        )
        concepts.update(actions)

        # E9: 2-gram compound technical terms
        words = _re.findall(r'\b[a-z]{2,}\b', text_lower)
        compound_anchors = {
            "api", "rate", "circuit", "event", "load", "service",
            "data", "access", "cost", "model", "token", "cache",
            "query", "memory", "prompt", "council", "governance",
            "risk", "security", "auth", "user", "role", "key",
        }
        for i in range(len(words) - 1):
            if words[i] in compound_anchors or words[i + 1] in compound_anchors:
                bigram = f"{words[i]}_{words[i + 1]}"
                concepts.add(bigram)

        return concepts

    async def _get_outcome(
        self,
        workspace_id: str,
        decision: PastDecision,
    ) -> Optional[Dict]:
        """Get the outcome for a past decision if available."""
        try:
            decision_time = decision.created_at
            window_end = (
                datetime.fromisoformat(decision_time.replace("Z", "+00:00")) +
                timedelta(days=self.outcome_window_days)
            ).isoformat()

            # Check for negative signals (new risks after decision)
            risks = self._client().table("risk_signals").select(
                "severity", count="exact"
            ).eq("workspace_id", workspace_id).gte(
                "created_at", decision_time
            ).lte("created_at", window_end).execute()

            risk_count = risks.count or 0

            if risk_count == 0:
                return {"description": "No negative signals detected", "quality": 0.8}
            elif risk_count <= 2:
                return {"description": f"{risk_count} minor risks appeared", "quality": 0.6}
            else:
                return {"description": f"{risk_count} risks appeared after decision", "quality": 0.3}

        except Exception:
            return None

    def _compute_outcome_quality(
        self,
        verdict: str,
        events: List[Dict],
        risks: List[Dict],
    ) -> float:
        """Compute outcome quality from post-decision signals."""
        quality = 0.7  # Baseline

        # Risks after decision
        critical_risks = sum(1 for r in risks if r.get("severity") == "critical")
        high_risks = sum(1 for r in risks if r.get("severity") == "high")
        resolved_risks = sum(1 for r in risks if r.get("resolved"))

        quality -= critical_risks * 0.15
        quality -= high_risks * 0.08
        quality += resolved_risks * 0.05

        # Events suggesting success
        success_events = sum(
            1 for e in events
            if e.get("event_type") in ("deployment_completed", "proposal_approved")
        )
        error_events = sum(1 for e in events if e.get("event_type") == "error")

        quality += success_events * 0.05
        quality -= error_events * 0.08

        return max(0.0, min(1.0, round(quality, 3)))

    def _describe_outcome(
        self,
        verdict: str,
        events: List[Dict],
        risks: List[Dict],
        quality: float,
    ) -> str:
        """Generate a human-readable outcome description."""
        if quality > 0.75:
            return f"Decision ({verdict}) was followed by positive signals — appears to be a good call"
        elif quality > 0.50:
            return f"Decision ({verdict}) had mixed outcomes — some positive, some negative signals"
        else:
            return f"Decision ({verdict}) was followed by negative signals — the council may have erred"


# Factory
def create_temporal_memory(
    top_k: int = 3,
    outcome_window_days: int = 30,
) -> TemporalMemory:
    return TemporalMemory(top_k=top_k, outcome_window_days=outcome_window_days)
