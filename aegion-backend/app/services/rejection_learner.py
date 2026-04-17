"""
Rejection Learner — Preference Learning from Human Rejection Signals.

Reference: Christiano et al., 2017 — "Deep Reinforcement Learning from Human Preferences"

Records rejection events when a user rejects a proposal, and applies a
confidence penalty to future queries that are semantically similar to
previously-rejected queries.

Mechanism:
    1. On rejection: hash query words → store (hash, reason, timestamp, workspace)
    2. On future query: compute Jaccard similarity to all past rejections
       → penalty = BASE_PENALTY × max_similarity (capped at MAX_PENALTY)
    3. Analytics: rejection rate over time, top reasons, daily counts
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set


class RejectionLearner:
    """
    Learn from human rejection signals to reduce repeated poor suggestions.

    Usage:
        learner = RejectionLearner()

        # When user rejects a proposal:
        learner.record_rejection(query, reason="Irrelevant suggestion", workspace_id="ws1")

        # When generating a new response:
        penalty = learner.get_penalty(new_query)
        adjusted_confidence = raw_confidence - penalty

        # Analytics:
        trends = learner.get_trends("ws1", days=30)
    """

    BASE_PENALTY: float = 0.15
    MAX_PENALTY: float = 0.30

    def __init__(self) -> None:
        self._log: List[Dict[str, Any]] = []

    # ── Recording ───────────────────────────────────────────────────────

    def record_rejection(
        self,
        query: str,
        reason: str,
        workspace_id: str,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Record a rejection event.

        Args:
            query:        The original query that was rejected.
            reason:       Human-provided reason for rejection.
            workspace_id: Workspace where the rejection occurred.
            timestamp:    Override timestamp (defaults to now UTC).

        Returns:
            The rejection log entry.
        """
        entry = {
            "query_hash": self._hash_query(query),
            "query_text": query[:200],
            "reason": reason,
            "workspace_id": workspace_id,
            "timestamp": timestamp or datetime.now(timezone.utc),
        }
        self._log.append(entry)
        return entry

    # ── Penalty Calculation ─────────────────────────────────────────────

    def get_penalty(self, query: str, workspace_id: Optional[str] = None) -> float:
        """
        Compute a confidence penalty based on similarity to past rejections.

        Uses Jaccard similarity between the query's word set and
        previously-rejected query word sets.

        Args:
            query:        New query to check.
            workspace_id: If set, only consider rejections from this workspace.

        Returns:
            Float in [0.0, MAX_PENALTY]. Higher = more similar to past rejections.
        """
        query_words = self._hash_query(query)
        if not query_words or not self._log:
            return 0.0

        max_sim = 0.0
        for entry in self._log:
            if workspace_id and entry["workspace_id"] != workspace_id:
                continue
            past_words = entry["query_hash"]
            intersection = len(query_words & past_words)
            union = len(query_words | past_words)
            if union > 0:
                sim = intersection / union
                max_sim = max(max_sim, sim)

        return min(self.BASE_PENALTY * max_sim, self.MAX_PENALTY)

    # ── Analytics ───────────────────────────────────────────────────────

    def get_trends(
        self,
        workspace_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get rejection trends for a workspace.

        Returns:
            {
                "total_rejections": int,
                "top_reasons": [(reason, count), ...],
                "daily_counts": {date_str: count, ...},
            }
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = [
            e for e in self._log
            if e["workspace_id"] == workspace_id
            and e["timestamp"] > cutoff
        ]

        reasons = Counter(e["reason"] for e in recent)

        # Group by date
        daily: Dict[str, int] = {}
        for e in recent:
            day = e["timestamp"].strftime("%Y-%m-%d")
            daily[day] = daily.get(day, 0) + 1

        return {
            "total_rejections": len(recent),
            "top_reasons": reasons.most_common(5),
            "daily_counts": daily,
        }

    def get_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent rejection log entries."""
        return self._log[-limit:]

    def clear(self, workspace_id: Optional[str] = None) -> int:
        """Clear rejection log (all or per-workspace). Returns count removed."""
        if workspace_id:
            before = len(self._log)
            self._log = [e for e in self._log if e["workspace_id"] != workspace_id]
            return before - len(self._log)
        else:
            count = len(self._log)
            self._log.clear()
            return count

    # ── Internal ────────────────────────────────────────────────────────

    @staticmethod
    def _hash_query(query: str) -> Set[str]:
        """Convert query to a set of lowercase non-trivial words."""
        words = query.lower().split()
        # Filter very short words (< 3 chars)
        return {w for w in words if len(w) >= 3}


# ─── Singleton ──────────────────────────────────────────────────────

_rejection_learner: Optional[RejectionLearner] = None


def get_rejection_learner() -> RejectionLearner:
    """Get or create the rejection learner singleton."""
    global _rejection_learner
    if _rejection_learner is None:
        _rejection_learner = RejectionLearner()
    return _rejection_learner
"""
Rejection Learner — Preference Learning from Human Rejection Signals.

Reference: Christiano et al., 2017 — "Deep Reinforcement Learning from Human Preferences"
"""
