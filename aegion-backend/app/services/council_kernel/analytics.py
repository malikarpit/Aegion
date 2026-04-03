"""
Council Analytics Engine — Phase 51: Council-Specific Performance Metrics.

Distinct from Noesis CognitiveAnalytics (which covers generic governance health).
This module tracks council-specific reasoning quality:

  1. Hallucination Rate   — % of consultations where red team found hallucinations
  2. Dissent Preservation — are minority opinions being kept?
  3. Decision Regret      — decisions later reversed correlate with consensus score
  4. Model Accuracy       — which models perform best for which task types
  5. Cost Efficiency      — cascade savings over time, ROI tracking

Uses council_findings table (new) + decisions + cost_tracking tables.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from ...core.logging import logger


class CouncilAnalytics:
    """
    Council-specific analytics for reasoning quality.

    Usage:
        analytics = CouncilAnalytics()
        rate = await analytics.hallucination_rate("ws-123", days=30)
        dissent = await analytics.dissent_preservation_score("ws-123")
        regret = await analytics.decision_regret_analysis("ws-123")
    """

    def _client(self):
        from ...db.supabase_client import get_supabase_client
        return get_supabase_client()

    # ══════════════════════════════════════════════
    # 1. Hallucination Rate Tracker
    # ══════════════════════════════════════════════

    async def hallucination_rate(
        self,
        workspace_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Track hallucination rate over time.

        Queries the council_findings table for red team hallucination findings.
        Returns:
            rate:           % of consultations with hallucination findings
            total_checks:   Number of red team validations run
            hallucinations: Number of validations with hallucination findings
            trend:          'improving', 'worsening', 'stable'
            by_model:       Dict of model → hallucination count
        """
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            result = self._client().table("council_findings").select(
                "id,workspace_id,attack_vector,severity,model_used,created_at"
            ).eq("workspace_id", workspace_id).gte(
                "created_at", since
            ).execute()

            findings = result.data or []
        except Exception as exc:
            logger.debug(f"Council findings query failed: {exc}")
            findings = []

        # Total unique red team runs (grouped by created_at rounded to minute)
        run_timestamps = set()
        hallucination_timestamps = set()
        model_hallucinations: Dict[str, int] = {}

        for f in findings:
            ts = f.get("created_at", "")[:16]  # Round to minute
            run_timestamps.add(ts)

            if f.get("attack_vector") == "hallucination":
                hallucination_timestamps.add(ts)
                model = f.get("model_used", "unknown")
                model_hallucinations[model] = model_hallucinations.get(model, 0) + 1

        total_checks = max(len(run_timestamps), 1)
        hallucination_count = len(hallucination_timestamps)
        rate = hallucination_count / total_checks

        # Trend: split findings by time
        mid_date = (datetime.now(timezone.utc) - timedelta(days=days // 2)).isoformat()
        first_half = [f for f in findings if f.get("created_at", "") < mid_date and f.get("attack_vector") == "hallucination"]
        second_half = [f for f in findings if f.get("created_at", "") >= mid_date and f.get("attack_vector") == "hallucination"]

        if len(first_half) + len(second_half) < 4:
            trend = "insufficient_data"
        elif len(second_half) < len(first_half) * 0.7:
            trend = "improving"
        elif len(second_half) > len(first_half) * 1.3:
            trend = "worsening"
        else:
            trend = "stable"

        return {
            "rate": round(rate, 3),
            "total_checks": total_checks,
            "hallucination_count": hallucination_count,
            "trend": trend,
            "by_model": model_hallucinations,
            "period_days": days,
        }

    # ══════════════════════════════════════════════
    # 2. Dissent Preservation Score
    # ══════════════════════════════════════════════

    async def dissent_preservation_score(
        self,
        workspace_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Track whether the council preserves minority/dissenting opinions.

        High dissent preservation = healthy debate culture.
        Low dissent preservation = possible groupthink.

        Returns:
            score:              0.0 (never) to 1.0 (always preserves dissent)
            total_decisions:    Number of decisions analyzed
            decisions_with_dissent: Count where dissenting_views > 0
            avg_consensus:      Average consensus score
        """
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            result = self._client().table("decisions").select(
                "evidence,verdict"
            ).eq("workspace_id", workspace_id).gte(
                "created_at", since
            ).execute()

            decisions = result.data or []
        except Exception:
            decisions = []

        if not decisions:
            return {
                "score": 0.0,
                "total_decisions": 0,
                "decisions_with_dissent": 0,
                "avg_consensus": 0.0,
                "health": "insufficient_data",
            }

        dissent_count = 0
        consensus_scores = []

        for d in decisions:
            ev = d.get("evidence") or {}
            if isinstance(ev, dict):
                views = ev.get("dissenting_views", [])
                if views and len(views) > 0:
                    dissent_count += 1
                cs = ev.get("consensus_score")
                if cs is not None:
                    consensus_scores.append(float(cs))

        total = len(decisions)
        score = dissent_count / max(total, 1)
        avg_consensus = sum(consensus_scores) / max(len(consensus_scores), 1) if consensus_scores else 0.0

        # Health assessment
        if score > 0.3 and avg_consensus < 0.9:
            health = "healthy"  # Good dissent + not rubber-stamping
        elif score < 0.1:
            health = "warning_low_dissent"  # Possible groupthink
        elif avg_consensus > 0.95:
            health = "warning_rubber_stamping"  # Too much agreement
        else:
            health = "moderate"

        return {
            "score": round(score, 3),
            "total_decisions": total,
            "decisions_with_dissent": dissent_count,
            "avg_consensus": round(avg_consensus, 3),
            "health": health,
        }

    # ══════════════════════════════════════════════
    # 3. Decision Regret Analysis
    # ══════════════════════════════════════════════

    async def decision_regret_analysis(
        self,
        workspace_id: str,
        days: int = 60,
    ) -> Dict[str, Any]:
        """
        Track decisions later reversed/superseded and correlate with consensus score.

        Low consensus decisions that get reversed = council "knew" it was wrong.
        High consensus decisions that get reversed = systemic issue.

        Returns:
            regret_rate:          % of decisions later reversed
            high_consensus_regret: Reversals where original consensus > 0.7
            low_consensus_regret:  Reversals where original consensus < 0.5
            pattern:              Analysis summary
        """
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            result = self._client().table("decisions").select(
                "id,verdict,evidence,created_at"
            ).eq("workspace_id", workspace_id).gte(
                "created_at", since
            ).execute()

            decisions = result.data or []
        except Exception:
            decisions = []

        if len(decisions) < 3:
            return {
                "regret_rate": 0.0,
                "total_decisions": len(decisions),
                "reversals": 0,
                "high_consensus_regret": 0,
                "low_consensus_regret": 0,
                "pattern": "Insufficient data for regret analysis",
            }

        reversed_decisions = [d for d in decisions if d.get("verdict") in ("reversed", "superseded")]
        reversal_count = len(reversed_decisions)
        regret_rate = reversal_count / max(len(decisions), 1)

        # Correlate with consensus
        high_consensus_regret = 0
        low_consensus_regret = 0

        for d in reversed_decisions:
            ev = d.get("evidence") or {}
            cs = ev.get("consensus_score", 0.5) if isinstance(ev, dict) else 0.5
            if cs > 0.7:
                high_consensus_regret += 1
            elif cs < 0.5:
                low_consensus_regret += 1

        # Pattern analysis
        if high_consensus_regret > low_consensus_regret and high_consensus_regret > 0:
            pattern = "⚠️ High-consensus decisions are being reversed — possible systemic groupthink bias"
        elif low_consensus_regret > 0:
            pattern = "Low-consensus decisions are being reversed — council is correctly identifying uncertain decisions"
        elif reversal_count == 0:
            pattern = "No reversals detected — either decisions are solid or outcomes aren't being tracked"
        else:
            pattern = "Mixed pattern — no clear correlation between consensus and reversals"

        return {
            "regret_rate": round(regret_rate, 3),
            "total_decisions": len(decisions),
            "reversals": reversal_count,
            "high_consensus_regret": high_consensus_regret,
            "low_consensus_regret": low_consensus_regret,
            "pattern": pattern,
        }

    # ══════════════════════════════════════════════
    # 4. Model Accuracy by Task Type
    # ══════════════════════════════════════════════

    async def model_accuracy_by_task(
        self,
        workspace_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Which models perform best for which task types.

        Categorizes decisions into task types (security, architecture, cost, code_review)
        and ranks models by quality within each category.
        """
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            result = self._client().table("decisions").select(
                "title,evidence"
            ).eq("workspace_id", workspace_id).gte(
                "created_at", since
            ).execute()

            decisions = result.data or []
        except Exception:
            decisions = []

        # Task type classification
        task_categories = {
            "security": ["security", "vulnerability", "cve", "injection", "auth", "encrypt"],
            "architecture": ["architecture", "pattern", "design", "microservice", "monolith", "refactor"],
            "cost": ["cost", "budget", "pricing", "expensive", "cheaper", "optimize"],
            "code_review": ["code", "review", "bug", "fix", "test", "quality"],
            "infrastructure": ["deploy", "docker", "kubernetes", "ci/cd", "pipeline", "terraform"],
        }

        # model → task_type → {quality_sum, count}
        model_task_stats: Dict[str, Dict[str, Dict[str, float]]] = {}

        for d in decisions:
            ev = d.get("evidence") or {}
            if not isinstance(ev, dict):
                continue

            title = (d.get("title") or "").lower()
            models_used = ev.get("models_used", [])
            quality = ev.get("rubric_score", ev.get("quality", 0.65))

            # Classify the task
            task_type = "general"
            for cat, keywords in task_categories.items():
                if any(kw in title for kw in keywords):
                    task_type = cat
                    break

            for model in models_used:
                if model not in model_task_stats:
                    model_task_stats[model] = {}
                if task_type not in model_task_stats[model]:
                    model_task_stats[model][task_type] = {"quality_sum": 0.0, "count": 0}
                model_task_stats[model][task_type]["quality_sum"] += quality
                model_task_stats[model][task_type]["count"] += 1

        # Build rankings per task type
        rankings: Dict[str, List[Dict]] = {}
        for model, tasks in model_task_stats.items():
            for task_type, stats in tasks.items():
                avg = stats["quality_sum"] / max(stats["count"], 1)
                if task_type not in rankings:
                    rankings[task_type] = []
                rankings[task_type].append({
                    "model": model,
                    "avg_quality": round(avg, 3),
                    "uses": stats["count"],
                })

        # Sort each ranking
        for task_type in rankings:
            rankings[task_type].sort(key=lambda x: x["avg_quality"], reverse=True)

        return {
            "rankings": rankings,
            "total_decisions": len(decisions),
            "task_types_found": list(rankings.keys()),
        }

    # ══════════════════════════════════════════════
    # 5. Cost Efficiency Tracking
    # ══════════════════════════════════════════════

    async def cost_efficiency(
        self,
        workspace_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Track cascade cost savings over time.

        Compares actual cost vs estimated frontier cost to compute ROI.
        """
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            result = self._client().table("cost_tracking").select(
                "cost_usd,tokens_in,tokens_out,models,cache_hit,created_at"
            ).eq("workspace_id", workspace_id).gte(
                "created_at", since
            ).execute()

            records = result.data or []
        except Exception:
            records = []

        if not records:
            return {
                "total_actual_cost": 0.0,
                "total_frontier_estimate": 0.0,
                "total_savings": 0.0,
                "savings_percentage": 0.0,
                "cache_hit_rate": 0.0,
                "total_queries": 0,
                "avg_cost_per_query": 0.0,
            }

        total_cost = sum(r.get("cost_usd", 0) for r in records)
        total_tokens_in = sum(r.get("tokens_in", 0) for r in records)
        total_tokens_out = sum(r.get("tokens_out", 0) for r in records)
        cache_hits = sum(1 for r in records if r.get("cache_hit"))

        # Estimated frontier cost (GPT-4 pricing: $15/1M in, $75/1M out)
        frontier_estimate = (total_tokens_in * 15.0 + total_tokens_out * 75.0) / 1_000_000

        savings = max(0, frontier_estimate - total_cost)
        savings_pct = (savings / max(frontier_estimate, 0.001)) * 100

        # Weekly breakdown
        weekly_costs: Dict[str, float] = {}
        for r in records:
            week = r.get("created_at", "")[:10]
            if week:
                weekly_costs[week] = weekly_costs.get(week, 0) + r.get("cost_usd", 0)

        return {
            "total_actual_cost": round(total_cost, 4),
            "total_frontier_estimate": round(frontier_estimate, 4),
            "total_savings": round(savings, 4),
            "savings_percentage": round(savings_pct, 1),
            "cache_hit_rate": round(cache_hits / max(len(records), 1), 3),
            "total_queries": len(records),
            "avg_cost_per_query": round(total_cost / max(len(records), 1), 6),
            "daily_breakdown": dict(sorted(weekly_costs.items())),
        }

    # ══════════════════════════════════════════════
    # Persist red team findings (called from engine)
    # ══════════════════════════════════════════════

    async def persist_findings(
        self,
        workspace_id: str,
        findings: list,
        model_used: str = "unknown",
    ) -> None:
        """Store red team findings for analytics tracking."""
        try:
            rows = [
                {
                    "workspace_id": workspace_id,
                    "attack_vector": f.attack_vector,
                    "severity": f.severity,
                    "description": f.description[:500],
                    "model_used": model_used,
                }
                for f in findings
            ]
            if rows:
                self._client().table("council_findings").insert(rows).execute()
        except Exception as exc:
            logger.debug(f"Failed to persist council findings: {exc}")


# Singleton
_council_analytics: Optional[CouncilAnalytics] = None


def get_council_analytics() -> CouncilAnalytics:
    global _council_analytics
    if _council_analytics is None:
        _council_analytics = CouncilAnalytics()
    return _council_analytics
