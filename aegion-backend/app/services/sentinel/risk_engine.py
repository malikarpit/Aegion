"""
Sentinel Risk Engine — initial implementation.

Uses basic threshold scoring. ML-style multi-signal scoring
will be added when the signal pipeline is complete.
"""

from typing import Dict, Any, List, Optional
from ...core.logging import logger


class RiskEngine:
    """Threshold-based risk scoring for proposals."""

    THRESHOLDS = {
        "low": 0.3,
        "medium": 0.6,
        "high": 0.8,
        "critical": 0.95,
    }

    def score_proposal(self, proposal: Dict[str, Any]) -> float:
        """Score risk of a proposal (0.0 = safe, 1.0 = dangerous)."""
        score = 0.0
        description = proposal.get("description", "").lower()

        # Simple keyword heuristics
        danger_keywords = ["delete", "drop", "rm -rf", "production", "deploy", "migrate"]
        for kw in danger_keywords:
            if kw in description:
                score += 0.15

        return min(score, 1.0)

    def classify(self, score: float) -> str:
        """Classify risk level from score."""
        if score >= self.THRESHOLDS["critical"]:
            return "critical"
        elif score >= self.THRESHOLDS["high"]:
            return "high"
        elif score >= self.THRESHOLDS["medium"]:
            return "medium"
        return "low"
