"""
Rules Engine — Phase 29: Configurable Governance Rules.

Evaluates workspace-specific business rules against proposal context.
Rules are stored in Supabase and evaluated in priority order.

Rule format:
  {
    "name": "block-direct-db-access",
    "condition": {"signal_type": "security", "severity": "high"},
    "action": "block",
    "priority": 100,
    "enabled": true
  }
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.logging import logger


class RulesEngine:
    """
    Workspace-configurable rules engine.

    Rules are stored in the `rules` table. Each rule has:
      - condition: dict of key-value pairs to match
      - action:    "block", "escalate", "warn", "allow"
      - priority:  higher = evaluated first
    """

    def _client(self):
        from ..db.supabase_client import get_supabase_client
        return get_supabase_client()

    async def evaluate(
        self,
        workspace_id: str,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all enabled rules for a workspace against the given context.

        Returns list of triggered rules with their actions.
        """
        try:
            result = (
                self._client()
                .table("rules")
                .select("*")
                .eq("workspace_id", workspace_id)
                .eq("enabled", True)
                .order("priority", desc=True)
                .execute()
            )
            rules = result.data or []
        except Exception as exc:
            logger.warning(f"Rules fetch failed: {exc}")
            return []

        triggered = []
        for rule in rules:
            condition = rule.get("condition", {})
            if self._matches(condition, context):
                triggered.append({
                    "rule_id": rule["id"],
                    "rule_name": rule.get("name", "unnamed"),
                    "action": rule.get("action", "warn"),
                    "priority": rule.get("priority", 0),
                    "condition": condition,
                })

        return triggered

    def _matches(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check if all condition key-value pairs match in context."""
        for key, expected in condition.items():
            actual = context.get(key)
            if actual is None:
                return False
            # Support basic operators
            if isinstance(expected, dict):
                if "$gt" in expected and not (actual > expected["$gt"]):
                    return False
                if "$lt" in expected and not (actual < expected["$lt"]):
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$contains" in expected and expected["$contains"] not in str(actual):
                    return False
            elif actual != expected:
                return False
        return True


# Singleton
_rules_engine: Optional[RulesEngine] = None

def get_rules_engine() -> RulesEngine:
    global _rules_engine
    if _rules_engine is None:
        _rules_engine = RulesEngine()
    return _rules_engine
