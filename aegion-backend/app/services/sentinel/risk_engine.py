"""
Aegion Sentinel Risk Engine.

Phase 4: Advanced Epistemics
Calculates risk scores based on decision patterns, evidence freshness, and velocity.
"""

from typing import List, Dict, Any, Optional
from datetime import timezone, datetime, timedelta

from ...contracts.risk import (
    RiskScore, RiskLevel, RiskCategory,
    RiskHeatmap, RiskHeatmapCell
)
from ...core.logging import logger


class RiskEngine:
    """
    Calculates risk scores for workspaces and entities.
    
    Doctrine: "Risk is the shadow of opportunity. Measure it."
    
    Risk Factors:
    - Staleness ratio (stale evidence / total evidence)
    - Decision velocity (decisions per hour)
    - Tier distribution (high-tier decisions frequency)
    - Evidence gaps (decisions with insufficient evidence)
    """

    def __init__(
        self,
        staleness_weight: float = 0.3,
        velocity_weight: float = 0.25,
        tier_weight: float = 0.25,
        evidence_weight: float = 0.2
    ):
        self.weights = {
            RiskCategory.STALENESS: staleness_weight,
            RiskCategory.VELOCITY: velocity_weight,
            RiskCategory.AUTHORITY: tier_weight,
            RiskCategory.EVIDENCE_GAP: evidence_weight,
        }

    async def calculate_risk_score(
        self,
        workspace_id: str,
        decisions: Optional[List[Dict]] = None,
        evidence: Optional[List[Dict]] = None,
        lookback_hours: int = 24
    ) -> RiskScore:
        """
        Calculate composite risk score for a workspace.
        
        Args:
            workspace_id: Workspace to analyze
            decisions: Recent decisions (optional, will fetch if not provided)
            evidence: Recent evidence (optional, will fetch if not provided)
            lookback_hours: Time window for analysis
        """
        # Calculate component scores
        component_scores = {}
        contributing_factors = []
        
        # Staleness score
        staleness_score, staleness_factors = await self._calculate_staleness_score(
            evidence or []
        )
        component_scores[RiskCategory.STALENESS] = staleness_score
        contributing_factors.extend(staleness_factors)
        
        # Velocity score
        velocity_score, velocity_factors = await self._calculate_velocity_score(
            decisions or [], lookback_hours
        )
        component_scores[RiskCategory.VELOCITY] = velocity_score
        contributing_factors.extend(velocity_factors)
        
        # Tier distribution score
        tier_score, tier_factors = await self._calculate_tier_score(
            decisions or []
        )
        component_scores[RiskCategory.AUTHORITY] = tier_score
        contributing_factors.extend(tier_factors)
        
        # Evidence gap score
        evidence_score, evidence_factors = await self._calculate_evidence_gap_score(
            decisions or [], evidence or []
        )
        component_scores[RiskCategory.EVIDENCE_GAP] = evidence_score
        contributing_factors.extend(evidence_factors)
        
        # Calculate weighted overall score
        overall_score = sum(
            score * self.weights.get(category, 0)
            for category, score in component_scores.items()
        )
        
        # Determine risk level
        overall_level = self._score_to_level(overall_score)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            component_scores, contributing_factors
        )
        
        return RiskScore(
            entity_id=workspace_id,
            entity_type="workspace",
            overall_score=overall_score,
            overall_level=overall_level,
            component_scores=component_scores,
            contributing_factors=contributing_factors,
            computed_at=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
            recommendations=recommendations
        )

    async def generate_heatmap(
        self,
        workspace_id: str,
        modules: List[Dict[str, Any]]
    ) -> RiskHeatmap:
        """
        Generate risk heatmap by module.
        
        Args:
            workspace_id: Workspace to analyze
            modules: List of modules with metadata
        """
        cells = []
        max_score = 0.0
        total_score = 0.0
        critical_modules = []
        
        for module in modules:
            module_id = module.get("module_id", "unknown")
            module_name = module.get("name", module_id)
            
            # Calculate per-module risk
            stale_count = module.get("stale_evidence_count", 0)
            pending_count = module.get("pending_decisions", 0)
            change_count = module.get("recent_changes", 0)
            
            # Simple risk formula for module
            risk_score = min(100.0, (
                stale_count * 15.0 +
                pending_count * 10.0 +
                change_count * 5.0
            ))
            
            risk_level = self._score_to_level(risk_score)
            
            cell = RiskHeatmapCell(
                module_id=module_id,
                module_name=module_name,
                risk_score=risk_score,
                risk_level=risk_level,
                stale_evidence_count=stale_count,
                pending_decisions_count=pending_count,
                recent_changes_count=change_count
            )
            cells.append(cell)
            
            max_score = max(max_score, risk_score)
            total_score += risk_score
            
            if risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                critical_modules.append(module_id)
        
        avg_score = total_score / len(cells) if cells else 0.0
        
        return RiskHeatmap(
            workspace_id=workspace_id,
            generated_at=datetime.now(timezone.utc),
            cells=cells,
            max_risk_score=max_score,
            avg_risk_score=avg_score,
            critical_modules=critical_modules
        )

    # ========== Private Methods ==========

    async def _calculate_staleness_score(
        self,
        evidence: List[Dict]
    ) -> tuple[float, List[str]]:
        """Calculate staleness risk score."""
        if not evidence:
            return 0.0, []
        
        stale_count = sum(1 for e in evidence if e.get("is_stale", False))
        ratio = stale_count / len(evidence)
        score = ratio * 100.0
        
        factors = []
        if ratio > 0.5:
            factors.append(f"High staleness: {stale_count}/{len(evidence)} evidence items stale")
        elif ratio > 0.2:
            factors.append(f"Moderate staleness: {stale_count} stale evidence items")
        
        return score, factors

    async def _calculate_velocity_score(
        self,
        decisions: List[Dict],
        lookback_hours: int
    ) -> tuple[float, List[str]]:
        """Calculate velocity risk score."""
        if not decisions:
            return 0.0, []
        
        # Decisions per hour
        velocity = len(decisions) / max(lookback_hours, 1)
        
        # Normal: 2-5 decisions/hour
        # Risky: > 10 decisions/hour
        factors = []
        if velocity > 10:
            score = min(100.0, velocity * 8.0)
            factors.append(f"High velocity: {velocity:.1f} decisions/hour")
        elif velocity > 5:
            score = velocity * 5.0
            factors.append(f"Elevated velocity: {velocity:.1f} decisions/hour")
        else:
            score = 0.0
        
        return score, factors

    async def _calculate_tier_score(
        self,
        decisions: List[Dict]
    ) -> tuple[float, List[str]]:
        """Calculate tier distribution risk score."""
        if not decisions:
            return 0.0, []
        
        high_tier = sum(
            1 for d in decisions
            if d.get("tier") in ["T2", "T3"]
        )
        ratio = high_tier / len(decisions)
        score = ratio * 80.0  # Max 80 for tier risk
        
        factors = []
        if ratio > 0.3:
            factors.append(f"High-tier concentration: {high_tier}/{len(decisions)} are T2/T3")
        
        return score, factors

    async def _calculate_evidence_gap_score(
        self,
        decisions: List[Dict],
        evidence: List[Dict]
    ) -> tuple[float, List[str]]:
        """Calculate evidence gap risk score."""
        if not decisions:
            return 0.0, []
        
        # Decisions without sufficient evidence
        evidence_per_decision = len(evidence) / len(decisions) if decisions else 0
        
        factors = []
        if evidence_per_decision < 1.0:
            score = (1.0 - evidence_per_decision) * 100.0
            factors.append(f"Evidence gap: {evidence_per_decision:.1f} evidence per decision")
        else:
            score = 0.0
        
        return score, factors

    def _score_to_level(self, score: float) -> RiskLevel:
        """Convert numeric score to risk level."""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        elif score >= 20:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL

    def _generate_recommendations(
        self,
        component_scores: Dict[RiskCategory, float],
        factors: List[str]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if component_scores.get(RiskCategory.STALENESS, 0) > 50:
            recommendations.append("Run fresh tests to update stale evidence")
        
        if component_scores.get(RiskCategory.VELOCITY, 0) > 50:
            recommendations.append("Consider slowing decision velocity for careful review")
        
        if component_scores.get(RiskCategory.AUTHORITY, 0) > 50:
            recommendations.append("Review high-tier decisions with additional scrutiny")
        
        if component_scores.get(RiskCategory.EVIDENCE_GAP, 0) > 50:
            recommendations.append("Collect more evidence before proceeding")
        
        return recommendations
