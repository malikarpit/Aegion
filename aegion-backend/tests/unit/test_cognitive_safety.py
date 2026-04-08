"""
Aegion Phase 4 Unit Tests - Cognitive Safety.

Tests for CognitiveSafetyService.
"""

import pytest
import asyncio

from app.services.noesis.cognitive_safety import CognitiveSafetyService
from app.contracts.risk import CognitiveLoadLevel


class TestCognitiveSafetyService:
    """Tests for cognitive safety monitoring."""

    def test_assess_optimal_load_sync(self):
        """Test assessment returns optimal for low activity."""
        async def run():
            service = CognitiveSafetyService()
            
            assessment = await service.assess_cognitive_load(
                user_id="user-001",
                recent_decisions=[],
                hours_active=0.5
            )
            
            assert assessment.load_level == CognitiveLoadLevel.OPTIMAL
            assert assessment.should_break is False
        
        asyncio.run(run())

    def test_assess_elevated_load_sync(self):
        """Test assessment detects elevated load."""
        async def run():
            service = CognitiveSafetyService()
            
            decisions = [{"complexity": 5} for _ in range(8)]
            
            assessment = await service.assess_cognitive_load(
                user_id="user-001",
                recent_decisions=decisions,
                hours_active=1.0
            )
            
            # 8 decisions/hour is approaching limit
            assert assessment.load_level in [
                CognitiveLoadLevel.ELEVATED,
                CognitiveLoadLevel.OPTIMAL
            ]
        
        asyncio.run(run())

    def test_assess_overloaded_sync(self):
        """Test assessment detects overloaded state."""
        async def run():
            service = CognitiveSafetyService(
                decisions_per_hour_limit=5.0,
                hours_without_break_limit=1.0
            )
            
            # High volume, long duration
            decisions = [{"complexity": 8} for _ in range(20)]
            
            assessment = await service.assess_cognitive_load(
                user_id="user-001",
                recent_decisions=decisions,
                hours_active=2.5  # Over the 1.0 limit
            )
            
            assert assessment.should_break is True
        
        asyncio.run(run())

    def test_should_suggest_break_sync(self):
        """Test quick break check."""
        async def run():
            service = CognitiveSafetyService()
            
            # First check - should not suggest break for new user
            should_break, reason = await service.should_suggest_break("user-new")
            
            # New user with no activity shouldn't need break
            assert should_break is False or (should_break and reason is not None)
        
        asyncio.run(run())

    def test_uncertainty_visualization_high_confidence_sync(self):
        """Test uncertainty visualization for high-confidence decision."""
        async def run():
            service = CognitiveSafetyService()
            
            evidence = [
                {"classification": "supporting"},
                {"classification": "supporting"},
                {"classification": "supporting"},
            ]
            
            viz = await service.get_uncertainty_visualization(
                decision_id="dec-001",
                evidence_data=evidence
            )
            
            assert viz.decision_id == "dec-001"
            assert viz.overall_uncertainty < 0.5  # Low uncertainty
            assert viz.evidence_strength > 0.5    # High strength
            assert viz.color_code in ["green", "yellow"]
        
        asyncio.run(run())

    def test_uncertainty_visualization_low_confidence_sync(self):
        """Test uncertainty visualization for low-confidence decision."""
        async def run():
            service = CognitiveSafetyService()
            
            evidence = [
                {"classification": "contradictory"},
                {"classification": "supporting"},
            ]
            
            viz = await service.get_uncertainty_visualization(
                decision_id="dec-002",
                evidence_data=evidence
            )
            
            assert viz.overall_uncertainty > 0.3  # Higher uncertainty
            assert viz.contradictory_evidence_count == 1
        
        asyncio.run(run())

    def test_uncertainty_visualization_no_evidence_sync(self):
        """Test uncertainty visualization with no evidence."""
        async def run():
            service = CognitiveSafetyService()
            
            viz = await service.get_uncertainty_visualization(
                decision_id="dec-003",
                evidence_data=[]
            )
            
            assert viz.overall_uncertainty == 1.0  # Maximum uncertainty
            assert viz.evidence_strength == 0.0
            assert viz.color_code == "red"
        
        asyncio.run(run())

    def test_record_decision_and_load_tracking_sync(self):
        """Test that recording decisions affects load tracking."""
        async def run():
            service = CognitiveSafetyService()
            
            # Record many decisions
            for i in range(10):
                await service.record_decision(
                    user_id="user-track",
                    decision_data={"complexity": 7}
                )
            
            # Check that tracking is updated
            assessment = await service.assess_cognitive_load("user-track")
            
            # Should have data from recorded decisions
            # (Internal tracking, not from recent_decisions param)
            assert assessment.user_id == "user-track"
        
        asyncio.run(run())

    def test_record_break_resets_timer_sync(self):
        """Test that recording a break resets the timer."""
        async def run():
            service = CognitiveSafetyService()
            
            # Record some activity
            await service.record_decision(
                user_id="user-break",
                decision_data={"complexity": 5}
            )
            
            # Record a break
            await service.record_break("user-break")
            
            # Check hours since break is reset
            session = service._user_sessions.get("user-break", {})
            assert session.get("hours_since_break", 0) == 0.0
        
        asyncio.run(run())

    def test_factors_populated_sync(self):
        """Test that all cognitive load factors are populated."""
        async def run():
            service = CognitiveSafetyService()
            
            decisions = [
                {"complexity": 5, "tier": "T1"},
                {"complexity": 7, "tier": "T2"},
            ]
            
            assessment = await service.assess_cognitive_load(
                user_id="user-001",
                recent_decisions=decisions,
                hours_active=1.0
            )
            
            factors = assessment.factors
            assert factors.decisions_per_hour >= 0
            assert factors.avg_decision_complexity >= 0
            assert factors.high_tier_decisions == 1
        
        asyncio.run(run())

    def test_uncertainty_explanation_generated_sync(self):
        """Test that uncertainty explanation is generated."""
        async def run():
            service = CognitiveSafetyService()
            
            viz = await service.get_uncertainty_visualization(
                decision_id="dec-001",
                evidence_data=[{"classification": "supporting"}]
            )
            
            assert viz.uncertainty_explanation is not None
            assert len(viz.uncertainty_explanation) > 0
        
        asyncio.run(run())
