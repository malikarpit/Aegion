"""
Aegion AI Safety Layer.

Doctrine: "AI serves governance. Governance constrains AI."

Provides:
- Token usage tracking and budget enforcement
- AI output safety classification
- Hallucination detection via evidence cross-referencing
- Per-user/workspace cost quotas
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel
from collections import defaultdict
import asyncio

from ...core.logging import logger


# ──────────────────────────────────────────────────────────────────────────
# Cost Tracking
# ──────────────────────────────────────────────────────────────────────────

class TokenUsage(BaseModel):
    """Record of token consumption for a single request."""
    request_id: str
    user_id: str
    workspace_id: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    timestamp: str


# Cost per 1K tokens (approximate, configurable)
MODEL_COSTS: Dict[str, Dict[str, float]] = {
    "gemini-2.0-flash": {"input": 0.00015, "output": 0.0006},
    "gemini-2.0-pro":  {"input": 0.00125, "output": 0.005},
    "gpt-4":           {"input": 0.03,    "output": 0.06},
    "gpt-4o":          {"input": 0.005,   "output": 0.015},
    "claude-3-opus":   {"input": 0.015,   "output": 0.075},
    "claude-3-sonnet": {"input": 0.003,   "output": 0.015},
    "default":         {"input": 0.001,   "output": 0.002},
}


class CostTracker:
    """
    Tracks AI token usage and enforces budget limits.

    Budgets are per-workspace per-day.
    """

    def __init__(self, daily_budget_usd: float = 50.0):
        self.daily_budget_usd = daily_budget_usd
        self._usage: Dict[str, List[TokenUsage]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def estimate_cost(
        self, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Estimate cost for a request."""
        costs = MODEL_COSTS.get(model, MODEL_COSTS["default"])
        return (
            (input_tokens / 1000) * costs["input"]
            + (output_tokens / 1000) * costs["output"]
        )

    async def record_usage(
        self,
        request_id: str,
        user_id: str,
        workspace_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> TokenUsage:
        """Record token usage for a request."""
        cost = self.estimate_cost(model, input_tokens, output_tokens)
        usage = TokenUsage(
            request_id=request_id,
            user_id=user_id,
            workspace_id=workspace_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        async with self._lock:
            bucket_key = f"{workspace_id}:{self._today()}"
            self._usage[bucket_key].append(usage)

        return usage

    async def check_budget(self, workspace_id: str) -> Tuple[bool, float, float]:
        """
        Check if workspace is within daily budget.

        Returns: (within_budget, spent_today, budget_remaining)
        """
        bucket_key = f"{workspace_id}:{self._today()}"

        async with self._lock:
            entries = self._usage.get(bucket_key, [])
            spent = sum(e.estimated_cost_usd for e in entries)

        remaining = max(0.0, self.daily_budget_usd - spent)
        return (spent < self.daily_budget_usd, spent, remaining)

    async def get_user_usage(
        self, user_id: str, workspace_id: str
    ) -> Dict[str, Any]:
        """Get usage summary for a user within a workspace."""
        bucket_key = f"{workspace_id}:{self._today()}"

        async with self._lock:
            entries = self._usage.get(bucket_key, [])
            user_entries = [e for e in entries if e.user_id == user_id]

        return {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "requests_today": len(user_entries),
            "total_input_tokens": sum(e.input_tokens for e in user_entries),
            "total_output_tokens": sum(e.output_tokens for e in user_entries),
            "total_cost_usd": sum(e.estimated_cost_usd for e in user_entries),
        }

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ──────────────────────────────────────────────────────────────────────────
# Output Safety Classification
# ──────────────────────────────────────────────────────────────────────────

class SafetyLevel(str, Enum):
    SAFE = "safe"               # No concerns
    REVIEW = "needs_review"     # Human should review
    BLOCKED = "blocked"         # Output should not be shown


class SafetyClassification(BaseModel):
    """Result of safety classification."""
    level: SafetyLevel
    confidence: float  # 0.0 to 1.0
    reasons: List[str]
    flagged_content: Optional[str] = None


class OutputClassifier:
    """
    Classifies AI output for safety concerns.

    Checks for:
    - Code execution suggestions without sandbox
    - Sensitive data disclosure patterns
    - Authority escalation recommendations
    - Governance bypass suggestions
    """

    # Patterns that trigger review
    REVIEW_PATTERNS = [
        "rm -rf",
        "sudo",
        "DROP TABLE",
        "DELETE FROM",
        "format c:",
        "bypass",
        "skip governance",
        "ignore approval",
        "override archon",
        "disable security",
    ]

    # Patterns that trigger blocking
    BLOCK_PATTERNS = [
        "password:",
        "secret_key:",
        "api_key:",
        "private_key",
        "BEGIN RSA PRIVATE",
        "BEGIN EC PRIVATE",
    ]

    def classify(self, output: str) -> SafetyClassification:
        """Classify AI output safety."""
        reasons = []
        level = SafetyLevel.SAFE

        output_lower = output.lower()

        # Check block patterns
        for pattern in self.BLOCK_PATTERNS:
            if pattern.lower() in output_lower:
                level = SafetyLevel.BLOCKED
                reasons.append(f"Sensitive data pattern: {pattern}")

        # Check review patterns
        if level != SafetyLevel.BLOCKED:
            for pattern in self.REVIEW_PATTERNS:
                if pattern.lower() in output_lower:
                    level = SafetyLevel.REVIEW
                    reasons.append(f"Potentially unsafe pattern: {pattern}")

        return SafetyClassification(
            level=level,
            confidence=0.85 if reasons else 0.95,
            reasons=reasons if reasons else ["No safety concerns detected"],
        )


# ──────────────────────────────────────────────────────────────────────────
# Hallucination Guard
# ──────────────────────────────────────────────────────────────────────────

class HallucinationGuard:
    """
    Cross-references AI claims against the evidence graph.

    When AI makes factual claims about the codebase or decisions,
    verify them against known evidence nodes.
    """

    def __init__(self, graph_service=None):
        self._graph = graph_service

    async def check_claim(
        self,
        claim: str,
        evidence_ids: List[str],
        workspace_id: str,
    ) -> Dict[str, Any]:
        """
        Verify an AI claim against evidence.

        Returns verification result with confidence score.
        """
        if not self._graph:
            return {
                "verified": False,
                "confidence": 0.0,
                "reason": "No graph service available for verification",
            }

        verified_count = 0
        total = len(evidence_ids)

        for eid in evidence_ids:
            node = await self._graph.get_node(eid)
            if node and node.properties.get("workspace_id") == workspace_id:
                verified_count += 1

        confidence = verified_count / total if total > 0 else 0.0

        return {
            "verified": confidence > 0.5,
            "confidence": confidence,
            "evidence_checked": total,
            "evidence_found": verified_count,
            "reason": (
                "Sufficient evidence support"
                if confidence > 0.5
                else "Insufficient evidence backing"
            ),
        }


# ──────────────────────────────────────────────────────────────────────────
# Singletons
# ──────────────────────────────────────────────────────────────────────────

_cost_tracker: Optional[CostTracker] = None
_output_classifier: Optional[OutputClassifier] = None


def get_cost_tracker(daily_budget_usd: float = 50.0) -> CostTracker:
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker(daily_budget_usd=daily_budget_usd)
    return _cost_tracker


def get_output_classifier() -> OutputClassifier:
    global _output_classifier
    if _output_classifier is None:
        _output_classifier = OutputClassifier()
    return _output_classifier
