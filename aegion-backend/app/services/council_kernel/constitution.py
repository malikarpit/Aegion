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

    Supports three rule sources (checked in priority order):
        1. Workspace-specific overrides from Supabase (highest priority)
        2. Global rules from Supabase
        3. Default hardcoded rules (fallback when DB unavailable)

    All blocking decisions include structured explanations so the user
    understands WHY their query was blocked and HOW to remediate.

    Usage:
        constitution = ConstitutionalAI()
        violations = constitution.check_query(user_query)
        if violations:
            explanations = constitution.explain_violations(user_query, violations)
            raise GovernanceError(f"Constitutional violations: {explanations}")
    """

    def __init__(self, constitution_path: Optional[str] = None, workspace_id: Optional[str] = None) -> None:
        self.workspace_id = workspace_id
        if constitution_path and os.path.exists(constitution_path):
            self.rules = self._load(constitution_path)
        else:
            self.rules = self._load_from_db_or_default(workspace_id=workspace_id)

    def _load(self, path: str) -> Dict[str, Any]:
        try:
            with open(path) as f:
                return yaml.safe_load(f)
        except Exception as exc:
            logger.warning(f"Failed to load constitution from {path}: {exc}")
            return _DEFAULT_CONSTITUTION

    def _load_from_db_or_default(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Attempt to load constitutional rules from Supabase.

        Falls back to _DEFAULT_CONSTITUTION if DB is unavailable.
        This enables runtime rule management via admin API without
        requiring a code deploy.

        W2.1: Supports workspace-scoped rules — loads global rules plus
        workspace-specific overrides when workspace_id is provided.
        """
        try:
            from ...db.supabase_client import get_supabase_client
            client = get_supabase_client()
            # Load global rules (workspace_id IS NULL) + workspace-specific rules
            query = client.table("constitutional_rules").select("*")
            if workspace_id:
                query = query.or_(f"workspace_id.is.null,workspace_id.eq.{workspace_id}")
            result = query.execute()
            if result.data:
                return self._db_rows_to_constitution(result.data)
        except ImportError:
            logger.debug("Constitution: Supabase not available, using defaults")
        except Exception as exc:
            logger.debug(f"Constitution: DB load failed ({exc}), using defaults")

        return _DEFAULT_CONSTITUTION

    @staticmethod
    def _db_rows_to_constitution(rows: List[Dict]) -> Dict[str, Any]:
        """
        Convert flat DB rows to the nested constitution format.

        DB schema: constitutional_rules(
            id, rule_type, rule_id, description,
            severity, enabled, workspace_id,
            metadata_json, created_at, updated_at
        )
        """
        hard = []
        soft = []
        escalation = []

        for row in rows:
            if not row.get("enabled", True):
                continue

            rule_type = row.get("rule_type", "hard")
            entry = {
                "rule": row.get("rule_id", ""),
                "description": row.get("description", ""),
            }

            if rule_type == "hard":
                hard.append(entry)
            elif rule_type == "soft":
                soft.append(entry)
            elif rule_type == "escalation":
                meta = row.get("metadata_json", {}) or {}
                escalation.append({
                    "condition": meta.get("condition", ""),
                    "action": meta.get("action", ""),
                })

        return {
            "version": "2.0.0-db",
            "hard_constraints": hard or _DEFAULT_CONSTITUTION["hard_constraints"],
            "soft_guidelines": soft or _DEFAULT_CONSTITUTION["soft_guidelines"],
            "escalation_triggers": escalation or _DEFAULT_CONSTITUTION["escalation_triggers"],
        }

    # ══════════════════════════════════════════════
    # E1: Full constraint checks on queries
    # ══════════════════════════════════════════════

    def check_query(self, query: str) -> List[str]:
        """
        Check a query for constitutional violations BEFORE sending to LLM.

        Returns list of violation descriptions (empty = OK).
        All 7 hard constraints now have runtime detectors.

        W2.1: Each violation now includes the rule_id for traceability.
        """
        violations = []
        query_lower = query.lower()

        for constraint in self.rules.get("hard_constraints", []):
            rule = constraint["rule"]
            keywords = _QUERY_DETECTORS.get(rule, [])

            if any(kw in query_lower for kw in keywords):
                violations.append(f"BLOCKED [{rule}]: {constraint['description']}")

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
    # Explain-Why: Structured Violation Explanations
    # ══════════════════════════════════════════════

    # Human-readable explanations for each hard constraint
    _RULE_EXPLANATIONS: Dict[str, Dict[str, str]] = {
        "no_ai_memory_write": {
            "why": "Direct AI writes to the Chronos timeline could corrupt the historical "
                   "decision record. All memory writes must go through the audited pipeline.",
            "remediation": "Use the Chronos API through the governance layer instead of "
                          "requesting direct writes.",
        },
        "no_ai_approval": {
            "why": "Tier 2+ decisions require human judgement. Autonomous AI approval "
                   "would bypass the accountability chain required by governance policy.",
            "remediation": "Submit the decision for human review via the approval workflow.",
        },
        "human_override": {
            "why": "Human authority is the highest-priority governance principle. "
                   "AI must always defer to explicit human decisions.",
            "remediation": "Rephrase your request to work with human decisions, not against them.",
        },
        "no_data_deletion": {
            "why": "Production data deletion is irreversible and could cause data loss. "
                   "Even backups may not be sufficient for full recovery.",
            "remediation": "Use soft-delete (archive) operations or request a supervised "
                          "deletion through the admin interface.",
        },
        "no_secret_exposure": {
            "why": "API keys, tokens, and credentials in responses could be stored in "
                   "logs, caches, or conversation history, leading to credential leaks.",
            "remediation": "Reference secrets by name (e.g., 'OPENAI_KEY') rather than "
                          "requesting their actual values.",
        },
        "no_governance_bypass": {
            "why": "Governance checks (Archon, Sentinel, Constitution) are safety-critical. "
                   "Disabling them removes the safety net for all subsequent operations.",
            "remediation": "If you need to adjust governance behavior, use the admin settings "
                          "to modify thresholds, not disable checks entirely.",
        },
        "audit_trail_always": {
            "why": "The audit trail provides accountability, debugging, and compliance evidence. "
                   "Gaps in logging make incident investigation impossible.",
            "remediation": "All actions are logged by design. If you need reduced logging "
                          "verbosity, adjust the log level in settings.",
        },
    }

    def explain_violations(
        self,
        query: str,
        violations: List[str],
    ) -> List[Dict[str, str]]:
        """
        Generate structured, human-readable explanations for each violation.

        Returns a list of dicts with keys:
            - rule: The constitutional rule ID
            - description: Short description of the rule
            - why: WHY this rule exists
            - evidence: WHAT in the query triggered the block
            - remediation: HOW the user can rephrase/fix their query
        """
        explanations = []
        query_lower = query.lower()

        for violation_str in violations:
            # Extract rule info from the violation string
            for constraint in self.rules.get("hard_constraints", []):
                if constraint["description"] in violation_str:
                    rule_id = constraint["rule"]
                    rule_info = self._RULE_EXPLANATIONS.get(rule_id, {})

                    # Find which keyword triggered it
                    keywords = _QUERY_DETECTORS.get(rule_id, [])
                    triggered_by = [kw for kw in keywords if kw in query_lower]

                    explanations.append({
                        "rule": rule_id,
                        "description": constraint["description"],
                        "why": rule_info.get("why", "This rule protects system integrity."),
                        "evidence": f"Triggered by: {', '.join(triggered_by)}" if triggered_by else "Pattern match detected",
                        "remediation": rule_info.get("remediation", "Please rephrase your request."),
                    })
                    break

        return explanations

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

    def reload_from_db(self) -> bool:
        """
        Hot-reload rules from DB without restarting the engine.

        Returns True if DB rules were loaded, False if fell back to defaults.
        """
        new_rules = self._load_from_db_or_default()
        is_db = new_rules.get("version", "").endswith("-db")
        self.rules = new_rules
        logger.info(f"Constitution reloaded (source={'db' if is_db else 'defaults'})")
        return is_db


# Singleton
_constitution: Optional[ConstitutionalAI] = None


def get_constitution() -> ConstitutionalAI:
    global _constitution
    if _constitution is None:
        _constitution = ConstitutionalAI()
    return _constitution
