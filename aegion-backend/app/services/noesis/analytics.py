"""
Noesis Cognitive Analytics — Phase 24 (Elevated): Real Analytics Engine.

Provides deep analytics over council decision-making:

  1. Decision Quality Tracker — rubric scores over time, reversal rate, time-to-decide
  2. Cognitive Drift Detector — detects when reasoning patterns shift
  3. Consensus Evolution — tracks how consensus forms across decisions
  4. Governance Health Score — composite metric for workspace governance quality
  5. Model Performance Ranking — which models produce the best outputs

All backed by Supabase queries against real tables (decisions, reasoning_chains,
rejection_log, timeline_events, risk_signals).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from ...core.logging import logger


class CognitiveAnalytics:
    """
    Real analytics engine for council decision-making quality.

    Usage:
        analytics = CognitiveAnalytics()
        health = await analytics.governance_health(workspace_id)
        trends = await analytics.decision_quality_trends(workspace_id, days=30)
        drift = await analytics.cognitive_drift_report(workspace_id)
    """

    def _client(self):
        from ...db.supabase_client import get_supabase_client
        return get_supabase_client()

    # ══════════════════════════════════════════════
    # 1. Decision Quality Tracking
    # ══════════════════════════════════════════════

    async def decision_quality_trends(
        self,
        workspace_id: str,
        days: int = 30,
        bucket_size_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Track decision quality over time in weekly buckets.

        Returns:
            buckets:           List of time buckets with avg quality, count
            overall_avg:       Overall average quality
            trend_direction:   'improving', 'declining', 'stable'
            reversal_rate:     % of decisions later reversed
        """
        client = self._client()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            result = client.table("decisions").select(
                "id,created_at,evidence,verdict"
            ).eq("workspace_id", workspace_id).gte(
                "created_at", since
            ).order("created_at", desc=False).execute()

            decisions = result.data or []
        except Exception as exc:
            logger.warning(f"Decision quality query failed: {exc}")
            decisions = []

        if not decisions:
            return {
                "buckets": [],
                "overall_avg": 0.0,
                "trend_direction": "insufficient_data",
                "reversal_rate": 0.0,
                "total_decisions": 0,
            }

        # Bucket by time periods
        buckets = {}
        total_quality = 0.0
        reversal_count = 0

        for d in decisions:
            try:
                created = datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))
            except (ValueError, TypeError, KeyError):
                continue

            bucket_key = created.strftime("%Y-W%W")

            if bucket_key not in buckets:
                buckets[bucket_key] = {"count": 0, "quality_sum": 0.0, "period": bucket_key}

            # Extract quality from evidence if available
            evidence = d.get("evidence") or {}
            quality = 0.65  # Default if no rubric score
            if isinstance(evidence, dict):
                quality = evidence.get("rubric_score", evidence.get("quality", 0.65))

            buckets[bucket_key]["count"] += 1
            buckets[bucket_key]["quality_sum"] += quality
            total_quality += quality

            if d.get("verdict") == "reversed":
                reversal_count += 1

        # Compute averages
        bucket_list = []
        for key in sorted(buckets.keys()):
            b = buckets[key]
            avg = b["quality_sum"] / max(b["count"], 1)
            bucket_list.append({
                "period": b["period"],
                "decision_count": b["count"],
                "avg_quality": round(avg, 3),
            })

        # Trend detection
        trend = "stable"
        if len(bucket_list) >= 3:
            first_half_avg = sum(b["avg_quality"] for b in bucket_list[:len(bucket_list)//2]) / max(len(bucket_list)//2, 1)
            second_half_avg = sum(b["avg_quality"] for b in bucket_list[len(bucket_list)//2:]) / max(len(bucket_list) - len(bucket_list)//2, 1)
            if second_half_avg > first_half_avg + 0.05:
                trend = "improving"
            elif second_half_avg < first_half_avg - 0.05:
                trend = "declining"

        return {
            "buckets": bucket_list,
            "overall_avg": round(total_quality / max(len(decisions), 1), 3),
            "trend_direction": trend,
            "reversal_rate": round(reversal_count / max(len(decisions), 1), 3),
            "total_decisions": len(decisions),
        }

    # ══════════════════════════════════════════════
    # 2. Cognitive Drift Detection
    # ══════════════════════════════════════════════

    async def cognitive_drift_report(
        self,
        workspace_id: str,
        days: int = 60,
    ) -> Dict[str, Any]:
        """
        Detect if the council's reasoning patterns are drifting.

        Tracks:
          - Approval rate over time (is the council becoming rubber-stamp?)
          - Consensus scores over time (is the council converging too easily?)
          - Risk tolerance change (is the council accepting more risk?)
        """
        client = self._client()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            result = client.table("decisions").select(
                "created_at,verdict,evidence"
            ).eq("workspace_id", workspace_id).gte(
                "created_at", since
            ).order("created_at", desc=False).execute()
            decisions = result.data or []
        except Exception:
            decisions = []

        if len(decisions) < 6:
            return {
                "has_drift": False,
                "message": "Insufficient data (need 6+ decisions)",
                "approval_rate_trend": None,
                "consensus_trend": None,
                "risk_tolerance_trend": None,
            }

        mid = len(decisions) // 2
        first_half = decisions[:mid]
        second_half = decisions[mid:]

        # Approval rate drift
        first_approvals = sum(1 for d in first_half if d.get("verdict") in ("approved", "approve"))
        second_approvals = sum(1 for d in second_half if d.get("verdict") in ("approved", "approve"))
        first_rate = first_approvals / max(len(first_half), 1)
        second_rate = second_approvals / max(len(second_half), 1)
        approval_drift = second_rate - first_rate

        # Consensus drift
        def avg_consensus(decisions_list):
            scores = []
            for d in decisions_list:
                ev = d.get("evidence") or {}
                if isinstance(ev, dict) and "consensus_score" in ev:
                    scores.append(ev["consensus_score"])
            return sum(scores) / max(len(scores), 1) if scores else 0.5

        first_consensus = avg_consensus(first_half)
        second_consensus = avg_consensus(second_half)
        consensus_drift = second_consensus - first_consensus

        # Detect drift
        has_drift = abs(approval_drift) > 0.15 or abs(consensus_drift) > 0.10

        alerts = []
        if approval_drift > 0.15:
            alerts.append("⚠️ Approval rate increased significantly — possible rubber-stamping")
        if approval_drift < -0.15:
            alerts.append("⚠️ Approval rate decreased — council may be overly conservative")
        if consensus_drift > 0.10:
            alerts.append("⚠️ Consensus forming too easily — possible groupthink")

        return {
            "has_drift": has_drift,
            "approval_rate": {
                "first_half": round(first_rate, 3),
                "second_half": round(second_rate, 3),
                "delta": round(approval_drift, 3),
            },
            "consensus": {
                "first_half": round(first_consensus, 3),
                "second_half": round(second_consensus, 3),
                "delta": round(consensus_drift, 3),
            },
            "alerts": alerts,
            "decisions_analyzed": len(decisions),
        }

    # ══════════════════════════════════════════════
    # 3. Consensus Evolution
    # ══════════════════════════════════════════════

    async def consensus_evolution(
        self,
        workspace_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Track how consensus scores evolve across decisions."""
        client = self._client()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            result = client.table("decisions").select(
                "id,created_at,evidence,verdict"
            ).eq("workspace_id", workspace_id).gte(
                "created_at", since
            ).order("created_at", desc=False).execute()
            decisions = result.data or []
        except Exception:
            decisions = []

        data_points = []
        for d in decisions:
            ev = d.get("evidence") or {}
            if isinstance(ev, dict) and "consensus_score" in ev:
                data_points.append({
                    "decision_id": d["id"],
                    "created_at": d.get("created_at"),
                    "consensus_score": ev["consensus_score"],
                    "verdict": d.get("verdict"),
                })

        avg = sum(p["consensus_score"] for p in data_points) / max(len(data_points), 1) if data_points else 0
        high_consensus = [p for p in data_points if p["consensus_score"] > 0.8]
        low_consensus = [p for p in data_points if p["consensus_score"] < 0.5]

        return {
            "data_points": data_points,
            "average_consensus": round(avg, 3),
            "high_consensus_count": len(high_consensus),
            "low_consensus_count": len(low_consensus),
            "total": len(data_points),
        }

    # ══════════════════════════════════════════════
    # 4. Governance Health Score
    # ══════════════════════════════════════════════

    async def governance_health(
        self,
        workspace_id: str,
    ) -> Dict[str, Any]:
        """
        Composite governance health metric.

        Score = weighted average of:
          - Decision throughput (are decisions being made?)          × 0.20
          - Decision quality (rubric scores)                        × 0.30
          - Consensus quality (not too high, not too low)            × 0.20
          - Low reversal rate                                       × 0.15
          - Risk coverage (are risks being addressed?)              × 0.15

        Score range: 0.0 (broken governance) to 1.0 (excellent governance)
        """
        quality = await self.decision_quality_trends(workspace_id, days=30)
        drift = await self.cognitive_drift_report(workspace_id, days=30)
        consensus = await self.consensus_evolution(workspace_id, days=30)

        # Throughput score: 0.5 base + bonus for activity
        throughput = min(1.0, 0.3 + quality["total_decisions"] * 0.07)

        # Quality score: direct from rubric averages
        quality_score = quality["overall_avg"]

        # Consensus score: penalize both extremes (groupthink and gridlock)
        avg_c = consensus["average_consensus"]
        if avg_c > 0.9:
            consensus_score = 0.6  # Too easy — possible groupthink
        elif avg_c < 0.4:
            consensus_score = 0.5  # Gridlock
        else:
            consensus_score = min(1.0, avg_c + 0.2)  # Sweet spot: 0.5-0.85

        # Reversal score: low reversal = good
        reversal_score = max(0.0, 1.0 - quality["reversal_rate"] * 3)

        # Risk coverage: check if risks are being resolved
        risk_score = await self._risk_coverage_score(workspace_id)

        # Composite
        health = (
            throughput * 0.20 +
            quality_score * 0.30 +
            consensus_score * 0.20 +
            reversal_score * 0.15 +
            risk_score * 0.15
        )

        grade = "A" if health > 0.85 else "B" if health > 0.70 else "C" if health > 0.55 else "D" if health > 0.40 else "F"

        return {
            "health_score": round(health, 3),
            "grade": grade,
            "components": {
                "throughput": round(throughput, 3),
                "decision_quality": round(quality_score, 3),
                "consensus_quality": round(consensus_score, 3),
                "reversal_rate": round(reversal_score, 3),
                "risk_coverage": round(risk_score, 3),
            },
            "drift_alerts": drift.get("alerts", []),
            "total_decisions_30d": quality["total_decisions"],
            "quality_trend": quality["trend_direction"],
        }

    async def _risk_coverage_score(self, workspace_id: str) -> float:
        """Score based on ratio of resolved to total risks."""
        try:
            total = self._client().table("risk_signals").select(
                "id", count="exact"
            ).eq("workspace_id", workspace_id).execute()
            resolved = self._client().table("risk_signals").select(
                "id", count="exact"
            ).eq("workspace_id", workspace_id).eq("resolved", True).execute()

            total_count = total.count or 0
            resolved_count = resolved.count or 0

            if total_count == 0:
                return 0.7  # No risks = decent but not perfect

            return min(1.0, resolved_count / max(total_count, 1))
        except Exception:
            return 0.5

    # ══════════════════════════════════════════════
    # 5. Model Performance Ranking
    # ══════════════════════════════════════════════

    async def model_performance_ranking(
        self,
        workspace_id: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Rank models by output quality and cost-effectiveness.

        Uses rubric scores from decisions to determine which models
        produce the highest quality outputs.
        """
        client = self._client()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            result = client.table("decisions").select(
                "evidence"
            ).eq("workspace_id", workspace_id).gte(
                "created_at", since
            ).execute()
            decisions = result.data or []
        except Exception:
            decisions = []

        model_stats: Dict[str, Dict] = {}

        for d in decisions:
            ev = d.get("evidence") or {}
            if not isinstance(ev, dict):
                continue

            models_used = ev.get("models_used", [])
            quality = ev.get("rubric_score", ev.get("quality", 0.65))
            cost = ev.get("total_cost_usd", 0.0)

            for model in models_used:
                if model not in model_stats:
                    model_stats[model] = {
                        "model": model,
                        "uses": 0,
                        "quality_sum": 0.0,
                        "cost_sum": 0.0,
                    }
                model_stats[model]["uses"] += 1
                model_stats[model]["quality_sum"] += quality
                model_stats[model]["cost_sum"] += cost

        ranking = []
        for model, stats in model_stats.items():
            avg_quality = stats["quality_sum"] / max(stats["uses"], 1)
            avg_cost = stats["cost_sum"] / max(stats["uses"], 1)
            # Cost-effectiveness: quality per dollar
            cost_effectiveness = avg_quality / max(avg_cost, 0.0001)

            ranking.append({
                "model": model,
                "uses": stats["uses"],
                "avg_quality": round(avg_quality, 3),
                "avg_cost_usd": round(avg_cost, 4),
                "cost_effectiveness": round(cost_effectiveness, 1),
            })

        ranking.sort(key=lambda x: x["avg_quality"], reverse=True)
        return ranking


# Singleton
_analytics: Optional[CognitiveAnalytics] = None


def get_cognitive_analytics() -> CognitiveAnalytics:
    global _analytics
    if _analytics is None:
        _analytics = CognitiveAnalytics()
    return _analytics
