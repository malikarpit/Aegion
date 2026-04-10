"""
Aegion AI Safety Hardening: Compliance.

Provides:
- Prompt injection detection (pattern + scoring)
- PII redaction before model delivery
- Governance-aware classification (block override attempts)
- Cost circuit breaker (per-request and daily limits)
- Training data leakage defense
"""

import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone


class SafetyVerdict(str, Enum):
    """AI safety check result."""
    ALLOW = "allow"
    REVIEW = "review"    # Score > 0.4
    BLOCK = "block"       # Score > 0.7


@dataclass
class SafetyCheckResult:
    """Result of an AI safety check."""
    verdict: SafetyVerdict
    score: float
    reasons: List[str]
    redacted_input: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# ========== Injection Detection ==========

_INJECTION_PATTERNS: List[Tuple[str, float, re.Pattern]] = [
    ("ignore_instructions", 0.8, re.compile(
        r"ignore\s+(previous|all|above|prior)\s+(instructions|prompts|rules)",
        re.IGNORECASE
    )),
    ("system_override", 0.9, re.compile(
        r"(system\s*:?\s*you\s+are|new\s+system\s+prompt|override\s+system)",
        re.IGNORECASE
    )),
    ("role_play_escape", 0.7, re.compile(
        r"(pretend|act\s+as\s+if|imagine\s+you\s+are|you\s+are\s+now)\s+(a\s+)?(different|new|unrestricted)",
        re.IGNORECASE
    )),
    ("governance_bypass", 0.95, re.compile(
        r"(skip|bypass|ignore|override|disable)\s+(approval|governance|freeze|proposal|review)",
        re.IGNORECASE
    )),
    ("jailbreak_marker", 0.85, re.compile(
        r"(DAN|do\s+anything\s+now|jailbreak|unrestricted\s+mode)",
        re.IGNORECASE
    )),
    ("data_exfil", 0.8, re.compile(
        r"(show|reveal|display|print|output)\s+(all|every|the)\s+(secret|key|password|token|credential)",
        re.IGNORECASE
    )),
]

# Governance terms that AI must never recommend bypassing
_GOVERNANCE_TERMS = {
    "skip approval", "override freeze", "bypass governance",
    "ignore proposal", "disable audit", "remove rate limit",
    "skip review", "bypass security",
}


def detect_injection(text: str) -> Tuple[float, List[str]]:
    """
    Detect prompt injection attempts.

    Returns (max_score, list_of_matched_patterns).
    Score > 0.7 = BLOCK, > 0.4 = REVIEW, <= 0.4 = ALLOW.
    """
    max_score = 0.0
    matches = []

    for name, score, pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            max_score = max(max_score, score)
            matches.append(name)

    return (max_score, matches)


# ========== PII Redaction ==========

_PII_PATTERNS = [
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("phone", re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")),
    ("api_key", re.compile(r"(?:sk|pk|api)[_-][A-Za-z0-9]{20,}", re.IGNORECASE)),
]


def redact_pii_for_model(text: str) -> Tuple[str, List[str]]:
    """
    Redact PII before sending to AI model.

    Returns (redacted_text, list_of_redacted_types).
    """
    result = text
    redacted = []

    for name, pattern in _PII_PATTERNS:
        if pattern.search(result):
            result = pattern.sub(f"[{name.upper()}_REDACTED]", result)
            redacted.append(name)

    return (result, redacted)


# ========== Cost Circuit Breaker ==========

class CostCircuitBreaker:
    """
    Prevents runaway AI costs.

    - Per-request limit: abort if estimated cost > $1
    - Daily workspace limit: hard cutoff at configurable threshold
    """

    def __init__(
        self,
        per_request_limit: float = 1.0,
        daily_workspace_limit: float = 50.0,
    ):
        self.per_request_limit = per_request_limit
        self.daily_workspace_limit = daily_workspace_limit
        self._daily_costs: Dict[str, float] = {}
        self._total_blocked = 0

    def check_request(
        self, workspace_id: str, estimated_cost: float
    ) -> Tuple[bool, str]:
        """
        Check if request should proceed.

        Returns (allowed, reason).
        """
        if estimated_cost > self.per_request_limit:
            self._total_blocked += 1
            return (False, f"Request cost ${estimated_cost:.2f} exceeds per-request limit ${self.per_request_limit:.2f}")

        current_daily = self._daily_costs.get(workspace_id, 0.0)
        if current_daily + estimated_cost > self.daily_workspace_limit:
            self._total_blocked += 1
            return (False, f"Daily limit would be exceeded: ${current_daily:.2f} + ${estimated_cost:.2f} > ${self.daily_workspace_limit:.2f}")

        return (True, "OK")

    def record_cost(self, workspace_id: str, actual_cost: float) -> None:
        """Record actual cost after request completes."""
        self._daily_costs[workspace_id] = self._daily_costs.get(workspace_id, 0.0) + actual_cost

    def reset_daily(self) -> None:
        """Reset daily cost counters (call at midnight UTC)."""
        self._daily_costs.clear()

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "daily_costs": dict(self._daily_costs),
            "total_blocked": self._total_blocked,
            "workspaces_tracked": len(self._daily_costs),
        }


