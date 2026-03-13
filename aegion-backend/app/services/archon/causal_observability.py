"""
Aegion Causal Graph Observability.

Doctrine: "Click a Decision → see the exact trace that created it."

Provides:
- Trace context model (trace_id, span_id binding to graph nodes)
- Causal links between governance operations
- Trace-to-graph correlation: enrich graph nodes with trace context
- Export-ready spans for Jaeger/Tempo/Zipkin
- Governance operation timeline reconstruction
"""

import uuid
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from contextlib import contextmanager

from ...core.logging import logger


# ────────────────────────────────────────────────
# Trace Context
# ────────────────────────────────────────────────


@dataclass
class TraceContext:
    """
    Immutable trace context bound to a governance operation.

    Each governance action (proposal, decision, evidence submission)
    gets a TraceContext that links the request trace to the
    resulting graph node.
    """
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    operation: str = ""               # e.g., "approve_proposal", "submit_evidence"
    actor_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation,
            "actor_id": self.actor_id,
            "timestamp": self.timestamp.isoformat(),
            "attributes": self.attributes,
        }


@dataclass
class CausalLink:
    """
    Directed causal edge between two trace contexts.

    Captures: "Operation A caused Operation B"
    """
    source_trace_id: str
    source_span_id: str
    target_trace_id: str
    target_span_id: str
    relationship: str  # e.g., "triggered", "approved", "escalated"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": f"{self.source_trace_id}:{self.source_span_id}",
            "target": f"{self.target_trace_id}:{self.target_span_id}",
            "relationship": self.relationship,
            "timestamp": self.timestamp.isoformat(),
        }


# ────────────────────────────────────────────────
# Governance Span (enriched)
# ────────────────────────────────────────────────


@dataclass
class GovernanceSpan:
    """
    An enriched span representing a governance operation.

    Beyond standard trace spans, this captures:
    - The graph node it produced (node_id, node_type)
    - Governance metadata (tier, evidence count, invariant results)
    - Causal links to parent operations
    """
    span_id: str
    trace_id: str
    operation: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "OK"
    # Graph binding
    node_id: Optional[str] = None
    node_type: Optional[str] = None      # "proposal", "decision", "evidence"
    # Governance metadata
    tier: Optional[str] = None
    evidence_count: int = 0
    invariant_violations: int = 0
    # Parent
    parent_span_id: Optional[str] = None
    actor_id: str = ""
    workspace_id: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def to_otlp_dict(self) -> Dict[str, Any]:
        """Export in OpenTelemetry-compatible format."""
        return {
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentSpanId": self.parent_span_id or "",
            "operationName": self.operation,
            "startTime": int(self.start_time * 1_000_000),  # microseconds
            "duration": int(self.duration_ms * 1000),         # microseconds
            "status": {"code": 1 if self.status == "OK" else 2},
            "attributes": {
                "aegion.node_id": self.node_id or "",
                "aegion.node_type": self.node_type or "",
                "aegion.tier": self.tier or "",
                "aegion.actor_id": self.actor_id,
                "aegion.workspace_id": self.workspace_id,
                "aegion.evidence_count": self.evidence_count,
                "aegion.invariant_violations": self.invariant_violations,
                **self.attributes,
            },
            "tags": [
                {"key": "service.name", "value": "aegion-archon"},
            ],
        }


# ────────────────────────────────────────────────
# Causal Observability Service
# ────────────────────────────────────────────────


