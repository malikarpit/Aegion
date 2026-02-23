"""
Aegion Sentinel Time-Series Persistence.

Persists Sentinel/Noesis health and risk outputs as time-series history.
Enables drift detection and historical baseline comparison.
"""

from typing import Dict, List, Any, Optional
from datetime import timezone, datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import asyncio

from ...core.logging import logger


class MetricType(str, Enum):
    """Types of metrics tracked."""
    RISK_SCORE = "risk_score"
    HEALTH_SCORE = "health_score"
    STALENESS_RATIO = "staleness_ratio"
    EVIDENCE_COVERAGE = "evidence_coverage"
    GOVERNANCE_LOAD = "governance_load"
    DECISION_VELOCITY = "decision_velocity"
    APPROVAL_LATENCY = "approval_latency"


@dataclass
class TimeSeriesPoint:
    """A single point in the time series."""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimeSeriesMetric:
    """A complete time series for a metric."""
    metric_type: MetricType
    workspace_id: str
    points: List[TimeSeriesPoint] = field(default_factory=list)
    
    def add_point(self, value: float, labels: Dict[str, str] = None, metadata: Dict[str, Any] = None):
        """Add a new data point."""
        self.points.append(TimeSeriesPoint(
            timestamp=datetime.now(timezone.utc),
            value=value,
            labels=labels or {},
            metadata=metadata or {}
        ))
    
    def get_latest(self, count: int = 1) -> List[TimeSeriesPoint]:
        """Get the latest N points."""
        return sorted(self.points, key=lambda p: p.timestamp, reverse=True)[:count]
    
    def get_range(self, start: datetime, end: datetime) -> List[TimeSeriesPoint]:
        """Get points within a time range."""
        return [p for p in self.points if start <= p.timestamp <= end]
    
    def calculate_drift(self, window_hours: int = 24) -> Optional[float]:
        """
        Calculate drift from historical baseline.
        Returns percentage change from baseline.
        """
        if len(self.points) < 2:
            return None
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        recent = [p for p in self.points if p.timestamp > cutoff]
        historical = [p for p in self.points if p.timestamp <= cutoff]
        
        if not recent or not historical:
            return None
        
        recent_avg = sum(p.value for p in recent) / len(recent)
        historical_avg = sum(p.value for p in historical) / len(historical)
        
        if historical_avg == 0:
            return None
        
        return ((recent_avg - historical_avg) / historical_avg) * 100


