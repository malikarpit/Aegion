"""
Aegion Phase 4 Unit Tests - Sentinel Services.

Tests for RiskEngine and DriftDetector.
"""

import pytest
import asyncio
from datetime import datetime

from app.services.sentinel import RiskEngine, DriftDetector
from app.contracts.risk import RiskLevel, RiskCategory, DriftType


class TestRiskEngine:
    """Tests for the Sentinel risk engine."""

    def test_calculate_risk_score_empty_data_sync(self):
        """Test risk calculation with no data."""
        async def run():
            engine = RiskEngine()
            
            score = await engine.calculate_risk_score(
                workspace_id="ws-test",
                decisions=[],
                evidence=[]
            )
            
            assert score.entity_id == "ws-test"
            assert score.overall_level == RiskLevel.MINIMAL
            assert score.overall_score < 20
        
        asyncio.run(run())

    def test_calculate_risk_score_with_stale_evidence_sync(self):
        """Test risk increases with stale evidence."""
        async def run():
            engine = RiskEngine()
            
            evidence = [
                {"is_stale": True},
                {"is_stale": True},
                {"is_stale": False},
            ]
            
            score = await engine.calculate_risk_score(
                workspace_id="ws-test",
                decisions=[],
                evidence=evidence
            )
            
            # 2/3 = 66% stale - high risk
            assert score.component_scores[RiskCategory.STALENESS] > 50
            assert len(score.contributing_factors) > 0
        
        asyncio.run(run())

    def test_calculate_risk_score_high_velocity_sync(self):
        """Test risk increases with high decision velocity."""
        async def run():
            engine = RiskEngine()
            
            # 15 decisions in 1 hour = high velocity
            decisions = [{"id": f"dec-{i}"} for i in range(15)]
            
            score = await engine.calculate_risk_score(
                workspace_id="ws-test",
                decisions=decisions,
                evidence=[],
                lookback_hours=1
            )
            
            assert score.component_scores[RiskCategory.VELOCITY] > 50
        
        asyncio.run(run())

    def test_calculate_risk_score_high_tier_concentration_sync(self):
        """Test risk increases with high-tier decision concentration."""
        async def run():
            engine = RiskEngine()
            
            decisions = [
                {"tier": "T2"},
                {"tier": "T2"},
                {"tier": "T3"},
                {"tier": "T1"},
                {"tier": "T1"},
            ]
            
            score = await engine.calculate_risk_score(
                workspace_id="ws-test",
                decisions=decisions,
                evidence=[]
            )
            
            # 3/5 high-tier: (2*10 + 1*25)/5 = 9.0 (normalized by total decisions)
            assert score.component_scores[RiskCategory.AUTHORITY] > 5
        
        asyncio.run(run())

    def test_generate_heatmap_sync(self):
        """Test heatmap generation."""
        async def run():
            engine = RiskEngine()
            
            modules = [
                {
                    "module_id": "mod-auth",
                    "name": "Authentication",
                    "stale_evidence_count": 5,
                    "pending_decisions": 2,
                    "recent_changes": 10
                },
                {
                    "module_id": "mod-db",
                    "name": "Database",
                    "stale_evidence_count": 0,
                    "pending_decisions": 1,
                    "recent_changes": 2
                }
            ]
            
            heatmap = await engine.generate_heatmap("ws-test", modules)
            
            assert heatmap.workspace_id == "ws-test"
            assert len(heatmap.cells) == 2
            
            # Authentication should have higher risk
            auth_cell = next(c for c in heatmap.cells if c.module_id == "mod-auth")
            db_cell = next(c for c in heatmap.cells if c.module_id == "mod-db")
            
            assert auth_cell.risk_score > db_cell.risk_score
        
        asyncio.run(run())

    def test_recommendations_generated_sync(self):
        """Test that recommendations are generated for high-risk areas."""
        async def run():
            engine = RiskEngine()
            
            evidence = [{"is_stale": True} for _ in range(10)]
            
            score = await engine.calculate_risk_score(
                workspace_id="ws-test",
                decisions=[],
                evidence=evidence
            )
            
            assert len(score.recommendations) > 0
            assert any("stale" in r.lower() for r in score.recommendations)
        
        asyncio.run(run())


