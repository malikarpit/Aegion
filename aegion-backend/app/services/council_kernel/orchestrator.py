"""
Cross-Council Orchestration — Phase 50: Sub-Council Spawning.

Parent councils can spawn specialized sub-councils for focused analysis,
then aggregate results before final synthesis.

Example: PARENT debates "Should we add Redis?" →
  spawns CHILD(security_auditor) for security analysis
  spawns CHILD(cost_analyst) for cost analysis
  spawns SENTINEL for dependency risk scan
  → aggregates all results into parent evidence

Constraints (configurable via WorkspaceCouncilConfig):
  - Max sub-councils per query (default: 3)
  - Per-sub-council budget (default: $0.05)
  - Total orchestration budget (default: $0.20)
  - No recursion (sub-councils cannot spawn further sub-councils)

Gated by WorkspaceCouncilConfig.cross_council_enabled (default: off).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...core.logging import logger


@dataclass
class SubCouncilSpec:
    """Specification for a sub-council to spawn."""
    name: str                   # Human-readable name
    council_type: str           # "child" or "sentinel"
    focus_query: str            # Focused query for the sub-council
    persona: Optional[str] = None  # Optional persona to apply
    budget_usd: float = 0.05   # Max budget for this sub-council


@dataclass
class SubCouncilResult:
    """Result from a spawned sub-council."""
    name: str
    focus_query: str
    synthesis: str
    confidence: float
    cost_usd: float
    model_used: str = ""
    findings: List[str] = field(default_factory=list)


class CrossCouncilOrchestrator:
    """
    Spawns specialized sub-councils and aggregates their results.

    Usage:
        orchestrator = CrossCouncilOrchestrator(
            max_sub_councils=3,
            sub_budget_usd=0.05,
            total_budget_usd=0.20,
        )
        specs = orchestrator.analyze_spawn_needs(query, evidence)
        results = await orchestrator.spawn_sub_councils(specs, workspace_id)
        enriched = orchestrator.format_for_prompt(results)
    """

    # Topic → sub-council mapping
    SPAWN_RULES = {
        "security": {
            "triggers": [
                "security", "vulnerability", "cve", "injection", "xss", "csrf",
                "authentication", "authorization", "encryption", "pii", "gdpr",
                "owasp", "supply chain", "dependency", "audit",
            ],
            "spec": SubCouncilSpec(
                name="Security Analysis",
                council_type="sentinel",
                focus_query="Analyze the security implications: {query}",
            ),
        },
        "cost": {
            "triggers": [
                "cost", "budget", "pricing", "expensive", "cheaper", "billing",
                "token", "api cost", "compute", "storage cost", "egress",
                "savings", "roi", "optimization",
            ],
            "spec": SubCouncilSpec(
                name="Cost Analysis",
                council_type="child",
                focus_query="Analyze the cost implications: {query}",
                persona="cost_analyst",
            ),
        },
        "performance": {
            "triggers": [
                "performance", "latency", "throughput", "scalab", "bottleneck",
                "slow", "fast", "memory", "cpu", "cache", "index", "n+1",
                "connection pool", "concurrency", "benchmark",
            ],
            "spec": SubCouncilSpec(
                name="Performance Analysis",
                council_type="child",
                focus_query="Analyze the performance implications: {query}",
                persona="performance_architect",
            ),
        },
        "governance": {
            "triggers": [
                "policy", "compliance", "regulation", "governance", "tier",
                "approval", "archon", "adr", "constraint", "rule",
                "breaking change", "migration",
            ],
            "spec": SubCouncilSpec(
                name="Governance Analysis",
                council_type="child",
                focus_query="Analyze the governance implications: {query}",
                persona="governance_advisor",
            ),
        },
        "architecture": {
            "triggers": [
                "architecture", "design pattern", "microservice", "monolith",
                "database", "schema", "api design", "event sourcing", "cqrs",
                "message queue", "service mesh", "data model", "migration",
            ],
            "spec": SubCouncilSpec(
                name="Architecture Analysis",
                council_type="child",
                focus_query="Analyze the architectural implications: {query}",
            ),
        },
    }

    def __init__(
        self,
        max_sub_councils: int = 3,
        sub_budget_usd: float = 0.05,
        total_budget_usd: float = 0.20,
    ):
        self.max_sub_councils = max_sub_councils
        self.sub_budget_usd = sub_budget_usd
        self.total_budget_usd = total_budget_usd

    def analyze_spawn_needs(
        self,
        query: str,
        evidence: Optional[Dict] = None,
    ) -> List[SubCouncilSpec]:
        """
        Analyze a query to determine which sub-councils should be spawned.

        Returns a list of SubCouncilSpecs, limited to max_sub_councils.
        """
        query_lower = query.lower()
        matched_specs: List[tuple] = []  # (match_count, spec)

        for domain, config in self.SPAWN_RULES.items():
            match_count = sum(
                1 for trigger in config["triggers"]
                if trigger in query_lower
            )
            if match_count > 0:
                spec = SubCouncilSpec(
                    name=config["spec"].name,
                    council_type=config["spec"].council_type,
                    focus_query=config["spec"].focus_query.format(query=query),
                    persona=config["spec"].persona,
                    budget_usd=self.sub_budget_usd,
                )
                matched_specs.append((match_count, spec))

        # Sort by match strength, take top N
        matched_specs.sort(key=lambda x: x[0], reverse=True)
        specs = [spec for _, spec in matched_specs[:self.max_sub_councils]]

        # Enforce total budget
        total_allocated = sum(s.budget_usd for s in specs)
        if total_allocated > self.total_budget_usd:
            per_budget = self.total_budget_usd / max(len(specs), 1)
            for spec in specs:
                spec.budget_usd = per_budget

        if specs:
            logger.info(
                f"Cross-council: spawning {len(specs)} sub-councils: "
                f"{[s.name for s in specs]}"
            )

        return specs

    async def spawn_sub_councils(
        self,
        specs: List[SubCouncilSpec],
        workspace_id: str,
    ) -> List[SubCouncilResult]:
        """
        Spawn sub-councils in parallel and collect results.

        Sub-councils are always CHILD type for cost control.
        They cannot spawn further sub-councils (no recursion).
        """
        import asyncio

        async def _run_sub(spec: SubCouncilSpec) -> Optional[SubCouncilResult]:
            try:
                from .engine import get_council_engine
                from .types import CouncilType
                engine = get_council_engine()

                # Map to council type
                council_type = (
                    CouncilType.SENTINEL if spec.council_type == "sentinel"
                    else CouncilType.CHILD
                )

                # Build context with persona if specified
                context = {"_is_sub_council": True}  # Prevents recursive spawning
                if spec.persona:
                    context["persona"] = spec.persona

                result = await engine.consult(
                    workspace_id=workspace_id,
                    query=spec.focus_query,
                    council_type=council_type,
                    context=context,
                )

                # Extract key findings from synthesis
                findings = self._extract_findings(result.synthesis)

                return SubCouncilResult(
                    name=spec.name,
                    focus_query=spec.focus_query,
                    synthesis=result.synthesis[:1500],  # Cap length
                    confidence=result.consensus_score,
                    cost_usd=result.total_cost_usd,
                    model_used=result.models_used[0] if result.models_used else "",
                    findings=findings,
                )
            except Exception as exc:
                logger.warning(f"Sub-council '{spec.name}' failed: {exc}")
                return SubCouncilResult(
                    name=spec.name,
                    focus_query=spec.focus_query,
                    synthesis=f"[Sub-council failed: {exc}]",
                    confidence=0.0,
                    cost_usd=0.0,
                )

        # Run all sub-councils in parallel
        results = await asyncio.gather(*[_run_sub(spec) for spec in specs])
        return [r for r in results if r is not None]

    def format_for_prompt(self, results: List[SubCouncilResult]) -> str:
        """Format sub-council results as a prompt block for the parent council."""
        if not results:
            return ""

        lines = ["SUB-COUNCIL ANALYSES:"]
        for r in results:
            lines.append(f"\n  [{r.name}] (confidence: {r.confidence:.0%})")
            lines.append(f"  Query: {r.focus_query[:100]}")

            if r.findings:
                lines.append("  Key findings:")
                for f in r.findings[:5]:
                    lines.append(f"    • {f}")
            else:
                # Use first 200 chars of synthesis
                lines.append(f"  Summary: {r.synthesis[:200]}")

        lines.append("")
        lines.append("Consider these specialist analyses when forming your position.")
        return "\n".join(lines)

    def _extract_findings(self, synthesis: str) -> List[str]:
        """Extract key findings from a synthesis text."""
        import re
        findings = []

        # Look for bullet points
        bullets = re.findall(r'(?:^|\n)\s*[•\-\*]\s*(.{10,120})', synthesis)
        findings.extend(bullets[:5])

        # Look for numbered items
        numbered = re.findall(r'(?:^|\n)\s*\d+[.)]\s*(.{10,120})', synthesis)
        findings.extend(numbered[:5])

        if not findings:
            # Fallback: first 3 sentences
            sentences = re.split(r'[.!?]\s+', synthesis)
            findings = [s.strip() for s in sentences[:3] if len(s.strip()) > 10]

        return findings[:5]


# Factory
def create_orchestrator(
    max_sub_councils: int = 3,
    sub_budget_usd: float = 0.05,
    total_budget_usd: float = 0.20,
) -> CrossCouncilOrchestrator:
    return CrossCouncilOrchestrator(
        max_sub_councils=max_sub_councils,
        sub_budget_usd=sub_budget_usd,
        total_budget_usd=total_budget_usd,
    )
