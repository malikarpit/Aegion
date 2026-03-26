"""
Aegion Sentinel Advanced Drift Forecasting.

Phase 5: Statistical Anomaly Detection & Predictive Analytics.
Uses EWMA, Z-scores, and trend analysis for advanced drift forecasting.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import timezone, datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import math

from ...contracts.risk import DriftType, DriftSignal, RiskLevel
from ...core.logging import logger


class TrendDirection(str, Enum):
    """Trend direction over time."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


class AnomalyType(str, Enum):
    """Types of statistical anomalies."""
    SPIKE = "spike"
    DIP = "dip"
    LEVEL_SHIFT = "level_shift"
    TREND_CHANGE = "trend_change"
    SEASONALITY_BREAK = "seasonality_break"


@dataclass
class TimeSeriesPoint:
    """Single point in a time series."""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StatisticalAnomaly:
    """Detected statistical anomaly."""
    anomaly_id: str
    anomaly_type: AnomalyType
    timestamp: datetime
    observed_value: float
    expected_value: float
    z_score: float
    severity: RiskLevel
    description: str
    confidence: float  # 0-1


@dataclass
class TrendForecast:
    """Forecasted trend with prediction intervals."""
    metric_name: str
    current_value: float
    predicted_value: float
    prediction_interval_low: float
    prediction_interval_high: float
    trend_direction: TrendDirection
    forecast_horizon_hours: int
    confidence: float
    will_breach_threshold: bool
    breach_threshold: Optional[float] = None
    estimated_breach_time: Optional[datetime] = None


@dataclass
class DriftForecastReport:
    """Complete drift forecast report."""
    workspace_id: str
    generated_at: datetime
    anomalies: List[StatisticalAnomaly]
    forecasts: List[TrendForecast]
    overall_risk_score: float
    risk_trend: TrendDirection
    requires_attention: bool
    attention_reasons: List[str]


