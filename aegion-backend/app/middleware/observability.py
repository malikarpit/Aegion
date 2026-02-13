"""
Aegion Observability — Metrics & Tracing.

Doctrine: "What is not measured cannot be governed."

Provides:
- Prometheus-compatible metrics (counters, histograms, gauges)
- OpenTelemetry-compatible tracing spans
- Governance-specific metrics (violations, approval rates, drift)
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from collections import defaultdict
import time
import asyncio

from ..core.logging import logger


# ──────────────────────────────────────────────────────────────────────────
# Metrics (Prometheus-compatible)
# ──────────────────────────────────────────────────────────────────────────

class MetricsCollector:
    """
    In-process metrics collector compatible with Prometheus exposition format.

    Tracks:
    - Request counts by endpoint and status
    - Latency histograms
    - Governance event counts
    - AI model performance
    """

    def __init__(self):
        self._counters: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, list] = defaultdict(list)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()

    async def increment(self, name: str, value: float = 1.0, labels: Optional[Dict] = None):
        """Increment a counter metric."""
        key = self._metric_key(name, labels)
        async with self._lock:
            self._counters[key] += value

    async def observe(self, name: str, value: float, labels: Optional[Dict] = None):
        """Record a histogram observation (e.g., latency)."""
        key = self._metric_key(name, labels)
        async with self._lock:
            self._histograms[key].append(value)
            # Keep only last 10000 observations
            if len(self._histograms[key]) > 10000:
                self._histograms[key] = self._histograms[key][-5000:]

    async def set_gauge(self, name: str, value: float, labels: Optional[Dict] = None):
        """Set a gauge metric to a specific value."""
        key = self._metric_key(name, labels)
        async with self._lock:
            self._gauges[key] = value

    def _metric_key(self, name: str, labels: Optional[Dict] = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    async def export_prometheus(self) -> str:
        """Export metrics in Prometheus exposition format."""
        lines = []
        async with self._lock:
            for key, value in sorted(self._counters.items()):
                lines.append(f"aegion_{key} {value}")
            for key, observations in sorted(self._histograms.items()):
                if observations:
                    lines.append(f'aegion_{key}_count {len(observations)}')
                    lines.append(f'aegion_{key}_sum {sum(observations):.4f}')
                    lines.append(f'aegion_{key}_avg {sum(observations)/len(observations):.4f}')
            for key, value in sorted(self._gauges.items()):
                lines.append(f"aegion_{key} {value}")
        return "\n".join(lines)


# Predefined metric names
class MetricNames:
    # Request metrics
    REQUEST_TOTAL = "http_requests_total"
    REQUEST_LATENCY = "http_request_duration_seconds"
    REQUEST_ERRORS = "http_request_errors_total"

    # Governance metrics
    PROPOSALS_CREATED = "governance_proposals_created_total"
    PROPOSALS_APPROVED = "governance_proposals_approved_total"
    PROPOSALS_REJECTED = "governance_proposals_rejected_total"
    GOVERNANCE_VIOLATIONS = "governance_violations_total"
    FREEZE_ACTIVATIONS = "governance_freeze_activations_total"

    # AI metrics
    AI_REQUESTS = "ai_requests_total"
    AI_TOKENS_USED = "ai_tokens_used_total"
    AI_LATENCY = "ai_request_duration_seconds"
    AI_FALLBACKS = "ai_fallback_total"

    # Session metrics
    ACTIVE_SESSIONS = "sessions_active"
    SESSION_DURATION = "session_duration_seconds"

    # Graph metrics
    GRAPH_NODES = "graph_nodes_total"
    GRAPH_EDGES = "graph_edges_total"
    DRIFT_SCORE = "drift_score_current"


# ──────────────────────────────────────────────────────────────────────────
# Tracing (OpenTelemetry-compatible spans)
# ──────────────────────────────────────────────────────────────────────────

class Span:
    """Lightweight span for tracing."""

    def __init__(self, name: str, trace_id: str, parent_id: Optional[str] = None):
        self.name = name
        self.trace_id = trace_id
        self.span_id = f"{id(self):016x}"
        self.parent_id = parent_id
        self.start_time = time.monotonic()
        self.end_time: Optional[float] = None
        self.attributes: Dict[str, Any] = {}
        self.status: str = "OK"

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def set_status(self, status: str):
        self.status = status

    def end(self):
        self.end_time = time.monotonic()

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentId": self.parent_id,
            "startTime": self.start_time,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "status": self.status,
        }


class TracingCollector:
    """Collects spans for export to tracing backends."""

    def __init__(self, max_spans: int = 5000):
        self._spans: list = []
        self._max_spans = max_spans
        self._lock = asyncio.Lock()

    def create_span(
        self, name: str, trace_id: str, parent_id: Optional[str] = None
    ) -> Span:
        return Span(name=name, trace_id=trace_id, parent_id=parent_id)

    async def record_span(self, span: Span):
        async with self._lock:
            self._spans.append(span.to_dict())
            if len(self._spans) > self._max_spans:
                self._spans = self._spans[-self._max_spans // 2:]

    async def export(self) -> list:
        async with self._lock:
            return list(self._spans)


# ──────────────────────────────────────────────────────────────────────────
# Singletons
# ──────────────────────────────────────────────────────────────────────────

_metrics: Optional[MetricsCollector] = None
_tracing: Optional[TracingCollector] = None


def get_metrics() -> MetricsCollector:
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def get_tracing() -> TracingCollector:
    global _tracing
    if _tracing is None:
        _tracing = TracingCollector()
    return _tracing
