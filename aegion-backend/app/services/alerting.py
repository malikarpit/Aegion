"""
Aegion Alerting Engine — Phase 74 (Elevated): Real-Time Alert Evaluation.

Evaluates alert rules against workspace metrics and triggers notifications.

Alert channels:
  - Webhook (POST to URL)
  - Log (structured logger)
  - Supabase table (persisted for dashboard)

Built-in alert rules:
  - High API error rate (>10% over 5min)
  - Council cascade exhaustion (all tiers failed)
  - Budget threshold exceeded (>80% of monthly budget)
  - Sentinel critical risk (risk_score >= 0.9)
  - Governance health degraded (grade F or D)
  - Cognitive drift detected
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from ..core.logging import logger


class AlertSeverity:
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertRule:
    """A single alert rule definition."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        severity: str,
        description: str,
        check_fn_name: str,
        cooldown_minutes: int = 15,
    ):
        self.rule_id = rule_id
        self.name = name
        self.severity = severity
        self.description = description
        self.check_fn_name = check_fn_name
        self.cooldown_minutes = cooldown_minutes
        self.last_fired: Optional[datetime] = None


# Built-in alert rules
_ALERT_RULES: Dict[str, AlertRule] = {
    "high_error_rate": AlertRule(
        "high_error_rate", "High API Error Rate",
        AlertSeverity.WARNING,
        "API error rate exceeded 10% in the last 5 minutes",
        "check_error_rate",
    ),
    "cascade_exhaustion": AlertRule(
        "cascade_exhaustion", "Council Cascade Exhausted",
        AlertSeverity.CRITICAL,
        "All LLM cascade tiers failed — no model could serve the request",
        "check_cascade_exhaustion",
    ),
    "budget_exceeded": AlertRule(
        "budget_exceeded", "Budget Threshold Exceeded",
        AlertSeverity.WARNING,
        "Workspace has used >80% of its monthly LLM budget",
        "check_budget_threshold",
    ),
    "sentinel_critical": AlertRule(
        "sentinel_critical", "Sentinel Critical Risk",
        AlertSeverity.CRITICAL,
        "Risk score >= 0.9 detected by Sentinel",
        "check_sentinel_critical",
    ),
    "governance_degraded": AlertRule(
        "governance_degraded", "Governance Health Degraded",
        AlertSeverity.WARNING,
        "Governance health score dropped to D or F grade",
        "check_governance_health",
    ),
    "cognitive_drift": AlertRule(
        "cognitive_drift", "Cognitive Drift Detected",
        AlertSeverity.INFO,
        "Council reasoning patterns have shifted significantly",
        "check_cognitive_drift",
    ),
}


