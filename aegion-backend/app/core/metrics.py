"""
Aegion Metrics and Tracing.

Lightweight metrics collection and request tracing.
Compatible with OpenTelemetry when available.
"""

import time
from typing import Dict, Optional, List, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from contextlib import contextmanager
from functools import wraps
import asyncio

from .time import TimeAuthority
from .cloud_logging import cloud_logger, request_id_var


@dataclass
class MetricPoint:
    """Single metric data point."""
    name: str
    value: float
    timestamp: str
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


class MetricsCollector:
    """
    In-memory metrics collector with periodic export.
    
    Collects:
    - Counters: Monotonically increasing values
    - Gauges: Point-in-time values
    - Histograms: Distribution of values
    - Timers: Duration measurements
    """
    
    def __init__(self):
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._labels: Dict[str, Dict[str, str]] = {}
    
    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment a counter."""
        key = self._make_key(name, labels)
        self._counters[key] += value
        if labels:
            self._labels[key] = labels
    
    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge value."""
        key = self._make_key(name, labels)
        self._gauges[key] = value
        if labels:
            self._labels[key] = labels
    
    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram value."""
        key = self._make_key(name, labels)
        self._histograms[key].append(value)
        if labels:
            self._labels[key] = labels
        
        # Prevent unbounded growth
        if len(self._histograms[key]) > 10000:
            self._histograms[key] = self._histograms[key][-5000:]
    
    @contextmanager
    def timer(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Context manager to time operations."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            self.histogram(f"{name}_duration_ms", duration_ms, labels)
            self.increment(f"{name}_total", labels=labels)
    
    def timed(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Decorator to time function execution."""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                with self.timer(name, labels):
                    return await func(*args, **kwargs)
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self.timer(name, labels):
                    return func(*args, **kwargs)
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper
        return decorator
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        stats = {
            "timestamp": TimeAuthority.now(),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {},
        }
        
        # Calculate histogram stats
        for key, values in self._histograms.items():
            if values:
                sorted_values = sorted(values)
                n = len(sorted_values)
                stats["histograms"][key] = {
                    "count": n,
                    "min": sorted_values[0],
                    "max": sorted_values[-1],
                    "avg": sum(values) / n,
                    "p50": sorted_values[n // 2],
                    "p95": sorted_values[int(n * 0.95)] if n >= 20 else sorted_values[-1],
                    "p99": sorted_values[int(n * 0.99)] if n >= 100 else sorted_values[-1],
                }
        
        return stats
    
    def export_to_log(self):
        """Export metrics to logging system."""
        stats = self.get_stats()
        
        for name, value in stats["counters"].items():
            cloud_logger.metric(name, value, labels=self._labels.get(name, {}))
        
        for name, value in stats["gauges"].items():
            cloud_logger.metric(name, value, labels=self._labels.get(name, {}))
        
        for name, hist_stats in stats["histograms"].items():
            for stat_name, stat_value in hist_stats.items():
                cloud_logger.metric(
                    f"{name}_{stat_name}", 
                    stat_value,
                    labels=self._labels.get(name, {})
                )
    
    def reset(self):
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._labels.clear()
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create unique key for metric with labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


class RequestTracer:
    """
    Lightweight request tracing.
    
    Creates spans for operations and tracks request flow.
    """
    
    def __init__(self, metrics: MetricsCollector):
        self.metrics = metrics
        self._active_spans: Dict[str, dict] = {}
    
    @contextmanager
    def span(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Create a tracing span."""
        span_id = f"{request_id_var.get() or 'unknown'}:{name}:{time.time()}"
        start = time.perf_counter()
        
        span_data = {
            "name": name,
            "start_time": TimeAuthority.now(),
            "labels": labels or {},
        }
        self._active_spans[span_id] = span_data
        
        try:
            yield span_data
            span_data["status"] = "ok"
        except Exception as e:
            span_data["status"] = "error"
            span_data["error"] = str(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            span_data["duration_ms"] = duration_ms
            
            # Record metrics
            self.metrics.histogram(
                f"span_{name}_duration_ms",
                duration_ms,
                labels=labels
            )
            
            if span_data.get("status") == "error":
                self.metrics.increment(f"span_{name}_errors", labels=labels)
            
            del self._active_spans[span_id]
    
    def traced(self, name: Optional[str] = None, labels: Optional[Dict[str, str]] = None):
        """Decorator to trace function execution."""
        def decorator(func):
            span_name = name or func.__name__
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                with self.span(span_name, labels):
                    return await func(*args, **kwargs)
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self.span(span_name, labels):
                    return func(*args, **kwargs)
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper
        return decorator


# Global instances
metrics = MetricsCollector()
tracer = RequestTracer(metrics)


# Pre-defined application metrics
class AppMetrics:
    """Standard application metrics."""
    
    @staticmethod
    def request_received(method: str, path: str):
        metrics.increment("http_requests_total", labels={"method": method, "path": path})
    
    @staticmethod
    def request_completed(method: str, path: str, status: int, duration_ms: float):
        metrics.increment(
            "http_requests_completed",
            labels={"method": method, "path": path, "status": str(status)}
        )
        metrics.histogram(
            "http_request_duration_ms",
            duration_ms,
            labels={"method": method, "path": path}
        )
    
    @staticmethod
    def proposal_created(tier: str):
        metrics.increment("proposals_created_total", labels={"tier": tier})
    
    @staticmethod
    def decision_made(tier: str, outcome: str):
        metrics.increment("decisions_total", labels={"tier": tier, "outcome": outcome})
    
    @staticmethod
    def ai_inference(model: str, duration_ms: float):
        metrics.histogram("ai_inference_duration_ms", duration_ms, labels={"model": model})
        metrics.increment("ai_inferences_total", labels={"model": model})
    
    @staticmethod
    def session_active(count: int):
        metrics.gauge("sessions_active", count)
    
    @staticmethod
    def error_occurred(error_type: str):
        metrics.increment("errors_total", labels={"type": error_type})


class ChronosMetrics:
    """Metrics for Architecture Timeline & Data Foundation."""

    @staticmethod
    def event_appended(event_type: str, workspace_id: str):
        metrics.increment("chronos_events_appended_total", labels={"type": event_type, "workspace": workspace_id})

    @staticmethod
    def conflict_detected(workspace_id: str):
        metrics.increment("chronos_concurrency_conflicts_total", labels={"workspace": workspace_id})

    @staticmethod
    def hydration_complete(duration_ms: float, event_count: int, workspace_id: str):
        metrics.histogram("chronos_hydration_duration_ms", duration_ms, labels={"workspace": workspace_id})
        metrics.gauge("chronos_hydration_event_count", event_count, labels={"workspace": workspace_id})


class RepoMetrics:
    """Metrics for Repo Intelligence."""
    
    @staticmethod
    def scan_duration(duration_ms: float, workspace_id: str, file_count: int):
        metrics.histogram("repo_scan_duration_ms", duration_ms, labels={"workspace": workspace_id})
        metrics.gauge("repo_files_scanned_last", file_count, labels={"workspace": workspace_id})
        metrics.increment("repo_scans_total", labels={"workspace": workspace_id})

    @staticmethod
    def context_built(duration_ms: float, workspace_id: str, file_count: int, size_bytes: int):
        metrics.histogram("repo_context_build_duration_ms", duration_ms, labels={"workspace": workspace_id})
        metrics.histogram("repo_context_size_bytes", size_bytes, labels={"workspace": workspace_id})
        metrics.increment("repo_context_packages_built_total", labels={"workspace": workspace_id})


