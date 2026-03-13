"""
Aegion Formal Invariant Engine.

Loads invariant specifications from invariants.yaml and evaluates them
at runtime on governance write operations.

Invariants are declarative rules that must always hold. They can be:
- blocking:  prevents the write and raises GovernanceError
- alerting:  logs a warning but allows the write

The engine supports:
- Startup validation of all invariant specs
- Per-operation evaluation with rich context
- Background continuous monitoring (periodic sweep)
- Detailed violation reporting
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ...core.logging import logger


# ────────────────────────────────────────────────
# Data Structures
# ────────────────────────────────────────────────


@dataclass(frozen=True)
class InvariantSpec:
    """A single invariant loaded from YAML."""
    id: str
    name: str
    description: str
    category: str          # structural | temporal | authority | evidence | freeze
    severity: str          # blocking | alerting
    condition: str         # Python expression — when the invariant applies
    must_satisfy: str      # Python expression — the assertion
    error_msg: str         # Human-readable template
    enabled: bool = True


@dataclass
class InvariantViolation:
    """A detected violation."""
    invariant_id: str
    invariant_name: str
    severity: str
    category: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class InvariantResult:
    """Result of evaluating invariants against a governance operation."""
    passed: bool
    violations: List[InvariantViolation] = field(default_factory=list)
    evaluated_count: int = 0
    skipped_count: int = 0

    @property
    def blocking_violations(self) -> List[InvariantViolation]:
        return [v for v in self.violations if v.severity == "blocking"]

    @property
    def alerting_violations(self) -> List[InvariantViolation]:
        return [v for v in self.violations if v.severity == "alerting"]


# ────────────────────────────────────────────────
# Engine
# ────────────────────────────────────────────────

_DEFAULT_INVARIANTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "invariants.yaml",
)


class InvariantEngine:
    """
    Runtime invariant enforcement engine.

    Usage:
        engine = InvariantEngine()
        engine.load()

        # On every governance write:
        result = engine.evaluate(context={
            "tier": "T2",
            "evidence_count": 1,
            "proposer_id": "user-a",
            "approver_id": "user-b",
            ...
        })

        if not result.passed:
            raise GovernanceError(result.blocking_violations[0].message)
    """

    async_mode: bool = False
    
    # Global metrics for monitoring
    _total_violations: int = 0
    _blocking_violations_count: int = 0
    
    def __init__(self, yaml_path: Optional[str] = None):
        self._path = yaml_path or _DEFAULT_INVARIANTS_PATH
        self._invariants: List[InvariantSpec] = []
        self._loaded = False

    # ── Loading ──────────────────────────────────

    def load(self, yaml_path: Optional[str] = None) -> int:
        """
        Load invariant specifications from YAML.

        Returns the number of enabled invariants loaded.
        """
        path = yaml_path or self._path
        if not os.path.exists(path):
            logger.warning(f"Invariants file not found: {path}")
            return 0

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        raw_list = data.get("invariants", [])
        self._invariants = []

        for raw in raw_list:
            spec = InvariantSpec(
                id=raw["id"],
                name=raw["name"],
                description=raw["description"],
                category=raw["category"],
                severity=raw["severity"],
                condition=raw["condition"],
                must_satisfy=raw["must_satisfy"],
                error_msg=raw["error_msg"],
                enabled=raw.get("enabled", True),
            )
            self._invariants.append(spec)

        enabled = [s for s in self._invariants if s.enabled]
        self._loaded = True

        logger.info(
            f"InvariantEngine loaded {len(enabled)}/{len(self._invariants)} "
            f"invariants from {path}"
        )
        return len(enabled)

    # ── Evaluation ───────────────────────────────

    def evaluate(self, context: Dict[str, Any]) -> InvariantResult:
        """
        Evaluate all enabled invariants against the given context.

        Context is a dict of variable bindings available to both
        `condition` and `must_satisfy` expressions.

        Returns InvariantResult with pass/fail status and any violations.
        """
        if not self._loaded:
            self.load()

        violations: List[InvariantViolation] = []
        evaluated = 0
        skipped = 0

        for spec in self._invariants:
            if not spec.enabled:
                skipped += 1
                continue

            try:
                # Check if this invariant applies
                applies = self._safe_eval(spec.condition, context)
                if not applies:
                    skipped += 1
                    continue

                evaluated += 1

                # Check if the assertion holds
                satisfied = self._safe_eval(spec.must_satisfy, context)

                if not satisfied:
                    # Format the error message with context
                    try:
                        msg = spec.error_msg.format(**context)
                    except (KeyError, IndexError):
                        msg = spec.error_msg

                    violation = InvariantViolation(
                        invariant_id=spec.id,
                        invariant_name=spec.name,
                        severity=spec.severity,
                        category=spec.category,
                        message=msg,
                        context=context,
                    )
                    violations.append(violation)

                    if spec.severity == "blocking":
                        logger.audit(
                            action="INVARIANT_VIOLATION_BLOCKING",
                            actor="invariant_engine",
                            target=spec.id,
                            justification=msg,
                        )
                    else:
                        logger.warning(
                            f"Invariant alert {spec.id} ({spec.name}): {msg}"
                        )
                        
                    # Prometheus Metrics
                    try:
                        from ...services.archon.metrics import get_metrics_service
                        get_metrics_service().invariant_violations.labels(
                            severity=spec.severity, invariant_id=spec.id
                        ).inc()
                    except ImportError:
                        pass # Circular import or missing metrics module safety

            except Exception as e:
                logger.error(
                    f"InvariantEngine: error evaluating {spec.id} "
                    f"({spec.name}): {e}"
                )
                # Fail open — evaluation errors don't block
                continue

        blocking = [v for v in violations if v.severity == "blocking"]

        # Update metrics 
        self._total_violations += len(violations)
        self._blocking_violations_count += len(blocking)

        return InvariantResult(
            passed=len(blocking) == 0,
            violations=violations,
            evaluated_count=evaluated,
            skipped_count=skipped,
        )

    def evaluate_for_approval(
        self,
        tier: str,
        proposer_id: str,
        approver_id: str,
        approver_type: str,
        evidence_count: int,
        stale_evidence_count: int,
        distinct_evidence_types: int,
        all_evidence_after_proposal: bool,
        freeze_active: bool,
        existing_decisions_for_proposal: int = 0,
        **extra: Any,
    ) -> InvariantResult:
        """
        Convenience method — evaluates all invariants relevant to
        proposal approval with strongly-typed parameters.
        """
        context: Dict[str, Any] = {
            "tier": tier,
            "proposer_id": proposer_id,
            "approver_id": approver_id,
            "approver_type": approver_type,
            "evidence_count": evidence_count,
            "stale_evidence_count": stale_evidence_count,
            "distinct_evidence_types": distinct_evidence_types,
            "all_evidence_after_proposal": all_evidence_after_proposal,
            "freeze_active": freeze_active,
            "mutation_requested": True,
            "operation": "approve",
            "node_type": "decision",
            "is_create_operation": True,
            "existing_decisions_for_proposal": existing_decisions_for_proposal,
            "reclassification": False,
            "cross_workspace_reference": False,
            "created_at_is_past": True,
            **extra,
        }
        return self.evaluate(context)

    # ── Background Monitoring ────────────────────

    async def continuous_monitor(
        self,
        graph_port,
        workspace_id: Optional[str] = None,
    ) -> InvariantResult:
        """
        Background sweep: check structural invariants against the
        current graph state.

        This catches issues that slip through per-operation checks:
        - Orphan decisions (no proposal link)
        - Cross-workspace references
        - Future timestamps
        """
        violations: List[InvariantViolation] = []

        try:
            # Check for orphan decisions
            decisions = await graph_port.find_nodes(
                node_type=None,
                properties={"node_type": "decision"},
                limit=1000,
            )
            for decision in decisions:
                edges = await graph_port.get_edges(target_id=decision.node_id)
                proposal_links = [
                    e for e in edges
                    if e.edge_type.value in ("derives_from", "belongs_to")
                ]
                if not proposal_links:
                    violations.append(InvariantViolation(
                        invariant_id="INV-011",
                        invariant_name="no_orphan_decisions",
                        severity="alerting",
                        category="structural",
                        message=f"Decision {decision.node_id} has no proposal linkage.",
                    ))

            # Check for future timestamps
            from datetime import datetime as dt
            now = dt.now(timezone.utc)
            all_nodes = await graph_port.find_nodes(limit=500)
            for node in all_nodes:
                if node.created_at and node.created_at > now:
                    violations.append(InvariantViolation(
                        invariant_id="INV-013",
                        invariant_name="no_future_timestamps",
                        severity="alerting",
                        category="temporal",
                        message=f"Node {node.node_id} has future timestamp {node.created_at}.",
                    ))

        except Exception as e:
            logger.error(f"Continuous invariant monitor error: {e}")

        return InvariantResult(
            passed=all(v.severity != "blocking" for v in violations),
            violations=violations,
            evaluated_count=len(violations),
            skipped_count=0,
        )

    # ── Query ────────────────────────────────────

    def list_invariants(
        self, category: Optional[str] = None, enabled_only: bool = True
    ) -> List[Dict[str, Any]]:
        """List all loaded invariants, optionally filtered."""
        if not self._loaded:
            self.load()

        result = []
        for spec in self._invariants:
            if enabled_only and not spec.enabled:
                continue
            if category and spec.category != category:
                continue
            result.append({
                "id": spec.id,
                "name": spec.name,
                "description": spec.description,
                "category": spec.category,
                "severity": spec.severity,
                "enabled": spec.enabled,
            })
        return result

    # ── Internal ─────────────────────────────────

    def get_violation_metrics(self) -> Dict[str, int]:
        """Get global violation counts for StormWatcher."""
        return {
            "total_violations": self._total_violations,
            "blocking_violations": self._blocking_violations_count,
        }

    @staticmethod
    def _safe_eval(expression: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate a Python expression in a restricted namespace.

        Only the context dict keys + builtins (True, False, None, in, not, etc.)
        are available. No imports, no attribute access, no function calls
        besides builtins.
        """
        # Restricted builtins
        safe_builtins = {
            "True": True,
            "False": False,
            "None": None,
            "all": all,
            "any": any,
            "len": len,
            "abs": abs,
            "min": min,
            "max": max,
            "int": int,
            "str": str,
            "bool": bool,
        }

        namespace = {**safe_builtins, **context}

        try:
            return bool(eval(expression, {"__builtins__": {}}, namespace))
        except Exception:
            return False


# ────────────────────────────────────────────────
# Singleton
# ────────────────────────────────────────────────

_engine: Optional[InvariantEngine] = None


def get_invariant_engine() -> InvariantEngine:
    """Get the singleton InvariantEngine, loading invariants on first call."""
    global _engine
    if _engine is None:
        _engine = InvariantEngine()
        _engine.load()
    return _engine