class CausalObservabilityService:
    """
    Binds trace contexts to graph nodes and maintains causal links.

    Usage:
        obs = get_causal_observability()

        # Start a traced governance operation
        with obs.trace_operation("approve_proposal", actor_id="u-1") as ctx:
            ctx.set_attribute("tier", "T2")
            # ... do governance work ...
            ctx.bind_node("decision", "dec-123")

        # Later: query what trace created a specific node
        ctx = obs.get_trace_for_node("dec-123")
        # → TraceContext with the exact trace that created it

        # Get causal chain for a trace
        chain = obs.get_causal_chain("trace-abc...")
    """

    def __init__(self, max_spans: int = 10000):
        self._spans: List[GovernanceSpan] = []
        self._max_spans = max_spans
        self._node_to_trace: Dict[str, TraceContext] = {}   # node_id → TraceContext
        self._causal_links: List[CausalLink] = []
        self._active_context: Optional[_TracedOperation] = None

    @contextmanager
    def trace_operation(
        self,
        operation: str,
        actor_id: str = "",
        workspace_id: str = "",
        parent_trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
    ):
        """
        Context manager for traced governance operations.

        Yields a _TracedOperation that can be enriched with
        graph bindings and governance metadata.
        """
        trace_id = parent_trace_id or uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]

        span = GovernanceSpan(
            span_id=span_id,
            trace_id=trace_id,
            operation=operation,
            start_time=time.monotonic(),
            parent_span_id=parent_span_id,
            actor_id=actor_id,
            workspace_id=workspace_id,
        )

        op = _TracedOperation(span=span, service=self)
        prev = self._active_context
        self._active_context = op

        try:
            yield op
            span.status = "OK"
        except Exception:
            span.status = "ERROR"
            raise
        finally:
            span.end_time = time.monotonic()
            self._record_span(span)
            self._active_context = prev

            # Create causal link if there's a parent
            if parent_span_id and parent_trace_id:
                self._causal_links.append(CausalLink(
                    source_trace_id=parent_trace_id,
                    source_span_id=parent_span_id,
                    target_trace_id=trace_id,
                    target_span_id=span_id,
                    relationship="triggered",
                ))

    def bind_node_to_trace(
        self,
        node_id: str,
        node_type: str,
        trace_id: str,
        span_id: str,
        operation: str = "",
        actor_id: str = "",
    ) -> TraceContext:
        """
        Bind a graph node to a trace context.

        After this, you can look up "which trace created this node."
        """
        ctx = TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            operation=operation,
            actor_id=actor_id,
        )
        self._node_to_trace[node_id] = ctx

        logger.debug(
            f"Graph node {node_type}:{node_id} bound to trace {trace_id[:12]}"
        )
        return ctx

    def get_trace_for_node(self, node_id: str) -> Optional[TraceContext]:
        """Look up the trace context that created/modified a graph node."""
        return self._node_to_trace.get(node_id)

    def get_causal_chain(self, trace_id: str) -> List[CausalLink]:
        """Get all causal links involving a trace."""
        return [
            link for link in self._causal_links
            if link.source_trace_id == trace_id or link.target_trace_id == trace_id
        ]

    def get_spans_for_trace(self, trace_id: str) -> List[GovernanceSpan]:
        """Get all spans in a trace."""
        return [s for s in self._spans if s.trace_id == trace_id]

    def get_spans_for_node(self, node_id: str) -> List[GovernanceSpan]:
        """Get all spans that touched a specific graph node."""
        return [s for s in self._spans if s.node_id == node_id]

    def get_operation_timeline(
        self,
        workspace_id: str = "",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get a timeline of governance operations for a workspace."""
        spans = self._spans
        if workspace_id:
            spans = [s for s in spans if s.workspace_id == workspace_id]

        # Most recent first
        spans = sorted(spans, key=lambda s: s.start_time, reverse=True)[:limit]

        return [
            {
                "operation": s.operation,
                "trace_id": s.trace_id,
                "span_id": s.span_id,
                "node_id": s.node_id,
                "node_type": s.node_type,
                "tier": s.tier,
                "actor_id": s.actor_id,
                "duration_ms": round(s.duration_ms, 2),
                "status": s.status,
            }
            for s in spans
        ]

    def export_jaeger(self) -> List[Dict[str, Any]]:
        """Export all spans in Jaeger-compatible format."""
        return [s.to_otlp_dict() for s in self._spans]

    def stats(self) -> Dict[str, Any]:
        """Observability statistics."""
        return {
            "total_spans": len(self._spans),
            "bound_nodes": len(self._node_to_trace),
            "causal_links": len(self._causal_links),
            "active_traces": len(set(s.trace_id for s in self._spans)),
        }

    def _record_span(self, span: GovernanceSpan) -> None:
        """Record a completed span."""
        self._spans.append(span)
        if len(self._spans) > self._max_spans:
            self._spans = self._spans[-self._max_spans // 2:]

        # Also forward to the base TracingCollector if available
        try:
            tracing = get_tracing_safe()
            if tracing:
                from ...middleware.observability import Span as BaseSpan
                base = BaseSpan(
                    name=span.operation,
                    trace_id=span.trace_id,
                    parent_id=span.parent_span_id,
                )
                base.end_time = span.end_time
                base.start_time = span.start_time
                base.attributes = {
                    "aegion.node_id": span.node_id or "",
                    "aegion.node_type": span.node_type or "",
                    **span.attributes,
                }
                base.status = span.status
                # Fire and forget — TracingCollector.record_span is async
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(tracing.record_span(base))
                except RuntimeError:
                    pass  # No event loop — skip forwarding
        except Exception:
            pass  # Non-critical


# ────────────────────────────────────────────────
# Traced Operation (yielded by context manager)
# ────────────────────────────────────────────────


class _TracedOperation:
    """Handle yielded by CausalObservabilityService.trace_operation()."""

    def __init__(self, span: GovernanceSpan, service: CausalObservabilityService):
        self._span = span
        self._service = service

    @property
    def trace_id(self) -> str:
        return self._span.trace_id

    @property
    def span_id(self) -> str:
        return self._span.span_id

    def set_attribute(self, key: str, value: Any) -> None:
        self._span.attributes[key] = value

    def set_tier(self, tier: str) -> None:
        self._span.tier = tier

    def set_evidence_count(self, count: int) -> None:
        self._span.evidence_count = count

    def set_invariant_violations(self, count: int) -> None:
        self._span.invariant_violations = count

    def bind_node(self, node_type: str, node_id: str) -> TraceContext:
        """Bind the current operation to a graph node."""
        self._span.node_id = node_id
        self._span.node_type = node_type
        return self._service.bind_node_to_trace(
            node_id=node_id,
            node_type=node_type,
            trace_id=self._span.trace_id,
            span_id=self._span.span_id,
            operation=self._span.operation,
            actor_id=self._span.actor_id,
        )

    def set_status(self, status: str) -> None:
        self._span.status = status


# ────────────────────────────────────────────────
# Helper: safe import
# ────────────────────────────────────────────────

def get_tracing_safe():
    """Safely get the TracingCollector without circular imports."""
    try:
        from ...middleware.observability import get_tracing
        return get_tracing()
    except Exception:
        return None


# ────────────────────────────────────────────────
# Singleton
# ────────────────────────────────────────────────

_observability: Optional[CausalObservabilityService] = None


def get_causal_observability() -> CausalObservabilityService:
    """Get the global CausalObservabilityService singleton."""
    global _observability
    if _observability is None:
        _observability = CausalObservabilityService()
    return _observability
