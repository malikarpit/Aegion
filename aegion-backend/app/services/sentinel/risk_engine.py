"""
Aegion Sentinel Risk Engine — Phase 21: Advanced Multi-Signal Risk Scoring.

Provides production-grade risk assessment using weighted multi-signal analysis.
Replaces simple keyword heuristics with a structured signal pipeline.

Signal Categories:
  - FILE_SENSITIVITY: Production configs, auth files, migrations, secrets
  - BLAST_RADIUS: Number of files/services/modules affected by a change
  - PATTERN_MATCH: Dangerous code patterns (DROP TABLE, rm -rf, etc.)
  - DEPENDENCY_CHANGE: Adding/removing/updating dependencies
  - HISTORICAL_RISK: Files that have caused past incidents
  - STALENESS: Evidence freshness and age decay
  - VELOCITY: Decision-making speed (too fast = risky)
  - AUTHORITY: Tier distribution concentration
  - EVIDENCE_GAP: Decisions without sufficient supporting evidence

Produces:
  - Composite risk score (0.0 – 100.0)
  - Risk tier classification (T0–T3)
  - Per-signal breakdown with evidence strings
  - Actionable recommendations
  - Risk heatmap by module
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ...contracts.risk import (
    RiskCategory,
    RiskHeatmap,
    RiskHeatmapCell,
    RiskLevel,
    RiskScore,
)
from ...core.logging import logger


# ──────────────────────────────────────────────────────────────────────────────
# Risk signal types
# ──────────────────────────────────────────────────────────────────────────────

class SignalType(str, Enum):
    """Categories of risk signals."""
    FILE_SENSITIVITY = "file_sensitivity"
    BLAST_RADIUS = "blast_radius"
    PATTERN_MATCH = "pattern_match"
    DEPENDENCY_CHANGE = "dependency_change"
    HISTORICAL_RISK = "historical_risk"
    STALENESS = "staleness"
    VELOCITY = "velocity"
    AUTHORITY = "authority"
    EVIDENCE_GAP = "evidence_gap"


@dataclass
class RiskSignal:
    """Individual risk signal with weight, score, and evidence."""
    signal_type: SignalType
    score: float              # 0.0 – 1.0
    weight: float             # 0.0 – 1.0 (how much this matters)
    evidence: str             # Human-readable explanation
    matched_items: List[str] = field(default_factory=list)

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


# ──────────────────────────────────────────────────────────────────────────────
# Pattern definitions
# ──────────────────────────────────────────────────────────────────────────────

# File paths that indicate high sensitivity (score: 0.8–1.0)
_SENSITIVE_FILE_PATTERNS = [
    (re.compile(r"\.env($|\.)"), 1.0, "Environment/secrets file"),
    (re.compile(r"(secret|credential|password|key|token)s?\."), 0.95, "Secrets/credentials file"),
    (re.compile(r"auth[_/]"), 0.85, "Authentication module"),
    (re.compile(r"migrations?/"), 0.80, "Database migration"),
    (re.compile(r"(Dockerfile|docker-compose|cloudbuild)", re.I), 0.75, "Infrastructure config"),
    (re.compile(r"\.ya?ml$"), 0.60, "Configuration file"),
    (re.compile(r"(deploy|ci|cd|workflow)", re.I), 0.70, "CI/CD pipeline"),
    (re.compile(r"(rbac|acl|permission|policy)", re.I), 0.85, "Access control"),
    (re.compile(r"requirements\.txt|package\.json|Cargo\.toml|go\.mod"), 0.65, "Dependency manifest"),
    (re.compile(r"(main|app|server)\.(py|ts|js|go|rs)$"), 0.60, "Application entrypoint"),
]

# Dangerous code patterns (score: 0.7–1.0)
_DANGEROUS_PATTERNS = [
    (re.compile(r"DROP\s+(TABLE|DATABASE|SCHEMA)", re.I), 1.0, "SQL destructive operation"),
    (re.compile(r"DELETE\s+FROM\s+\w+\s*(;|$)", re.I), 0.90, "SQL bulk delete without WHERE"),
    (re.compile(r"TRUNCATE\s+TABLE", re.I), 0.95, "SQL truncate"),
    (re.compile(r"rm\s+(-rf?\s+|--recursive)", re.I), 0.95, "Recursive file deletion"),
    (re.compile(r"eval\s*\("), 0.85, "Dynamic code execution (eval)"),
    (re.compile(r"exec\s*\("), 0.80, "Dynamic code execution (exec)"),
    (re.compile(r"subprocess\.(call|run|Popen)\s*\(.*shell\s*=\s*True", re.I), 0.90, "Shell injection vector"),
    (re.compile(r"os\.system\s*\("), 0.85, "OS command execution"),
    (re.compile(r"__import__\s*\("), 0.75, "Dynamic import"),
    (re.compile(r"GRANT\s+ALL|ALTER\s+ROLE", re.I), 0.80, "Privilege escalation SQL"),
    (re.compile(r"disable.*ssl|verify\s*=\s*False|INSECURE", re.I), 0.80, "SSL/TLS bypass"),
    (re.compile(r"password\s*=\s*['\"][^'\"]+['\"]", re.I), 0.85, "Hardcoded password"),
    (re.compile(r"BEGIN_RSA|PRIVATE\s+KEY", re.I), 1.0, "Private key in source"),
]

# Dependency change indicators
_DEPENDENCY_FILES = {
    "requirements.txt", "requirements-dev.txt", "setup.py", "setup.cfg",
    "pyproject.toml", "Pipfile", "Pipfile.lock",
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.toml", "Cargo.lock", "go.mod", "go.sum",
    "Gemfile", "Gemfile.lock",
}


class RiskEngine:
    """
    Multi-signal risk scoring engine.

    Produces a composite risk score from independent risk signals,
    each with its own weight. Signals are evaluated in parallel and
    aggregated using a weighted sum.

    Tier Classification:
      T0: 0–25   (Minimal risk, auto-approve eligible)
      T1: 25–50  (Low risk, standard review)
      T2: 50–75  (Medium risk, senior review required)
      T3: 75–100 (Critical risk, council deliberation required)
    """

    # Default signal weights (sum to 1.0)
    DEFAULT_WEIGHTS: Dict[SignalType, float] = {
        SignalType.FILE_SENSITIVITY:  0.18,
        SignalType.BLAST_RADIUS:      0.15,
        SignalType.PATTERN_MATCH:     0.18,
        SignalType.DEPENDENCY_CHANGE: 0.08,
        SignalType.HISTORICAL_RISK:   0.06,
        SignalType.STALENESS:         0.12,
        SignalType.VELOCITY:          0.10,
        SignalType.AUTHORITY:         0.08,
        SignalType.EVIDENCE_GAP:      0.05,
    }

    # Legacy weight mapping for backward compat with risk contract
    _LEGACY_WEIGHTS = {
        RiskCategory.STALENESS:     0.3,
        RiskCategory.VELOCITY:      0.25,
        RiskCategory.AUTHORITY:     0.25,
        RiskCategory.EVIDENCE_GAP:  0.2,
    }

    def __init__(
        self,
        weights: Optional[Dict[SignalType, float]] = None,
        staleness_weight: float = 0.3,
        velocity_weight: float = 0.25,
        tier_weight: float = 0.25,
        evidence_weight: float = 0.2,
    ):
        self.weights = weights or self.DEFAULT_WEIGHTS
        # Keep legacy weights for backward compat
        self._legacy_weights = {
            RiskCategory.STALENESS: staleness_weight,
            RiskCategory.VELOCITY: velocity_weight,
            RiskCategory.AUTHORITY: tier_weight,
            RiskCategory.EVIDENCE_GAP: evidence_weight,
        }

    # ──────────────────────────────────────────────
    # Primary API
    # ──────────────────────────────────────────────

    async def calculate_risk_score(
        self,
        workspace_id: str,
        decisions: Optional[List[Dict]] = None,
        evidence: Optional[List[Dict]] = None,
        changed_files: Optional[List[str]] = None,
        diff_content: Optional[str] = None,
        lookback_hours: int = 24,
    ) -> RiskScore:
        """
        Calculate composite risk score for a workspace.

        Args:
            workspace_id: Workspace to analyze.
            decisions: Recent decisions (optional).
            evidence: Recent evidence (optional).
            changed_files: List of file paths being modified.
            diff_content: Raw diff text for pattern matching.
            lookback_hours: Time window for velocity analysis.

        Returns:
            RiskScore with composite score, per-category breakdown, and recommendations.
        """
        decisions = decisions or []
        evidence = evidence or []
        changed_files = changed_files or []
        diff_content = diff_content or ""

        # Collect all signals
        signals: List[RiskSignal] = []

        # File sensitivity signal
        if changed_files:
            signals.append(self._score_file_sensitivity(changed_files))

        # Blast radius signal
        if changed_files:
            signals.append(self._score_blast_radius(changed_files))

        # Pattern matching signal
        if diff_content:
            signals.append(self._score_patterns(diff_content))

        # Dependency change signal
        if changed_files:
            signals.append(self._score_dependencies(changed_files))

        # Historical risk signal
        if changed_files:
            signals.append(await self._score_historical(workspace_id, changed_files))

        # Staleness signal
        staleness_score, staleness_factors = await self._calculate_staleness_score(evidence)
        if staleness_score > 0:
            signals.append(RiskSignal(
                signal_type=SignalType.STALENESS,
                score=staleness_score / 100.0,
                weight=self.weights.get(SignalType.STALENESS, 0.12),
                evidence="; ".join(staleness_factors) if staleness_factors else "Evidence is fresh",
            ))

        # Velocity signal
        velocity_score, velocity_factors = await self._calculate_velocity_score(decisions, lookback_hours)
        if velocity_score > 0:
            signals.append(RiskSignal(
                signal_type=SignalType.VELOCITY,
                score=velocity_score / 100.0,
                weight=self.weights.get(SignalType.VELOCITY, 0.10),
                evidence="; ".join(velocity_factors) if velocity_factors else "Normal velocity",
            ))

        # Authority signal
        tier_score, tier_factors = await self._calculate_tier_score(decisions)
        if tier_score > 0:
            signals.append(RiskSignal(
                signal_type=SignalType.AUTHORITY,
                score=tier_score / 100.0,
                weight=self.weights.get(SignalType.AUTHORITY, 0.08),
                evidence="; ".join(tier_factors) if tier_factors else "Normal tier distribution",
            ))

        # Evidence gap signal
        evidence_score, evidence_factors = await self._calculate_evidence_gap_score(decisions, evidence)
        if evidence_score > 0:
            signals.append(RiskSignal(
                signal_type=SignalType.EVIDENCE_GAP,
                score=evidence_score / 100.0,
                weight=self.weights.get(SignalType.EVIDENCE_GAP, 0.05),
                evidence="; ".join(evidence_factors) if evidence_factors else "Adequate evidence",
            ))

        # Calculate composite score (0–100)
        if signals:
            total_weight = sum(s.weight for s in signals)
            if total_weight > 0:
                overall_score = sum(s.weighted_score for s in signals) / total_weight * 100.0
            else:
                overall_score = 0.0
        else:
            overall_score = 0.0

        overall_score = min(100.0, max(0.0, overall_score))
        overall_level = self._score_to_level(overall_score)

        # Build component scores for backward compat
        component_scores = self._build_component_scores(signals)

        # Contributing factors (human-readable)
        contributing_factors = [
            f"[{s.signal_type.value}] {s.evidence} (score: {s.score:.2f}, weight: {s.weight:.2f})"
            for s in signals if s.score > 0.1
        ]

        # Recommendations
        recommendations = self._generate_recommendations(component_scores, contributing_factors, signals)

        return RiskScore(
            entity_id=workspace_id,
            entity_type="workspace",
            overall_score=overall_score,
            overall_level=overall_level,
            component_scores=component_scores,
            contributing_factors=contributing_factors,
            computed_at=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
            recommendations=recommendations,
        )

    def classify_tier(self, score: float) -> str:
        """Classify a risk score into Archon governance tiers."""
        if score <= 25:
            return "T0"
        elif score <= 50:
            return "T1"
        elif score <= 75:
            return "T2"
        else:
            return "T3"

    # ──────────────────────────────────────────────
    # File sensitivity scoring
    # ──────────────────────────────────────────────

    def _score_file_sensitivity(self, files: List[str]) -> RiskSignal:
        """Score risk based on which files are being modified."""
        max_score = 0.0
        matched: List[str] = []

        for fpath in files:
            for pattern, severity, label in _SENSITIVE_FILE_PATTERNS:
                if pattern.search(fpath):
                    if severity > max_score:
                        max_score = severity
                    matched.append(f"{label}: {fpath}")
                    break  # One match per file

        return RiskSignal(
            signal_type=SignalType.FILE_SENSITIVITY,
            score=max_score,
            weight=self.weights.get(SignalType.FILE_SENSITIVITY, 0.18),
            evidence=f"{len(matched)} sensitive file(s) modified" if matched else "No sensitive files",
            matched_items=matched[:10],
        )

    # ──────────────────────────────────────────────
    # Blast radius scoring
    # ──────────────────────────────────────────────

    def _score_blast_radius(self, files: List[str]) -> RiskSignal:
        """Score risk based on how many files/modules are affected."""
        file_count = len(files)

        # Extract unique directories (modules)
        modules = set()
        for f in files:
            parts = f.replace("\\", "/").split("/")
            if len(parts) >= 2:
                modules.add(parts[0] + "/" + parts[1])
            elif parts:
                modules.add(parts[0])

        module_count = len(modules)

        # Scoring: more files/modules = higher risk
        if file_count > 50:
            score = 1.0
        elif file_count > 20:
            score = 0.8
        elif file_count > 10:
            score = 0.6
        elif file_count > 5:
            score = 0.4
        elif file_count > 2:
            score = 0.2
        else:
            score = 0.05

        # Boost if touching many different modules
        if module_count > 5:
            score = min(1.0, score + 0.2)

        return RiskSignal(
            signal_type=SignalType.BLAST_RADIUS,
            score=score,
            weight=self.weights.get(SignalType.BLAST_RADIUS, 0.15),
            evidence=f"{file_count} files across {module_count} modules",
        )

    # ──────────────────────────────────────────────
    # Dangerous pattern matching
    # ──────────────────────────────────────────────

    def _score_patterns(self, diff_content: str) -> RiskSignal:
        """Score risk based on dangerous code patterns in the diff."""
        max_score = 0.0
        matched: List[str] = []

        for pattern, severity, label in _DANGEROUS_PATTERNS:
            findings = pattern.findall(diff_content)
            if findings:
                if severity > max_score:
                    max_score = severity
                matched.append(f"{label} ({len(findings)} occurrence{'s' if len(findings) > 1 else ''})")

        return RiskSignal(
            signal_type=SignalType.PATTERN_MATCH,
            score=max_score,
            weight=self.weights.get(SignalType.PATTERN_MATCH, 0.18),
            evidence="; ".join(matched[:5]) if matched else "No dangerous patterns detected",
            matched_items=matched[:10],
        )

    # ──────────────────────────────────────────────
    # Dependency change scoring
    # ──────────────────────────────────────────────

    def _score_dependencies(self, files: List[str]) -> RiskSignal:
        """Score risk from dependency manifest changes."""
        dep_files = [f for f in files if f.split("/")[-1] in _DEPENDENCY_FILES]

        if not dep_files:
            return RiskSignal(
                signal_type=SignalType.DEPENDENCY_CHANGE,
                score=0.0,
                weight=self.weights.get(SignalType.DEPENDENCY_CHANGE, 0.08),
                evidence="No dependency changes",
            )

        # Lock files are lower risk than manifest files
        lock_files = [f for f in dep_files if "lock" in f.lower() or ".lock" in f]
        manifest_files = [f for f in dep_files if f not in lock_files]

        score = 0.0
        if manifest_files:
            score = 0.7  # Manifest change = new deps
        elif lock_files:
            score = 0.3  # Lock file only = version bump

        return RiskSignal(
            signal_type=SignalType.DEPENDENCY_CHANGE,
            score=score,
            weight=self.weights.get(SignalType.DEPENDENCY_CHANGE, 0.08),
            evidence=f"{len(manifest_files)} manifest(s), {len(lock_files)} lockfile(s) changed",
            matched_items=dep_files[:5],
        )

    # ──────────────────────────────────────────────
    # Historical risk scoring
    # ──────────────────────────────────────────────

    async def _score_historical(self, workspace_id: str, files: List[str]) -> RiskSignal:
        """Score risk based on past incident history for these files."""
        try:
            from ...db.supabase_client import get_supabase_client
            client = get_supabase_client()

            # Query audit_log for past incidents involving these files
            result = client.table("audit_log").select("id, entity_id") \
                .eq("workspace_id", workspace_id) \
                .eq("event_type", "incident") \
                .in_("entity_id", files[:20]) \
                .limit(10) \
                .execute()

            incidents = result.data if result.data else []
            if incidents:
                # More past incidents = higher risk
                score = min(1.0, len(incidents) * 0.25)
                return RiskSignal(
                    signal_type=SignalType.HISTORICAL_RISK,
                    score=score,
                    weight=self.weights.get(SignalType.HISTORICAL_RISK, 0.06),
                    evidence=f"{len(incidents)} past incident(s) linked to modified files",
                    matched_items=[i["entity_id"] for i in incidents[:5]],
                )
        except Exception as exc:
            logger.debug(f"Historical risk lookup failed (non-fatal): {exc}")

        return RiskSignal(
            signal_type=SignalType.HISTORICAL_RISK,
            score=0.0,
            weight=self.weights.get(SignalType.HISTORICAL_RISK, 0.06),
            evidence="No historical incidents found",
        )

    # ──────────────────────────────────────────────
    # Legacy signal calculators (backward compat)
    # ──────────────────────────────────────────────

    async def _calculate_staleness_score(
        self, evidence: List[Dict],
    ) -> Tuple[float, List[str]]:
        """Calculate staleness risk score."""
        if not evidence:
            return 0.0, []

        now = datetime.now(timezone.utc)
        stale_count = 0
        very_stale_count = 0

        for e in evidence:
            is_stale = e.get("is_stale", False)
            if is_stale:
                stale_count += 1
            # Check for very old evidence (> 7 days)
            created = e.get("created_at")
            if isinstance(created, str):
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if (now - created_dt).days > 7:
                        very_stale_count += 1
                except (ValueError, TypeError):
                    pass

        ratio = stale_count / len(evidence)
        score = ratio * 100.0

        # Boost score if very old evidence exists
        if very_stale_count > 0:
            score = min(100.0, score + very_stale_count * 5.0)

        factors = []
        if ratio > 0.5:
            factors.append(f"High staleness: {stale_count}/{len(evidence)} evidence items stale")
        elif ratio > 0.2:
            factors.append(f"Moderate staleness: {stale_count} stale evidence items")
        if very_stale_count > 0:
            factors.append(f"{very_stale_count} evidence items older than 7 days")

        return score, factors

    async def _calculate_velocity_score(
        self, decisions: List[Dict], lookback_hours: int,
    ) -> Tuple[float, List[str]]:
        """Calculate velocity risk score with burst detection."""
        if not decisions:
            return 0.0, []

        velocity = len(decisions) / max(lookback_hours, 1)

        # Burst detection: check if decisions cluster in short windows
        burst_score = 0.0
        if len(decisions) >= 5:
            timestamps = []
            for d in decisions:
                ts = d.get("created_at")
                if isinstance(ts, str):
                    try:
                        timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
                    except (ValueError, TypeError):
                        pass

            if len(timestamps) >= 5:
                timestamps.sort()
                # Check for 5 decisions within 10 minutes
                for i in range(len(timestamps) - 4):
                    window = (timestamps[i + 4] - timestamps[i]).total_seconds()
                    if window < 600:  # 10 minutes
                        burst_score = 0.3  # Burst penalty
                        break

        factors = []
        if velocity > 10:
            score = min(100.0, velocity * 8.0 + burst_score * 100)
            factors.append(f"Critical velocity: {velocity:.1f} decisions/hour")
        elif velocity > 5:
            score = velocity * 5.0 + burst_score * 50
            factors.append(f"Elevated velocity: {velocity:.1f} decisions/hour")
        elif velocity > 2:
            score = velocity * 2.0
            factors.append(f"Normal velocity: {velocity:.1f} decisions/hour")
        else:
            score = 0.0

        if burst_score > 0:
            factors.append("Burst detected: 5+ decisions within 10 minutes")

        return min(100.0, score), factors

    async def _calculate_tier_score(
        self, decisions: List[Dict],
    ) -> Tuple[float, List[str]]:
        """Calculate tier distribution risk score."""
        if not decisions:
            return 0.0, []

        tier_counts: Dict[str, int] = {}
        for d in decisions:
            tier = d.get("tier", "T0")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        total = len(decisions)
        t2_count = tier_counts.get("T2", 0)
        t3_count = tier_counts.get("T3", 0)
        high_tier = t2_count + t3_count
        ratio = high_tier / total

        # T3 decisions are weighted more heavily
        score = (t2_count * 10.0 + t3_count * 25.0) / total
        score = min(100.0, score)

        factors = []
        if ratio > 0.3:
            factors.append(f"High-tier concentration: {high_tier}/{total} are T2/T3 ({t3_count} critical)")
        elif ratio > 0.1:
            factors.append(f"Moderate tier spread: {high_tier}/{total} high-tier decisions")

        return score, factors

    async def _calculate_evidence_gap_score(
        self, decisions: List[Dict], evidence: List[Dict],
    ) -> Tuple[float, List[str]]:
        """Calculate evidence gap risk score."""
        if not decisions:
            return 0.0, []

        evidence_per_decision = len(evidence) / len(decisions)

        # Check for decisions with zero evidence
        decision_ids = {d.get("id") for d in decisions}
        evidence_decision_ids = {e.get("decision_id") for e in evidence}
        unsupported = decision_ids - evidence_decision_ids
        unsupported_count = len(unsupported)

        factors = []
        if evidence_per_decision < 0.5:
            score = (1.0 - evidence_per_decision) * 100.0
            factors.append(f"Severe evidence gap: {evidence_per_decision:.1f} evidence per decision")
        elif evidence_per_decision < 1.0:
            score = (1.0 - evidence_per_decision) * 80.0
            factors.append(f"Moderate evidence gap: {evidence_per_decision:.1f} evidence per decision")
        else:
            score = 0.0

        if unsupported_count > 0:
            score = min(100.0, score + unsupported_count * 10.0)
            factors.append(f"{unsupported_count} decision(s) have zero supporting evidence")

        return score, factors

    # ──────────────────────────────────────────────
    # Heatmap generation
    # ──────────────────────────────────────────────

    async def generate_heatmap(
        self,
        workspace_id: str,
        modules: List[Dict[str, Any]],
    ) -> RiskHeatmap:
        """
        Generate risk heatmap by module.

        Each module is scored individually based on its staleness,
        pending decisions, and recent change volume.
        """
        cells = []
        max_score = 0.0
        total_score = 0.0
        critical_modules = []

        for module in modules:
            module_id = module.get("module_id", "unknown")
            module_name = module.get("name", module_id)

            stale_count = module.get("stale_evidence_count", 0)
            pending_count = module.get("pending_decisions", 0)
            change_count = module.get("recent_changes", 0)
            incident_count = module.get("past_incidents", 0)

            # Multi-factor module risk with diminishing returns
            risk_score = min(100.0, (
                stale_count * 12.0 +
                pending_count * 8.0 +
                change_count * 4.0 +
                incident_count * 20.0
            ))

            risk_level = self._score_to_level(risk_score)

            cell = RiskHeatmapCell(
                module_id=module_id,
                module_name=module_name,
                risk_score=risk_score,
                risk_level=risk_level,
                stale_evidence_count=stale_count,
                pending_decisions_count=pending_count,
                recent_changes_count=change_count,
            )
            cells.append(cell)

            max_score = max(max_score, risk_score)
            total_score += risk_score

            if risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                critical_modules.append(module_id)

        avg_score = total_score / len(cells) if cells else 0.0

        return RiskHeatmap(
            workspace_id=workspace_id,
            generated_at=datetime.now(timezone.utc),
            cells=cells,
            max_risk_score=max_score,
            avg_risk_score=avg_score,
            critical_modules=critical_modules,
        )

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _score_to_level(self, score: float) -> RiskLevel:
        """Convert numeric score to risk level."""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        elif score >= 20:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL

    def _build_component_scores(
        self, signals: List[RiskSignal],
    ) -> Dict[RiskCategory, float]:
        """Map new signal types back to legacy RiskCategory for backward compat."""
        component_scores: Dict[RiskCategory, float] = {
            RiskCategory.STALENESS: 0.0,
            RiskCategory.VELOCITY: 0.0,
            RiskCategory.AUTHORITY: 0.0,
            RiskCategory.EVIDENCE_GAP: 0.0,
        }
        _mapping = {
            SignalType.STALENESS: RiskCategory.STALENESS,
            SignalType.VELOCITY: RiskCategory.VELOCITY,
            SignalType.AUTHORITY: RiskCategory.AUTHORITY,
            SignalType.EVIDENCE_GAP: RiskCategory.EVIDENCE_GAP,
        }
        for s in signals:
            cat = _mapping.get(s.signal_type)
            if cat is not None:
                component_scores[cat] = s.score * 100.0
        return component_scores

    def _generate_recommendations(
        self,
        component_scores: Dict[RiskCategory, float],
        factors: List[str],
        signals: Optional[List[RiskSignal]] = None,
    ) -> List[str]:
        """Generate actionable recommendations based on risk signals."""
        recommendations = []

        if component_scores.get(RiskCategory.STALENESS, 0) > 50:
            recommendations.append(
                "🔄 Run fresh tests to update stale evidence. "
                "Consider scheduling automated evidence refresh."
            )

        if component_scores.get(RiskCategory.VELOCITY, 0) > 50:
            recommendations.append(
                "🐢 Decision velocity is high. Consider batch-reviewing "
                "decisions or enabling Archon cooldown periods."
            )

        if component_scores.get(RiskCategory.AUTHORITY, 0) > 50:
            recommendations.append(
                "🛡️ High concentration of T2/T3 decisions. "
                "Enable multi-reviewer quorum for critical changes."
            )

        if component_scores.get(RiskCategory.EVIDENCE_GAP, 0) > 50:
            recommendations.append(
                "📎 Collect more evidence before proceeding. "
                "Link test results, code reviews, or external references."
            )

        # Signal-specific recommendations
        if signals:
            for s in signals:
                if s.signal_type == SignalType.PATTERN_MATCH and s.score > 0.5:
                    recommendations.append(
                        "⚠️ Dangerous code patterns detected. "
                        "Require explicit council approval before deployment."
                    )
                if s.signal_type == SignalType.FILE_SENSITIVITY and s.score > 0.7:
                    recommendations.append(
                        "🔒 Sensitive files modified (auth, secrets, infrastructure). "
                        "Enable Sentinel security review."
                    )
                if s.signal_type == SignalType.BLAST_RADIUS and s.score > 0.6:
                    recommendations.append(
                        "💥 Large blast radius. Consider splitting into smaller, "
                        "focused changesets for safer incremental deployment."
                    )

        return recommendations[:5]  # Cap at 5 recommendations
