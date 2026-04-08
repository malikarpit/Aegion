import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.api.v1.analytics import get_sentinel_alerts, get_drift_status
from app.services.sentinel.risk_engine import RiskScore, RiskLevel
from app.services.sentinel.drift_detector import DriftReport, DriftSignal, DriftType

def test_get_sentinel_alerts_schema_sync():
    """Synchronous wrapper for async alerts schema test."""
    asyncio.run(_test_get_sentinel_alerts_schema())

def test_get_drift_status_sync():
    """Synchronous wrapper for async drift status test."""
    asyncio.run(_test_get_drift_status())

async def _test_get_drift_status():
    """Verify get_drift_status returns correct status based on report."""
    with patch("app.api.v1.analytics._drift_detector") as mock_drift_detector:
        # Setup Drift Mock
        mock_drift_report = MagicMock(spec=DriftReport)
        mock_drift_report.requires_attention = True
        mock_drift_report.critical_signals = 1
        mock_drift_report.total_signals = 5
        mock_drift_report.generated_at = datetime.now(timezone.utc)
        
        mock_drift_detector.detect_drift = AsyncMock(return_value=mock_drift_report)
        
        # Execute
        response = await get_drift_status(workspace_id="ws-test")
        
        # Verify
        assert response["workspace_id"] == "ws-test"
        assert response["status"] == "degraded"
        assert response["signals_count"] == 5
        assert "last_check" in response

async def _test_get_sentinel_alerts_schema():
    """Verify get_sentinel_alerts returns correct schema and awaits dependencies."""
    
    # Mock dependencies
    with patch("app.api.v1.analytics._drift_detector") as mock_drift_detector, \
         patch("app.api.v1.analytics._risk_engine") as mock_risk_engine:
        
        # Setup Drift Mock
        mock_drift_report = MagicMock(spec=DriftReport)
        mock_drift_report.signals = [
            DriftSignal(
                signal_id="drift-1",
                drift_type=DriftType.EVIDENCE_DECLINE,
                severity=RiskLevel.CRITICAL,
                baseline_value=0.0,
                current_value=1.0,
                deviation_percent=100.0,
                workspace_id="ws-test",
                description="Critical drift detected"
            )
        ]
        
        # IMPORTANT: Mock as async to verify await usage in implementation
        mock_drift_detector.detect_drift = AsyncMock(return_value=mock_drift_report)
        
        # Setup Risk Mock
        mock_risk_score = RiskScore(
            entity_id="ws-test",
            entity_type="workspace",
            overall_score=85.0,
            overall_level=RiskLevel.CRITICAL,
            component_scores={},
            contributing_factors=[],
            computed_at=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc),
            recommendations=[]
        )
        mock_risk_engine.calculate_risk_score = AsyncMock(return_value=mock_risk_score)
        
        # Execute
        response = await get_sentinel_alerts(workspace_id="ws-test")
        
        # Verify await was called
        mock_drift_detector.detect_drift.assert_awaited_once()
        mock_risk_engine.calculate_risk_score.assert_awaited_once()
        
        # Verify Response Schema
        assert "alerts" in response
        alerts = response["alerts"]
        assert len(alerts) == 2  # 1 drift + 1 risk
        
        # Check specific fields matching client.ts SentinelAlert interface
        # 1. Drift Alert
        drift_alert = next(a for a in alerts if a["type"] == DriftType.EVIDENCE_DECLINE)
        assert drift_alert["alert_id"] == f"drift-{DriftType.EVIDENCE_DECLINE}"
        assert drift_alert["severity"] == "critical"
        assert drift_alert["message"] == "Critical drift detected"
        assert "timestamp" in drift_alert
        assert drift_alert["acknowledged"] is False
        
        # 2. Risk Alert
        risk_alert = next(a for a in alerts if a["type"] == "high_risk_score")
        assert risk_alert["alert_id"] == "risk-ws-test"
        assert risk_alert["severity"] == "critical"
        assert "timestamp" in risk_alert
        assert risk_alert["acknowledged"] is False