class TestDriftDetector:
    """Tests for the Sentinel drift detector."""

    def test_no_drift_detected_sync(self):
        """Test no drift when baseline equals current."""
        async def run():
            detector = DriftDetector()
            
            baseline = [{"id": "dec-1"}, {"id": "dec-2"}]
            current = [{"id": "dec-3"}, {"id": "dec-4"}]
            
            report = await detector.detect_drift(
                workspace_id="ws-test",
                current_period=current,
                baseline_period=baseline,
                observation_hours=24
            )
            
            assert report.total_signals == 0
            assert report.requires_attention is False
        
        asyncio.run(run())

    def test_velocity_increase_drift_sync(self):
        """Test detection of velocity increase."""
        async def run():
            detector = DriftDetector()
            
            baseline = [{"id": f"dec-{i}"} for i in range(5)]
            current = [{"id": f"dec-{i}"} for i in range(15)]  # 3x increase
            
            report = await detector.detect_drift(
                workspace_id="ws-test",
                current_period=current,
                baseline_period=baseline,
                observation_hours=24
            )
            
            velocity_signals = [
                s for s in report.signals
                if s.drift_type == DriftType.VELOCITY_INCREASE
            ]
            assert len(velocity_signals) == 1
        
        asyncio.run(run())

    def test_evidence_decline_drift_sync(self):
        """Test detection of evidence decline."""
        async def run():
            detector = DriftDetector()
            
            baseline = [
                {"evidence_ids": ["e1", "e2", "e3"]},
                {"evidence_ids": ["e1", "e2"]},
            ]  # Avg 2.5 evidence
            
            current = [
                {"evidence_ids": ["e1"]},
                {"evidence_ids": []},
            ]  # Avg 0.5 evidence
            
            report = await detector.detect_drift(
                workspace_id="ws-test",
                current_period=current,
                baseline_period=baseline,
                observation_hours=24
            )
            
            evidence_signals = [
                s for s in report.signals
                if s.drift_type == DriftType.EVIDENCE_DECLINE
            ]
            assert len(evidence_signals) == 1
        
        asyncio.run(run())

    def test_tier_escalation_drift_sync(self):
        """Test detection of tier escalation."""
        async def run():
            detector = DriftDetector()
            
            baseline = [{"tier": "T1"} for _ in range(10)]  # 0% high-tier
            current = [{"tier": "T2"} for _ in range(5)] + [{"tier": "T1"} for _ in range(5)]  # 50% high-tier
            
            report = await detector.detect_drift(
                workspace_id="ws-test",
                current_period=current,
                baseline_period=baseline,
                observation_hours=24
            )
            
            tier_signals = [
                s for s in report.signals
                if s.drift_type == DriftType.TIER_ESCALATION
            ]
            assert len(tier_signals) == 1
        
        asyncio.run(run())

    def test_review_bypass_drift_sync(self):
        """Test detection of review bypass."""
        async def run():
            detector = DriftDetector()
            
            baseline = [{"review_count": 2} for _ in range(10)]  # 100% reviewed
            current = [{"review_count": 0} for _ in range(10)]  # 0% reviewed
            
            report = await detector.detect_drift(
                workspace_id="ws-test",
                current_period=current,
                baseline_period=baseline,
                observation_hours=24
            )
            
            review_signals = [
                s for s in report.signals
                if s.drift_type == DriftType.REVIEW_BYPASS
            ]
            assert len(review_signals) == 1
        
        asyncio.run(run())

    def test_multiple_drifts_detected_sync(self):
        """Test detection of multiple drift types simultaneously."""
        async def run():
            detector = DriftDetector()
            
            baseline = [
                {"evidence_ids": ["e1", "e2"], "tier": "T1", "review_count": 1}
                for _ in range(5)
            ]
            
            current = [
                {"evidence_ids": [], "tier": "T2", "review_count": 0}
                for _ in range(15)  # Also velocity increase
            ]
            
            report = await detector.detect_drift(
                workspace_id="ws-test",
                current_period=current,
                baseline_period=baseline,
                observation_hours=24
            )
            
            assert report.total_signals >= 3
            assert report.requires_attention is True
        
        asyncio.run(run())

    def test_report_attention_reason_sync(self):
        """Test that attention reason is populated for critical signals."""
        async def run():
            detector = DriftDetector()
            
            baseline = [{"review_count": 1} for _ in range(10)]
            current = [{"review_count": 0} for _ in range(10)]
            
            report = await detector.detect_drift(
                workspace_id="ws-test",
                current_period=current,
                baseline_period=baseline,
                observation_hours=24
            )
            
            if report.requires_attention:
                assert report.attention_reason is not None
        
        asyncio.run(run())
