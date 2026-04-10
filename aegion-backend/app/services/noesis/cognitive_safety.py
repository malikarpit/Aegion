"""
Aegion Cognitive Safety Service.

Phase 4: Advanced Epistemics
Monitors cognitive load and prevents decision fatigue.
"""

from typing import Dict, Any, Optional, Tuple, List
from datetime import timezone, datetime, timedelta

from ...contracts.risk import (
    CognitiveLoadLevel,
    CognitiveLoadFactors,
    CognitiveLoadAssessment,
    UncertaintyVisualization,
)
from ...core.logging import logger


class CognitiveSafetyService:
    """
    Monitors cognitive load and decision fatigue.
    
    Doctrine: "A tired mind makes dangerous decisions."
    
    Factors:
    - Decisions per hour
    - Decision complexity
    - Time since break
    - Error rate trend
    - Context switches
    """

    def __init__(
        self,
        decisions_per_hour_limit: float = 10.0,
        hours_without_break_limit: float = 2.0,
        error_rate_limit: float = 0.15,
        complexity_limit: float = 7.0
    ):
        self.limits = {
            "decisions_per_hour": decisions_per_hour_limit,
            "hours_without_break": hours_without_break_limit,
            "error_rate": error_rate_limit,
            "avg_complexity": complexity_limit,
        }
        
        # In-memory tracking (would be backed by DB in production)
        self._user_sessions: Dict[str, Dict[str, Any]] = {}

    async def assess_cognitive_load(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        recent_decisions: Optional[List[Dict]] = None,
        hours_active: float = 0.0
    ) -> CognitiveLoadAssessment:
        """
        Assess current cognitive load for a user.
        
        Args:
            user_id: User to assess
            session_id: Optional session context
            recent_decisions: Recent decision data
            hours_active: Hours since session start
        """
        # Calculate factors
        decisions = recent_decisions or []
        
        decisions_per_hour = len(decisions) / max(hours_active, 0.5)
        
        avg_complexity = 0.0
        if decisions:
            complexities = [d.get("complexity", 5) for d in decisions]
            avg_complexity = sum(complexities) / len(complexities)
        
        # Get from tracking or estimate
        session_data = self._user_sessions.get(user_id, {})
        hours_since_break = session_data.get("hours_since_break", hours_active)
        error_rate = session_data.get("recent_error_rate", 0.0)
        context_switches = session_data.get("context_switches", 0)
        high_tier_count = sum(
            1 for d in decisions if d.get("tier") in ["T2", "T3"]
        )
        
        factors = CognitiveLoadFactors(
            decisions_per_hour=decisions_per_hour,
            avg_decision_complexity=avg_complexity,
            hours_since_break=hours_since_break,
            error_rate_recent=error_rate,
            context_switches=context_switches,
            high_tier_decisions=high_tier_count
        )
        
        # Calculate load score (0-100)
        load_score = self._calculate_load_score(factors)
        load_level = self._score_to_level(load_score)
        
        # Determine if break is needed
        should_break, break_reason = self._should_suggest_break(factors, load_level)
        recommended_minutes = self._recommend_break_duration(load_level)
        
        return CognitiveLoadAssessment(
            user_id=user_id,
            session_id=session_id,
            load_level=load_level,
            load_score=load_score,
            factors=factors,
            should_break=should_break,
            break_reason=break_reason,
            recommended_break_minutes=recommended_minutes,
            assessed_at=datetime.now(timezone.utc)
        )

    async def should_suggest_break(
        self,
        user_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Quick check if user should take a break.
        """
        assessment = await self.assess_cognitive_load(user_id)
        return assessment.should_break, assessment.break_reason

    async def get_uncertainty_visualization(
        self,
        decision_id: str,
        evidence_data: Optional[List[Dict]] = None,
        confidence_level: float = 0.95
    ) -> UncertaintyVisualization:
        """
        Generate visualization data for decision uncertainty.
        
        Args:
            decision_id: Decision to visualize
            evidence_data: Evidence supporting the decision
            confidence_level: Confidence interval level (default 95%)
        """
        evidence = evidence_data or []
        
        # Calculate evidence metrics
        evidence_count = len(evidence)
        contradictory_count = sum(
            1 for e in evidence
            if e.get("classification") == "contradictory"
        )
        
        # Evidence strength (0-1)
        if evidence_count > 0:
            evidence_strength = 1.0 - (contradictory_count / evidence_count)
            evidence_strength *= min(1.0, evidence_count / 3.0)  # Bonus for more evidence
        else:
            evidence_strength = 0.0
        
        # Overall uncertainty (inverse of strength)
        overall_uncertainty = 1.0 - evidence_strength
        
        # Uncertainty components
        components = {
            "evidence_scarcity": max(0.0, 1.0 - evidence_count / 5.0),
            "contradictory_evidence": contradictory_count / max(evidence_count, 1),
            "freshness": sum(
                1 for e in evidence if e.get("is_stale", False)
            ) / max(evidence_count, 1)
        }
        
        # Confidence interval
        # Simple heuristic: stronger evidence = tighter interval
        interval_width = overall_uncertainty * 0.4
        confidence_lower = max(0.0, evidence_strength - interval_width / 2)
        confidence_upper = min(1.0, evidence_strength + interval_width / 2)
        
        # Display hints
        if overall_uncertainty < 0.2:
            color = "green"
            display_type = "gauge"
        elif overall_uncertainty < 0.4:
            color = "yellow"
            display_type = "confidence_interval"
        elif overall_uncertainty < 0.6:
            color = "orange"
            display_type = "confidence_interval"
        else:
            color = "red"
            display_type = "bar"
        
        # Generate explanation
        explanation = self._generate_uncertainty_explanation(
            overall_uncertainty, components, evidence_count, contradictory_count
        )
        
        return UncertaintyVisualization(
            decision_id=decision_id,
            overall_uncertainty=overall_uncertainty,
            uncertainty_components=components,
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            confidence_level=confidence_level,
            evidence_strength=evidence_strength,
            evidence_count=evidence_count,
            contradictory_evidence_count=contradictory_count,
            display_type=display_type,
            color_code=color,
            uncertainty_explanation=explanation
        )

    async def record_decision(
        self,
        user_id: str,
        decision_data: Dict[str, Any]
    ) -> None:
        """Record a decision for cognitive load tracking."""
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = {
                "decisions": [],
                "session_start": datetime.now(timezone.utc),
                "last_break": datetime.now(timezone.utc),
                "context_switches": 0,
                "recent_error_rate": 0.0,
            }
        
        self._user_sessions[user_id]["decisions"].append({
            **decision_data,
            "recorded_at": datetime.now(timezone.utc)
        })
        
        # Update hours since break
        last_break = self._user_sessions[user_id].get(
            "last_break", datetime.now(timezone.utc)
        )
        self._user_sessions[user_id]["hours_since_break"] = (
            datetime.now(timezone.utc) - last_break
        ).total_seconds() / 3600

    async def record_break(self, user_id: str) -> None:
        """Record that user took a break."""
        if user_id in self._user_sessions:
            self._user_sessions[user_id]["last_break"] = datetime.now(timezone.utc)
            self._user_sessions[user_id]["hours_since_break"] = 0.0

    # ========== Private Methods ==========

    def _calculate_load_score(self, factors: CognitiveLoadFactors) -> float:
        """Calculate composite load score (0-100)."""
        # Normalize each factor against limits
        velocity_score = min(100, (
            factors.decisions_per_hour / self.limits["decisions_per_hour"]
        ) * 100)
        
        time_score = min(100, (
            factors.hours_since_break / self.limits["hours_without_break"]
        ) * 100)
        
        error_score = min(100, (
            factors.error_rate_recent / self.limits["error_rate"]
        ) * 100)
        
        complexity_score = min(100, (
            factors.avg_decision_complexity / self.limits["avg_complexity"]
        ) * 100)
        
        # Weighted average
        return (
            velocity_score * 0.25 +
            time_score * 0.30 +
            error_score * 0.25 +
            complexity_score * 0.20
        )

    def _score_to_level(self, score: float) -> CognitiveLoadLevel:
        """Convert score to level."""
        if score >= 80:
            return CognitiveLoadLevel.OVERLOADED
        elif score >= 60:
            return CognitiveLoadLevel.HIGH
        elif score >= 40:
            return CognitiveLoadLevel.ELEVATED
        else:
            return CognitiveLoadLevel.OPTIMAL

    def _should_suggest_break(
        self,
        factors: CognitiveLoadFactors,
        level: CognitiveLoadLevel
    ) -> Tuple[bool, Optional[str]]:
        """Determine if break should be suggested."""
        if level == CognitiveLoadLevel.OVERLOADED:
            return True, "Cognitive load is critical. Take a break now."
        
        if level == CognitiveLoadLevel.HIGH:
            if factors.hours_since_break > 1.5:
                return True, "High load for extended period. Break recommended."
        
        if factors.hours_since_break > self.limits["hours_without_break"]:
            return True, f"Working over {self.limits['hours_without_break']:.0f} hours without break."
        
        if factors.error_rate_recent > self.limits["error_rate"]:
            return True, "Error rate elevated. Take a brief rest."
        
        return False, None

    def _recommend_break_duration(self, level: CognitiveLoadLevel) -> int:
        """Recommend break duration in minutes."""
        durations = {
            CognitiveLoadLevel.OVERLOADED: 30,
            CognitiveLoadLevel.HIGH: 15,
            CognitiveLoadLevel.ELEVATED: 10,
            CognitiveLoadLevel.OPTIMAL: 5,
        }
        return durations.get(level, 10)

    def _generate_uncertainty_explanation(
        self,
        uncertainty: float,
        components: Dict[str, float],
        evidence_count: int,
        contradictory_count: int
    ) -> str:
        """Generate human-readable uncertainty explanation."""
        parts = []
        
        if uncertainty < 0.2:
            parts.append("High confidence decision backed by strong evidence.")
        elif uncertainty < 0.4:
            parts.append("Moderately confident decision.")
        elif uncertainty < 0.6:
            parts.append("Significant uncertainty exists.")
        else:
            parts.append("High uncertainty - proceed with caution.")
        
        if evidence_count < 2:
            parts.append(f"Only {evidence_count} evidence item(s) available.")
        
        if contradictory_count > 0:
            parts.append(f"{contradictory_count} contradictory evidence item(s) noted.")
        
        if components.get("freshness", 0) > 0.3:
            parts.append("Some evidence may be stale.")
        
        return " ".join(parts)