class AlertingEngine:
    """
    Evaluates alert rules and dispatches notifications.

    Usage:
        engine = AlertingEngine()
        alerts = await engine.evaluate_all("ws-123")
        active = await engine.get_active_alerts("ws-123")
    """

    def _client(self):
        from ..db.supabase_client import get_supabase_client
        return get_supabase_client()

    async def evaluate_all(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Evaluate all alert rules for a workspace. Returns fired alerts."""
        fired = []

        for rule_id, rule in _ALERT_RULES.items():
            # Cooldown check
            if rule.last_fired:
                elapsed = (datetime.now(timezone.utc) - rule.last_fired).total_seconds()
                if elapsed < rule.cooldown_minutes * 60:
                    continue

            # Run the check
            try:
                check_fn = getattr(self, f"_{rule.check_fn_name}", None)
                if check_fn is None:
                    continue

                triggered, details = await check_fn(workspace_id)
                if triggered:
                    alert = {
                        "rule_id": rule_id,
                        "name": rule.name,
                        "severity": rule.severity,
                        "description": rule.description,
                        "details": details,
                        "workspace_id": workspace_id,
                        "fired_at": datetime.now(timezone.utc).isoformat(),
                    }
                    fired.append(alert)
                    rule.last_fired = datetime.now(timezone.utc)

                    # Persist
                    self._persist_alert(alert)

                    # Log
                    log_fn = logger.critical if rule.severity == AlertSeverity.CRITICAL else logger.warning
                    log_fn(f"🚨 Alert [{rule.severity.upper()}] {rule.name}: {details}")

            except Exception as exc:
                logger.warning(f"Alert rule {rule_id} evaluation failed: {exc}")

        return fired

    async def get_active_alerts(
        self,
        workspace_id: str,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get alerts fired in the last N hours."""
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        try:
            result = (
                self._client()
                .table("alerts")
                .select("*")
                .eq("workspace_id", workspace_id)
                .gte("fired_at", since)
                .order("fired_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception:
            return []

    async def acknowledge_alert(self, alert_id: str, actor_id: str) -> bool:
        """Acknowledge an alert to clear it."""
        try:
            self._client().table("alerts").update({
                "acknowledged": True,
                "acknowledged_by": actor_id,
                "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", alert_id).execute()
            return True
        except Exception:
            return False

    # ──────────────────────────────────────────────
    # Check implementations
    # ──────────────────────────────────────────────

    async def _check_error_rate(self, workspace_id: str):
        """Check if API error rate exceeds threshold."""
        try:
            since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            total = self._client().table("timeline_events").select(
                "id", count="exact"
            ).eq("workspace_id", workspace_id).gte(
                "timestamp", since
            ).execute()

            errors = self._client().table("timeline_events").select(
                "id", count="exact"
            ).eq("workspace_id", workspace_id).eq(
                "event_type", "error"
            ).gte("timestamp", since).execute()

            total_count = total.count or 0
            error_count = errors.count or 0

            if total_count < 10:  # Not enough data
                return False, {}

            error_rate = error_count / total_count
            return error_rate > 0.10, {
                "error_rate": round(error_rate, 3),
                "errors": error_count,
                "total": total_count,
            }
        except Exception:
            return False, {}

    async def _check_cascade_exhaustion(self, workspace_id: str):
        """Check for cascade exhaustion events."""
        try:
            since = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
            result = self._client().table("timeline_events").select(
                "id", count="exact"
            ).eq("workspace_id", workspace_id).eq(
                "event_type", "cascade_exhausted"
            ).gte("timestamp", since).execute()

            count = result.count or 0
            return count > 0, {"exhaustion_count": count}
        except Exception:
            return False, {}

    async def _check_budget_threshold(self, workspace_id: str):
        """Check if LLM spend is approaching budget."""
        try:
            result = self._client().table("cost_tracking").select(
                "total_cost_usd, monthly_budget_usd"
            ).eq("workspace_id", workspace_id).single().execute()

            if result.data:
                spent = result.data.get("total_cost_usd", 0)
                budget = result.data.get("monthly_budget_usd", 100)
                usage_pct = spent / max(budget, 0.01)
                return usage_pct > 0.80, {
                    "spent_usd": round(spent, 2),
                    "budget_usd": budget,
                    "usage_pct": round(usage_pct, 3),
                }
        except Exception:
            pass
        return False, {}

    async def _check_sentinel_critical(self, workspace_id: str):
        """Check for critical risk signals."""
        try:
            result = self._client().table("risk_signals").select(
                "description, severity"
            ).eq("workspace_id", workspace_id).eq(
                "severity", "critical"
            ).eq("resolved", False).execute()

            signals = result.data or []
            if signals:
                return True, {
                    "critical_risks": len(signals),
                    "descriptions": [s["description"][:100] for s in signals[:3]],
                }
        except Exception:
            pass
        return False, {}

    async def _check_governance_health(self, workspace_id: str):
        """Check governance health score."""
        try:
            from .noesis.analytics import get_cognitive_analytics
            analytics = get_cognitive_analytics()
            health = await analytics.governance_health(workspace_id)

            grade = health.get("grade", "C")
            if grade in ("D", "F"):
                return True, {
                    "grade": grade,
                    "score": health.get("health_score"),
                    "components": health.get("components"),
                }
        except Exception:
            pass
        return False, {}

    async def _check_cognitive_drift(self, workspace_id: str):
        """Check for cognitive drift."""
        try:
            from .noesis.analytics import get_cognitive_analytics
            analytics = get_cognitive_analytics()
            drift = await analytics.cognitive_drift_report(workspace_id, days=30)

            if drift.get("has_drift"):
                return True, {
                    "alerts": drift.get("alerts", []),
                    "approval_delta": drift.get("approval_rate", {}).get("delta"),
                }
        except Exception:
            pass
        return False, {}

    # ──────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────

    def _persist_alert(self, alert: Dict) -> None:
        try:
            self._client().table("alerts").insert(alert).execute()
        except Exception:
            pass


# Singleton
_alerting: Optional[AlertingEngine] = None


def get_alerting_engine() -> AlertingEngine:
    global _alerting
    if _alerting is None:
        _alerting = AlertingEngine()
    return _alerting
