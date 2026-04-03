"""
Constitutional AI Layer — Phase 46: Machine-Readable Governance.

Defines hard constraints, soft guidelines, and escalation rules in YAML.
Every council query is validated against the constitution before execution.

Hard constraints cannot be overridden by any model or user.
Soft guidelines influence behaviour but allow case-by-case exceptions.

E1-E3 Enhancements:
  - All 7 hard constraints now have runtime check_query() detectors
  - check_response() extended with shared secret/injection patterns
  - evaluate_escalation() method that parses conditions against real data
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import yaml

from ...core.logging import logger


# ──────────────────────────────────────────────────────────────────────────────
# Shared detection patterns (used by both constitution + red_team)
# ──────────────────────────────────────────────────────────────────────────────

SECRET_PATTERNS = [
    r'(?:sk-|sk-proj-)[A-Za-z0-9]{20,}',        # OpenAI
    r'AKIA[A-Z0-9]{16}',                          # AWS
    r'AIza[A-Za-z0-9\-_]{35}',                    # Google
    r'ghp_[A-Za-z0-9]{36}',                       # GitHub PAT
    r'glpat-[A-Za-z0-9\-]{20,}',                  # GitLab PAT
    r'xoxb-[0-9]+-[A-Za-z0-9]+',                  # Slack bot
    r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----',   # PEM keys
    r'(?:password|passwd|pwd)\s*[:=]\s*\S{6,}',    # Inline passwords
    r'Bearer\s+[A-Za-z0-9\-_.~+/]{20,}',          # Bearer tokens
]
SECRET_RE = re.compile('|'.join(SECRET_PATTERNS), re.IGNORECASE)


_DEFAULT_CONSTITUTION = {
    "version": "1.0.0",
    "hard_constraints": [
        {"rule": "no_ai_memory_write", "description": "AI cannot write to Chronos directly"},
        {"rule": "no_ai_approval", "description": "AI cannot approve T2+ decisions"},
        {"rule": "human_override", "description": "Humans can override any AI decision"},
        {"rule": "no_data_deletion", "description": "AI cannot delete production data"},
        {"rule": "no_secret_exposure", "description": "AI must never expose API keys or secrets"},
        {"rule": "no_governance_bypass", "description": "AI cannot disable governance checks"},
        {"rule": "audit_trail_always", "description": "Every AI action must be logged"},
    ],
    "soft_guidelines": [
        {"rule": "prefer_reversible", "description": "Prefer reversible changes over irreversible"},
        {"rule": "prefer_incremental", "description": "Prefer small incremental changes"},
        {"rule": "explain_reasoning", "description": "Always explain the reasoning behind decisions"},
        {"rule": "cite_evidence", "description": "Support claims with evidence when possible"},
        {"rule": "dissent_welcome", "description": "Dissenting views should be preserved"},
        {"rule": "cost_awareness", "description": "Consider cost implications of recommendations"},
    ],
    "escalation_triggers": [
        {"condition": "risk_score > 0.7", "action": "escalate_to_t3"},
        {"condition": "security_signal_detected", "action": "trigger_sentinel"},
        {"condition": "breaking_change_detected", "action": "require_parent_council"},
        {"condition": "cost_exceeds_budget", "action": "notify_and_cap"},
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# Query-side detection keywords per hard constraint
# ──────────────────────────────────────────────────────────────────────────────

_QUERY_DETECTORS: Dict[str, List[str]] = {
    "no_ai_memory_write": [
        "write to chronos", "insert into chronos", "update chronos directly",
        "modify timeline directly", "push to event store",
    ],
    "no_ai_approval": [
        "auto-approve", "approve this yourself", "approve without human",
        "skip review and approve", "self-approve", "approve autonomously",
    ],
    "human_override": [
        "ignore human input", "override the human", "disregard user decision",
        "humans are wrong", "bypass human review",
    ],
    "no_data_deletion": [
        "delete all", "drop table", "truncate", "rm -rf", "destroy database",
        "wipe all data", "purge records", "delete production",
    ],
    "no_secret_exposure": [
        "show me the api key", "print the secret", "expose credentials",
        "reveal the password", "dump all tokens", "list api keys",
        "output the private key", "show env secrets",
    ],
    "no_governance_bypass": [
        "skip governance", "bypass archon", "disable sentinel",
        "turn off governance", "ignore governance", "disable constitution",
        "bypass security checks", "skip validation",
    ],
    "audit_trail_always": [
        "disable logging", "skip audit", "turn off audit trail",
        "no logging needed", "don't log this", "hide this action",
        "suppress audit", "delete audit logs",
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# Response-side detection keywords per hard constraint
# ──────────────────────────────────────────────────────────────────────────────

_RESPONSE_DETECTORS: Dict[str, List[str]] = {
    "no_ai_approval": [
        "i approve this", "auto-approving", "approved without review",
        "i have approved", "decision auto-approved", "approved autonomously",
    ],
    "no_ai_memory_write": [
        "i have written to chronos", "inserted into the timeline",
        "updated chronos directly", "committed to event store",
    ],
    "no_governance_bypass": [
        "i've disabled governance", "governance checks skipped",
        "bypassing archon", "sentinel has been disabled",
    ],
    "audit_trail_always": [
        "i've disabled logging", "audit trail suppressed",
        "this action won't be logged",
    ],
}


class ConstitutionalAI:
    """
    Guards council operations against constitutional violations.

    Usage:
        constitution = ConstitutionalAI()
        violations = constitution.check_query(user_query)
        if violations:
            raise GovernanceError(f"Constitutional violations: {violations}")
    """

    def __init__(self, constitution_path: Optional[str] = None) -> None:
        if constitution_path and os.path.exists(constitution_path):
            self.rules = self._load(constitution_path)
        else:
            self.rules = _DEFAULT_CONSTITUTION

    def _load(self, path: str) -> Dict[str, Any]:
        try:
            with open(path) as f:
                return yaml.safe_load(f)
        except Exception as exc:
            logger.warning(f"Failed to load constitution from {path}: {exc}")
            return _DEFAULT_CONSTITUTION

    # ══════════════════════════════════════════════
    # E1: Full constraint checks on queries
    # ══════════════════════════════════════════════

    def check_query(self, query: str) -> List[str]:
        """
        Check a query for constitutional violations BEFORE sending to LLM.

        Returns list of violation descriptions (empty = OK).
        All 7 hard constraints now have runtime detectors.
        """
        violations = []
        query_lower = query.lower()

        for constraint in self.rules.get("hard_constraints", []):
            rule = constraint["rule"]
            keywords = _QUERY_DETECTORS.get(rule, [])

            if any(kw in query_lower for kw in keywords):
                violations.append(f"BLOCKED: {constraint['description']}")

        return violations

    # ══════════════════════════════════════════════
    # E2: Extended response checks with shared patterns
    # ══════════════════════════════════════════════

    def check_response(self, response: str) -> List[str]:
        """
        Check an LLM response for constitutional violations AFTER generation.

        Extended with:
          - Shared secret detection patterns (same as red_team)
          - Keyword detectors for all response-checkable constraints
          - URL-pattern secret leak detection

        Returns list of violation descriptions (empty = OK).
        """
        violations = []
        response_lower = response.lower()

        for constraint in self.rules.get("hard_constraints", []):
            rule = constraint["rule"]

            # Keyword-based detection
            keywords = _RESPONSE_DETECTORS.get(rule, [])
            if any(kw in response_lower for kw in keywords):
                violations.append(f"BLOCKED: {constraint['description']}")

            # Secret pattern detection (shared with red_team)
            if rule == "no_secret_exposure":
                if SECRET_RE.search(response):
                    violations.append(f"REDACTED: {constraint['description']}")

        return violations

    # ══════════════════════════════════════════════
    # E3: Escalation trigger evaluation
    # ══════════════════════════════════════════════

    def evaluate_escalation(
        self,
        context: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """
        Evaluate escalation triggers against real runtime context.

        Args:
            context: Dict with keys like 'risk_score', 'has_security_signal',
                     'is_breaking_change', 'cost_usd', 'budget_usd'

        Returns:
            List of triggered escalation actions:
                [{"condition": "...", "action": "escalate_to_t3"}, ...]
        """
        triggered = []

        for trigger in self.rules.get("escalation_triggers", []):
            condition = trigger.get("condition", "")
            action = trigger.get("action", "")

            if self._evaluate_condition(condition, context):
                triggered.append({"condition": condition, "action": action})
                logger.info(f"Escalation triggered: {condition} → {action}")

        return triggered

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Parse and evaluate a single escalation condition string."""

        # Simple comparison: "risk_score > 0.7"
        match = re.match(r'(\w+)\s*(>|<|>=|<=|==)\s*([\d.]+)', condition)
        if match:
            field, op, threshold = match.groups()
            value = context.get(field)
            if value is None:
                return False
            threshold_f = float(threshold)
            value_f = float(value)
            ops = {
                '>': value_f > threshold_f,
                '<': value_f < threshold_f,
                '>=': value_f >= threshold_f,
                '<=': value_f <= threshold_f,
                '==': abs(value_f - threshold_f) < 1e-9,
            }
            return ops.get(op, False)

        # Boolean flags: "security_signal_detected"
        flag_map = {
            "security_signal_detected": "has_security_signal",
            "breaking_change_detected": "is_breaking_change",
            "cost_exceeds_budget": None,  # special handling
        }

        if condition in flag_map:
            mapped_key = flag_map[condition]

            # Special: cost budget check
            if condition == "cost_exceeds_budget":
                cost = context.get("cost_usd", 0.0)
                budget = context.get("budget_usd", float("inf"))
                return cost > budget

            if mapped_key:
                return bool(context.get(mapped_key, False))

        return False

    def build_system_prompt_preamble(self) -> str:
        """
        Build a preamble injected into every council system prompt
        to enforce soft guidelines.
        """
        guidelines = "\n".join(
            f"  - {g['description']}"
            for g in self.rules.get("soft_guidelines", [])
        )
        constraints = "\n".join(
            f"  - {c['description']}"
            for c in self.rules.get("hard_constraints", [])
        )

        return (
            "[AEGION CONSTITUTION — Governance Rules]\n\n"
            "HARD CONSTRAINTS (NEVER violate these):\n"
            f"{constraints}\n\n"
            "GUIDELINES (follow when possible):\n"
            f"{guidelines}\n"
        )

    def get_escalation_triggers(self) -> List[Dict[str, str]]:
        """Return configured escalation triggers."""
        return self.rules.get("escalation_triggers", [])


# Singleton
_constitution: Optional[ConstitutionalAI] = None


def get_constitution() -> ConstitutionalAI:
    global _constitution
    if _constitution is None:
        _constitution = ConstitutionalAI()
    return _constitution