# ========== Leakage Defense ==========

_INTERNAL_PATTERNS = [
    re.compile(r"node_[a-f0-9]{8,}"),  # Internal node IDs
    re.compile(r"ws_[a-f0-9]{8,}"),     # Internal workspace IDs
    re.compile(r"session_[a-f0-9]{8,}"),  # Session IDs
]


def check_output_leakage(model_output: str) -> Tuple[bool, List[str]]:
    """
    Check model output for internal data leakage.

    Returns (has_leakage, list_of_leaked_patterns).
    """
    leaked = []
    for pattern in _INTERNAL_PATTERNS:
        if pattern.search(model_output):
            leaked.append(pattern.pattern)

    return (len(leaked) > 0, leaked)


# ========== Main Safety Pipeline ==========

class AISafetyPipeline:
    """
    Orchestrates all AI safety checks in order:
    1. Injection detection
    2. PII redaction
    3. Cost check
    4. Output leakage check (post-response)
    """

    def __init__(self, cost_breaker: Optional[CostCircuitBreaker] = None):
        self._cost_breaker = cost_breaker or CostCircuitBreaker()
        self._check_log: List[SafetyCheckResult] = []

    def check_input(
        self,
        text: str,
        workspace_id: str,
        estimated_cost: float = 0.0,
    ) -> SafetyCheckResult:
        """Run all input safety checks."""
        reasons = []

        # 1. Injection detection
        score, injection_matches = detect_injection(text)
        if injection_matches:
            reasons.extend([f"injection:{m}" for m in injection_matches])

        # 2. Governance term check
        text_lower = text.lower()
        for term in _GOVERNANCE_TERMS:
            if term in text_lower:
                score = max(score, 0.95)
                reasons.append(f"governance_bypass:{term}")

        # 3. PII redaction
        redacted_text, pii_types = redact_pii_for_model(text)
        if pii_types:
            reasons.extend([f"pii_redacted:{t}" for t in pii_types])

        # 4. Cost check
        if estimated_cost > 0:
            allowed, cost_reason = self._cost_breaker.check_request(
                workspace_id, estimated_cost
            )
            if not allowed:
                score = max(score, 0.8)
                reasons.append(f"cost:{cost_reason}")

        # Determine verdict
        if score > 0.7:
            verdict = SafetyVerdict.BLOCK
        elif score > 0.4:
            verdict = SafetyVerdict.REVIEW
        else:
            verdict = SafetyVerdict.ALLOW

        result = SafetyCheckResult(
            verdict=verdict,
            score=round(score, 2),
            reasons=reasons,
            redacted_input=redacted_text if pii_types else None,
        )
        self._check_log.append(result)
        return result

    def check_output(self, model_output: str) -> Tuple[bool, List[str]]:
        """Check model output for leakage."""
        return check_output_leakage(model_output)

    def get_check_log(self) -> List[SafetyCheckResult]:
        return list(self._check_log)

    @property
    def stats(self) -> Dict[str, Any]:
        total = len(self._check_log)
        blocked = sum(1 for r in self._check_log if r.verdict == SafetyVerdict.BLOCK)
        reviewed = sum(1 for r in self._check_log if r.verdict == SafetyVerdict.REVIEW)
        return {
            "total_checks": total,
            "blocked": blocked,
            "reviewed": reviewed,
            "allowed": total - blocked - reviewed,
            "cost_stats": self._cost_breaker.stats,
        }