class SentinelTimeSeriesStore:
    """
    Time-series storage for Sentinel/Noesis metrics.
    
    Provides:
    - Persisted metric history
    - Drift detection
    - Historical baselines
    - Anomaly alerting
    """
    
    def __init__(self, storage_path: str = ".aegion/timeseries"):
        self._storage_path = Path(storage_path)
        self._metrics: Dict[str, Dict[str, TimeSeriesMetric]] = {}  # workspace_id -> metric_type -> metric
        self._retention_days = 90  # Keep 90 days of history
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the time series store."""
        self._storage_path.mkdir(parents=True, exist_ok=True)
        await self._load_from_disk()
        self._initialized = True
        logger.info(f"Sentinel time-series store initialized at {self._storage_path}")
    
    async def _load_from_disk(self) -> None:
        """Load persisted metrics from disk."""
        for workspace_dir in self._storage_path.iterdir():
            if workspace_dir.is_dir():
                workspace_id = workspace_dir.name
                self._metrics[workspace_id] = {}
                
                for metric_file in workspace_dir.glob("*.json"):
                    try:
                        data = json.loads(await asyncio.to_thread(metric_file.read_text))
                        metric_type = MetricType(data["metric_type"])
                        
                        points = [
                            TimeSeriesPoint(
                                timestamp=datetime.fromisoformat(p["timestamp"]),
                                value=p["value"],
                                labels=p.get("labels", {}),
                                metadata=p.get("metadata", {})
                            )
                            for p in data["points"]
                        ]
                        
                        self._metrics[workspace_id][metric_type.value] = TimeSeriesMetric(
                            metric_type=metric_type,
                            workspace_id=workspace_id,
                            points=points
                        )
                    except Exception as e:
                        logger.error(f"Failed to load metric file {metric_file}: {e}")
    
    async def _persist_metric(self, workspace_id: str, metric: TimeSeriesMetric) -> None:
        """Persist a metric to disk."""
        workspace_dir = self._storage_path / workspace_id
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        metric_file = workspace_dir / f"{metric.metric_type.value}.json"
        data = {
            "metric_type": metric.metric_type.value,
            "workspace_id": workspace_id,
            "points": [
                {
                    "timestamp": p.timestamp.isoformat(),
                    "value": p.value,
                    "labels": p.labels,
                    "metadata": p.metadata
                }
                for p in metric.points
            ]
        }
        
        await asyncio.to_thread(
            metric_file.write_text,
            json.dumps(data, indent=2, default=str)
        )
    
    # ========== Write Operations ==========
    
    async def record_risk_score(
        self,
        workspace_id: str,
        score: float,
        risk_factors: Dict[str, float] = None
    ) -> None:
        """Record a risk score observation."""
        await self._record_metric(
            workspace_id,
            MetricType.RISK_SCORE,
            score,
            metadata={"risk_factors": risk_factors or {}}
        )
    
    async def record_health_score(
        self,
        workspace_id: str,
        score: float,
        component_scores: Dict[str, float] = None
    ) -> None:
        """Record a health score observation."""
        await self._record_metric(
            workspace_id,
            MetricType.HEALTH_SCORE,
            score,
            metadata={"component_scores": component_scores or {}}
        )
    
    async def record_staleness_ratio(
        self,
        workspace_id: str,
        ratio: float,
        stale_count: int = 0,
        total_count: int = 0
    ) -> None:
        """Record staleness ratio."""
        await self._record_metric(
            workspace_id,
            MetricType.STALENESS_RATIO,
            ratio,
            metadata={"stale_count": stale_count, "total_count": total_count}
        )
    
    async def record_evidence_coverage(
        self,
        workspace_id: str,
        coverage: float,
        decisions_with_evidence: int = 0,
        total_decisions: int = 0
    ) -> None:
        """Record evidence coverage ratio."""
        await self._record_metric(
            workspace_id,
            MetricType.EVIDENCE_COVERAGE,
            coverage,
            metadata={
                "decisions_with_evidence": decisions_with_evidence,
                "total_decisions": total_decisions
            }
        )
    
    async def record_governance_load(
        self,
        workspace_id: str,
        pending_count: int,
        tier_breakdown: Dict[str, int] = None
    ) -> None:
        """Record governance load (pending approvals)."""
        await self._record_metric(
            workspace_id,
            MetricType.GOVERNANCE_LOAD,
            float(pending_count),
            metadata={"tier_breakdown": tier_breakdown or {}}
        )
    
    async def record_decision_velocity(
        self,
        workspace_id: str,
        decisions_per_hour: float
    ) -> None:
        """Record decision velocity."""
        await self._record_metric(
            workspace_id,
            MetricType.DECISION_VELOCITY,
            decisions_per_hour
        )
    
    async def record_approval_latency(
        self,
        workspace_id: str,
        latency_seconds: float,
        tier: str = None
    ) -> None:
        """Record approval latency."""
        await self._record_metric(
            workspace_id,
            MetricType.APPROVAL_LATENCY,
            latency_seconds,
            labels={"tier": tier} if tier else {}
        )
    
    async def _record_metric(
        self,
        workspace_id: str,
        metric_type: MetricType,
        value: float,
        labels: Dict[str, str] = None,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Internal method to record a metric."""
        if workspace_id not in self._metrics:
            self._metrics[workspace_id] = {}
        
        if metric_type.value not in self._metrics[workspace_id]:
            self._metrics[workspace_id][metric_type.value] = TimeSeriesMetric(
                metric_type=metric_type,
                workspace_id=workspace_id
            )
        
        metric = self._metrics[workspace_id][metric_type.value]
        metric.add_point(value, labels, metadata)
        
        # Persist to disk
        await self._persist_metric(workspace_id, metric)
        
        # Check for drift and alert
        drift = metric.calculate_drift()
        if drift is not None and abs(drift) > 20:  # 20% drift threshold
            logger.warning(
                f"Drift detected for {metric_type.value} in {workspace_id}: {drift:.1f}%"
            )
    
    # ========== Read Operations ==========
    
    async def get_metric_history(
        self,
        workspace_id: str,
        metric_type: MetricType,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get metric history for the specified time range."""
        if workspace_id not in self._metrics:
            return []
        
        if metric_type.value not in self._metrics[workspace_id]:
            return []
        
        metric = self._metrics[workspace_id][metric_type.value]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        return [
            {
                "timestamp": p.timestamp.isoformat(),
                "value": p.value,
                "labels": p.labels,
                "metadata": p.metadata
            }
            for p in metric.points
            if p.timestamp > cutoff
        ]
    
    async def get_drift_report(
        self,
        workspace_id: str,
        baseline_hours: int = 168  # 1 week
    ) -> Dict[str, Any]:
        """Get drift report for all metrics."""
        if workspace_id not in self._metrics:
            return {"workspace_id": workspace_id, "drifts": {}}
        
        drifts = {}
        for metric_type, metric in self._metrics[workspace_id].items():
            drift = metric.calculate_drift(baseline_hours)
            drifts[metric_type] = {
                "drift_percentage": drift,
                "current_value": metric.get_latest(1)[0].value if metric.points else None,
                "alert": drift is not None and abs(drift) > 20
            }
        
        return {
            "workspace_id": workspace_id,
            "baseline_hours": baseline_hours,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "drifts": drifts
        }
    
    async def get_historical_baseline(
        self,
        workspace_id: str,
        metric_type: MetricType,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get historical baseline statistics."""
        if workspace_id not in self._metrics:
            return {}
        
        if metric_type.value not in self._metrics[workspace_id]:
            return {}
        
        metric = self._metrics[workspace_id][metric_type.value]
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        points = [p for p in metric.points if p.timestamp > cutoff]
        
        if not points:
            return {}
        
        values = [p.value for p in points]
        return {
            "metric_type": metric_type.value,
            "period_days": days,
            "point_count": len(points),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": points[-1].value if points else None
        }
    
    # ========== Maintenance ==========
    
    async def cleanup_old_data(self) -> int:
        """Remove data older than retention period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        removed_count = 0
        
        for workspace_id, metrics in self._metrics.items():
            for metric_type, metric in metrics.items():
                original_count = len(metric.points)
                metric.points = [p for p in metric.points if p.timestamp > cutoff]
                removed_count += original_count - len(metric.points)
                
                await self._persist_metric(workspace_id, metric)
        
        logger.info(f"Cleaned up {removed_count} old time-series points")
        return removed_count


# Singleton instance
_sentinel_timeseries: Optional[SentinelTimeSeriesStore] = None


def get_sentinel_timeseries() -> SentinelTimeSeriesStore:
    """Get the Sentinel time-series store singleton."""
    global _sentinel_timeseries
    if _sentinel_timeseries is None:
        _sentinel_timeseries = SentinelTimeSeriesStore()
    return _sentinel_timeseries
