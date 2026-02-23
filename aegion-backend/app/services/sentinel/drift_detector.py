"""
Aegion Sentinel Drift Detector.

Phase 4: Advanced Epistemics
Detects pattern drift in decision-making behavior.
"""

from typing import List, Dict, Any, Optional
from datetime import timezone, datetime, timedelta

from ...contracts.risk import (
    DriftType, DriftSignal, DriftReport, RiskLevel
)
from ...core.logging import logger


class DriftDetector:
    """
    Detects drift in decision-making patterns.
    
    Doctrine: "Patterns reveal intent. Drift reveals risk."
    
    Detects:
    - Velocity changes (faster/slower decisions)
    - Evidence decline (less evidence per decision)
    - Tier escalation (more high-tier decisions)
    - Review bypass (fewer peer reviews)
    """

    def __init__(
        self,
        velocity_threshold: float = 0.3,  # 30% change triggers signal
        evidence_threshold: float = 0.25,  # 25% decline triggers signal
        tier_threshold: float = 0.2,       # 20% more high-tier triggers signal
        review_threshold: float = 0.2      # 20% fewer reviews triggers signal
    ):
        self.thresholds = {
            DriftType.VELOCITY_INCREASE: velocity_threshold,
            DriftType.VELOCITY_DECREASE: velocity_threshold,
            DriftType.EVIDENCE_DECLINE: evidence_threshold,
            DriftType.TIER_ESCALATION: tier_threshold,
            DriftType.REVIEW_BYPASS: review_threshold,
        }

    async def detect_drift(
        self,
        workspace_id: str,
        current_period: List[Dict],
        baseline_period: List[Dict],
        observation_hours: int = 24
    ) -> DriftReport:
        """
        Compare current period against baseline to detect drift.
        
        Args:
            workspace_id: Workspace to analyze
            current_period: Recent decisions/events
            baseline_period: Historical baseline for comparison
            observation_hours: Window size for observation
        """
        signals = []
        
        # Velocity drift
        velocity_signal = await self._detect_velocity_drift(
            workspace_id, current_period, baseline_period, observation_hours
        )
        if velocity_signal:
            signals.append(velocity_signal)
        
        # Evidence decline
        evidence_signal = await self._detect_evidence_drift(
            workspace_id, current_period, baseline_period
        )
        if evidence_signal:
            signals.append(evidence_signal)
        
        # Tier escalation
        tier_signal = await self._detect_tier_drift(
            workspace_id, current_period, baseline_period
        )
        if tier_signal:
            signals.append(tier_signal)
        
        # Review bypass
        review_signal = await self._detect_review_drift(
            workspace_id, current_period, baseline_period
        )
        if review_signal:
            signals.append(review_signal)
        
        # Build report
        critical_count = sum(1 for s in signals if s.severity == RiskLevel.CRITICAL)
        high_count = sum(1 for s in signals if s.severity == RiskLevel.HIGH)
        
        requires_attention = critical_count > 0 or high_count >= 2
        attention_reason = None
        if critical_count > 0:
            attention_reason = f"{critical_count} critical drift signal(s) detected"
        elif high_count >= 2:
            attention_reason = f"{high_count} high-severity drift signals detected"
        
        return DriftReport(
            workspace_id=workspace_id,
            generated_at=datetime.now(timezone.utc),
            signals=signals,
            total_signals=len(signals),
            critical_signals=critical_count,
            high_signals=high_count,
            requires_attention=requires_attention,
            attention_reason=attention_reason
        )

    # ========== Detection Methods ==========

    async def _detect_velocity_drift(
        self,
        workspace_id: str,
        current: List[Dict],
        baseline: List[Dict],
        hours: int
    ) -> Optional[DriftSignal]:
        """Detect velocity increase or decrease."""
        current_velocity = len(current) / max(hours, 1)
        baseline_velocity = len(baseline) / max(hours, 1)
        
        if baseline_velocity == 0:
            return None
        
        deviation = (current_velocity - baseline_velocity) / baseline_velocity
        abs_deviation = abs(deviation)
        
        threshold = self.thresholds[DriftType.VELOCITY_INCREASE]
        if abs_deviation < threshold:
            return None
        
        if deviation > 0:
            drift_type = DriftType.VELOCITY_INCREASE
            description = f"Decision velocity increased {abs_deviation*100:.0f}%"
            recommendation = "Consider slowing down to maintain quality"
        else:
            drift_type = DriftType.VELOCITY_DECREASE
            description = f"Decision velocity decreased {abs_deviation*100:.0f}%"
            recommendation = "Check for blockers or bottlenecks"
        
        severity = self._deviation_to_severity(abs_deviation)
        
        return DriftSignal(
            signal_id=f"drift-vel-{datetime.now(timezone.utc).timestamp():.0f}",
            drift_type=drift_type,
            severity=severity,
            baseline_value=baseline_velocity,
            current_value=current_velocity,
            deviation_percent=abs_deviation * 100,
            workspace_id=workspace_id,
            detected_at=datetime.now(timezone.utc),
            observation_window_hours=hours,
            description=description,
            recommendation=recommendation
        )

    async def _detect_evidence_drift(
        self,
        workspace_id: str,
        current: List[Dict],
        baseline: List[Dict]
    ) -> Optional[DriftSignal]:
        """Detect decline in evidence per decision."""
        def avg_evidence(decisions):
            if not decisions:
                return 0
            return sum(
                len(d.get("evidence_ids", [])) for d in decisions
            ) / len(decisions)
        
        current_avg = avg_evidence(current)
        baseline_avg = avg_evidence(baseline)
        
        if baseline_avg == 0:
            return None
        
        deviation = (baseline_avg - current_avg) / baseline_avg
        threshold = self.thresholds[DriftType.EVIDENCE_DECLINE]
        
        if deviation < threshold:
            return None
        
        return DriftSignal(
            signal_id=f"drift-evd-{datetime.now(timezone.utc).timestamp():.0f}",
            drift_type=DriftType.EVIDENCE_DECLINE,
            severity=self._deviation_to_severity(deviation),
            baseline_value=baseline_avg,
            current_value=current_avg,
            deviation_percent=deviation * 100,
            workspace_id=workspace_id,
            detected_at=datetime.now(timezone.utc),
            observation_window_hours=24,
            description=f"Average evidence per decision dropped from {baseline_avg:.1f} to {current_avg:.1f}",
            recommendation="Ensure decisions have sufficient supporting evidence"
        )

    async def _detect_tier_drift(
        self,
        workspace_id: str,
        current: List[Dict],
        baseline: List[Dict]
    ) -> Optional[DriftSignal]:
        """Detect increase in high-tier decisions."""
        def high_tier_ratio(decisions):
            if not decisions:
                return 0
            high_tier = sum(
                1 for d in decisions
                if d.get("tier") in ["T2", "T3"]
            )
            return high_tier / len(decisions)
        
        current_ratio = high_tier_ratio(current)
        baseline_ratio = high_tier_ratio(baseline)
        
        if baseline_ratio == 0 and current_ratio == 0:
            return None
        
        if baseline_ratio == 0:
            deviation = 1.0  # New high-tier activity
        else:
            deviation = (current_ratio - baseline_ratio) / baseline_ratio
        
        threshold = self.thresholds[DriftType.TIER_ESCALATION]
        
        if deviation < threshold:
            return None
        
        return DriftSignal(
            signal_id=f"drift-tier-{datetime.now(timezone.utc).timestamp():.0f}",
            drift_type=DriftType.TIER_ESCALATION,
            severity=self._deviation_to_severity(deviation),
            baseline_value=baseline_ratio * 100,
            current_value=current_ratio * 100,
            deviation_percent=deviation * 100,
            workspace_id=workspace_id,
            detected_at=datetime.now(timezone.utc),
            observation_window_hours=24,
            description=f"High-tier decisions increased from {baseline_ratio*100:.0f}% to {current_ratio*100:.0f}%",
            recommendation="Review high-tier decisions for appropriate escalation"
        )

    async def _detect_review_drift(
        self,
        workspace_id: str,
        current: List[Dict],
        baseline: List[Dict]
    ) -> Optional[DriftSignal]:
        """Detect decline in peer reviews."""
        def review_ratio(decisions):
            if not decisions:
                return 0
            reviewed = sum(
                1 for d in decisions
                if d.get("review_count", 0) > 0
            )
            return reviewed / len(decisions)
        
        current_ratio = review_ratio(current)
        baseline_ratio = review_ratio(baseline)
        
        if baseline_ratio == 0:
            return None
        
        deviation = (baseline_ratio - current_ratio) / baseline_ratio
        threshold = self.thresholds[DriftType.REVIEW_BYPASS]
        
        if deviation < threshold:
            return None
        
        return DriftSignal(
            signal_id=f"drift-rev-{datetime.now(timezone.utc).timestamp():.0f}",
            drift_type=DriftType.REVIEW_BYPASS,
            severity=self._deviation_to_severity(deviation),
            baseline_value=baseline_ratio * 100,
            current_value=current_ratio * 100,
            deviation_percent=deviation * 100,
            workspace_id=workspace_id,
            detected_at=datetime.now(timezone.utc),
            observation_window_hours=24,
            description=f"Peer review rate dropped from {baseline_ratio*100:.0f}% to {current_ratio*100:.0f}%",
            recommendation="Ensure peer reviews are not being bypassed"
        )

    def _deviation_to_severity(self, deviation: float) -> RiskLevel:
        """Convert deviation percentage to severity level."""
        if deviation >= 0.5:
            return RiskLevel.CRITICAL
        elif deviation >= 0.35:
            return RiskLevel.HIGH
        elif deviation >= 0.25:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