class StatisticalDriftForecaster:
    """
    Advanced drift forecasting using statistical methods.
    
    Doctrine: "Predict drift before it becomes crisis."
    
    Methods:
    - EWMA (Exponentially Weighted Moving Average)
    - Z-score anomaly detection
    - Linear trend analysis with confidence intervals
    - Seasonality detection
    """
    
    def __init__(
        self,
        ewma_alpha: float = 0.3,         # EWMA smoothing factor
        z_threshold: float = 2.0,         # Z-score threshold for anomalies
        min_samples: int = 10,            # Minimum samples for analysis
        forecast_horizon_hours: int = 24  # Default forecast horizon
    ):
        self.ewma_alpha = ewma_alpha
        self.z_threshold = z_threshold
        self.min_samples = min_samples
        self.forecast_horizon = forecast_horizon_hours
    
    async def analyze(
        self,
        workspace_id: str,
        metrics: Dict[str, List[TimeSeriesPoint]],
        thresholds: Optional[Dict[str, float]] = None
    ) -> DriftForecastReport:
        """
        Perform comprehensive drift analysis on metrics.
        
        Args:
            workspace_id: Workspace being analyzed
            metrics: Dict of metric_name -> time series data
            thresholds: Optional breach thresholds per metric
        """
        thresholds = thresholds or {}
        anomalies = []
        forecasts = []
        attention_reasons = []
        
        for metric_name, series in metrics.items():
            if len(series) < self.min_samples:
                continue
            
            # Detect anomalies
            metric_anomalies = await self._detect_anomalies(
                metric_name, series
            )
            anomalies.extend(metric_anomalies)
            
            # Generate forecast
            threshold = thresholds.get(metric_name)
            forecast = await self._forecast_trend(
                metric_name, series, threshold
            )
            if forecast:
                forecasts.append(forecast)
                
                if forecast.will_breach_threshold:
                    attention_reasons.append(
                        f"{metric_name} predicted to breach threshold in {forecast.forecast_horizon_hours}h"
                    )
        
        # Calculate overall risk
        critical_anomalies = sum(1 for a in anomalies if a.severity == RiskLevel.CRITICAL)
        high_anomalies = sum(1 for a in anomalies if a.severity == RiskLevel.HIGH)
        breach_forecasts = sum(1 for f in forecasts if f.will_breach_threshold)
        
        overall_risk = min(1.0, (
            critical_anomalies * 0.3 +
            high_anomalies * 0.15 +
            breach_forecasts * 0.2
        ))
        
        # Determine trend
        risk_trend = await self._determine_overall_trend(metrics)
        
        if critical_anomalies > 0:
            attention_reasons.insert(0, f"{critical_anomalies} critical anomalies detected")
        
        return DriftForecastReport(
            workspace_id=workspace_id,
            generated_at=datetime.now(timezone.utc),
            anomalies=anomalies,
            forecasts=forecasts,
            overall_risk_score=overall_risk,
            risk_trend=risk_trend,
            requires_attention=len(attention_reasons) > 0,
            attention_reasons=attention_reasons
        )
    
    async def _detect_anomalies(
        self,
        metric_name: str,
        series: List[TimeSeriesPoint]
    ) -> List[StatisticalAnomaly]:
        """Detect statistical anomalies using EWMA and Z-scores."""
        anomalies = []
        
        if len(series) < self.min_samples:
            return anomalies
        
        # Sort by timestamp
        sorted_series = sorted(series, key=lambda p: p.timestamp)
        values = [p.value for p in sorted_series]
        
        # Calculate EWMA
        ewma = self._calculate_ewma(values)
        
        # Calculate rolling std
        rolling_std = self._calculate_rolling_std(values)
        
        # Detect anomalies
        for i in range(self.min_samples, len(sorted_series)):
            point = sorted_series[i]
            expected = ewma[i-1]  # Previous EWMA
            std = rolling_std[i-1] if rolling_std[i-1] > 0 else 1.0
            
            z_score = abs(point.value - expected) / std
            
            if z_score >= self.z_threshold:
                anomaly_type = (
                    AnomalyType.SPIKE if point.value > expected
                    else AnomalyType.DIP
                )
                
                severity = self._z_score_to_severity(z_score)
                
                anomalies.append(StatisticalAnomaly(
                    anomaly_id=f"anomaly-{metric_name}-{point.timestamp.timestamp():.0f}",
                    anomaly_type=anomaly_type,
                    timestamp=point.timestamp,
                    observed_value=point.value,
                    expected_value=expected,
                    z_score=z_score,
                    severity=severity,
                    description=f"{metric_name}: {anomaly_type.value} detected (z={z_score:.2f})",
                    confidence=min(0.99, 1 - (1 / (1 + z_score)))
                ))
        
        return anomalies
    
    async def _forecast_trend(
        self,
        metric_name: str,
        series: List[TimeSeriesPoint],
        threshold: Optional[float]
    ) -> Optional[TrendForecast]:
        """Forecast trend using linear regression."""
        if len(series) < self.min_samples:
            return None
        
        sorted_series = sorted(series, key=lambda p: p.timestamp)
        
        # Convert to numeric for regression
        base_time = sorted_series[0].timestamp
        x = [(p.timestamp - base_time).total_seconds() / 3600 for p in sorted_series]  # Hours
        y = [p.value for p in sorted_series]
        
        # Simple linear regression
        slope, intercept = self._linear_regression(x, y)
        
        # Calculate residual std
        residuals = [y[i] - (slope * x[i] + intercept) for i in range(len(x))]
        residual_std = self._std(residuals)
        
        # Current and predicted values
        current_value = y[-1]
        future_x = x[-1] + self.forecast_horizon
        predicted = slope * future_x + intercept
        
        # Prediction interval (95%)
        interval = 1.96 * residual_std
        
        # Determine trend direction
        if abs(slope) < 0.01:
            direction = TrendDirection.STABLE
        elif slope > 0:
            direction = TrendDirection.INCREASING
        else:
            direction = TrendDirection.DECREASING
        
        # Check for threshold breach
        will_breach = False
        breach_time = None
        if threshold is not None:
            if direction == TrendDirection.INCREASING and predicted > threshold:
                will_breach = True
                # Estimate breach time
                if slope > 0:
                    hours_to_breach = (threshold - current_value) / slope
                    breach_time = datetime.now(timezone.utc) + timedelta(hours=max(0, hours_to_breach))
            elif direction == TrendDirection.DECREASING and predicted < threshold:
                will_breach = True
                if slope < 0:
                    hours_to_breach = (threshold - current_value) / slope
                    breach_time = datetime.now(timezone.utc) + timedelta(hours=max(0, hours_to_breach))
        
        # Confidence based on R²
        r_squared = self._r_squared(x, y, slope, intercept)
        
        return TrendForecast(
            metric_name=metric_name,
            current_value=current_value,
            predicted_value=predicted,
            prediction_interval_low=predicted - interval,
            prediction_interval_high=predicted + interval,
            trend_direction=direction,
            forecast_horizon_hours=self.forecast_horizon,
            confidence=r_squared,
            will_breach_threshold=will_breach,
            breach_threshold=threshold,
            estimated_breach_time=breach_time
        )
    
    async def _determine_overall_trend(
        self,
        metrics: Dict[str, List[TimeSeriesPoint]]
    ) -> TrendDirection:
        """Determine overall trend across all metrics."""
        trends = []
        
        for series in metrics.values():
            if len(series) < self.min_samples:
                continue
            
            sorted_series = sorted(series, key=lambda p: p.timestamp)
            values = [p.value for p in sorted_series]
            
            # Compare first/second half
            mid = len(values) // 2
            first_half_mean = sum(values[:mid]) / mid
            second_half_mean = sum(values[mid:]) / (len(values) - mid)
            
            change = (second_half_mean - first_half_mean) / first_half_mean if first_half_mean != 0 else 0
            trends.append(change)
        
        if not trends:
            return TrendDirection.STABLE
        
        avg_change = sum(trends) / len(trends)
        volatility = self._std(trends)
        
        if volatility > 0.3:
            return TrendDirection.VOLATILE
        elif avg_change > 0.1:
            return TrendDirection.INCREASING
        elif avg_change < -0.1:
            return TrendDirection.DECREASING
        else:
            return TrendDirection.STABLE
    
    # ========== Statistical Helpers ==========
    
    def _calculate_ewma(self, values: List[float]) -> List[float]:
        """Calculate Exponentially Weighted Moving Average."""
        ewma = [values[0]]
        for i in range(1, len(values)):
            ewma.append(self.ewma_alpha * values[i] + (1 - self.ewma_alpha) * ewma[-1])
        return ewma
    
    def _calculate_rolling_std(self, values: List[float], window: int = 10) -> List[float]:
        """Calculate rolling standard deviation."""
        result = []
        for i in range(len(values)):
            start = max(0, i - window + 1)
            window_vals = values[start:i+1]
            result.append(self._std(window_vals))
        return result
    
    def _std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(variance)
    
    def _linear_regression(self, x: List[float], y: List[float]) -> Tuple[float, float]:
        """Simple linear regression returning (slope, intercept)."""
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(xi ** 2 for xi in x)
        
        denom = n * sum_x2 - sum_x ** 2
        if denom == 0:
            return 0.0, sum_y / n if n > 0 else 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        
        return slope, intercept
    
    def _r_squared(self, x: List[float], y: List[float], slope: float, intercept: float) -> float:
        """Calculate R² for regression."""
        mean_y = sum(y) / len(y)
        ss_tot = sum((yi - mean_y) ** 2 for yi in y)
        ss_res = sum((y[i] - (slope * x[i] + intercept)) ** 2 for i in range(len(y)))
        
        if ss_tot == 0:
            return 1.0
        
        return max(0, 1 - ss_res / ss_tot)
    
    def _z_score_to_severity(self, z_score: float) -> RiskLevel:
        """Convert Z-score to severity level."""
        if z_score >= 4.0:
            return RiskLevel.CRITICAL
        elif z_score >= 3.0:
            return RiskLevel.HIGH
        elif z_score >= 2.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


# Singleton accessor
_forecaster: Optional[StatisticalDriftForecaster] = None

def get_drift_forecaster() -> StatisticalDriftForecaster:
    """Get singleton drift forecaster instance."""
    global _forecaster
    if _forecaster is None:
        _forecaster = StatisticalDriftForecaster()
    return _forecaster
