"""
Aegion Metrics Service.

Doctrine: "You cannot govern what you cannot measure."

Provides:
- Prometheus metrics for key governance KPIs
- Proposal throughput
- Council latency
- Invariant violation rates
- System health gauges
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime
from functools import wraps

# Try to import Prometheus client, fallback to dummy implementation if missing
try:
    from ...core.logging import logger
except (ImportError, ValueError):
    # Standalone fallback
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("MetricsService")

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not found. Metrics will be logged only.")
    
    # Dummy implementation for fallback
    class Metric:
        def __init__(self, name, documentation, labelnames=(), **kwargs):
            self.name = name
            
        def labels(self, **kwargs):
            return self
            
    class Counter(Metric):
        def inc(self, amount=1):
            pass
            
    class Gauge(Metric):
        def set(self, value):
            pass
        def inc(self, amount=1):
            pass
        def dec(self, amount=1):
            pass
            
    class Histogram(Metric):
        def observe(self, value):
            pass
            
    def generate_latest():
        return b""
        
    CONTENT_TYPE_LATEST = "text/plain"


class MetricsService:
    """
    Centralized metrics registry for Aegion.
    """
    
    # Singleton instance
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MetricsService, cls).__new__(cls)
            cls._instance._initialize_metrics()
        return cls._instance
    
    def _initialize_metrics(self):
        """Define Prometheus metrics."""
        # Counters
        self.proposals_created = Counter(
            "aegion_proposals_created_total",
            "Total number of governance proposals created",
            ["type", "workspace"]
        )
        self.decisions_approved = Counter(
            "aegion_decisions_approved_total",
            "Total number of proposals approved",
            ["tier", "workspace"]
        )
        self.invariant_violations = Counter(
            "aegion_invariant_violations_total",
            "Total number of invariant violations detected",
            ["severity", "invariant_id"]
        )
        self.council_sessions = Counter(
            "aegion_council_sessions_total",
            "Total number of AI council sessions convened",
            ["result"]
        )
        
        # Gauges
        self.active_proposals = Gauge(
            "aegion_active_proposals",
            "Number of proposals currently in pending state",
            ["workspace"]
        )
        self.system_health = Gauge(
            "aegion_system_health",
            "Overall system health status (1=Healthy, 0=Unhealthy)",
            ["component"]
        )
        
        # Histograms
        self.council_duration = Histogram(
            "aegion_council_duration_seconds",
            "Time taken for AI council to reach consensus",
            buckets=[1, 5, 10, 30, 60, 120]
        )
        self.proposal_latency = Histogram(
            "aegion_proposal_processing_seconds",
            "End-to-end latency from proposal creation to decision",
            buckets=[60, 300, 3600, 86400]
        )

    def get_metrics_data(self) -> bytes:
        """Expose metrics for scraping."""
        if PROMETHEUS_AVAILABLE:
            from prometheus_client import generate_latest
            return generate_latest()
        return b"# Prometheus client not installed."

    def track_council_duration(self):
        """Decorator to track council session duration."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    self.council_duration.observe(duration)
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    self.council_duration.observe(duration)
                    raise e
            return wrapper
        return decorator


# Global accessor
def get_metrics_service() -> MetricsService:
    return MetricsService()
