"""
Sentinel ↔ ACK Bridge — Phase 21-23: AI-Powered Security Analysis.

Extends the existing Sentinel risk engine with ACK council integration
for AI-powered code security scanning and drift detection.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ...core.logging import logger


# Weighted risk signal types
RISK_WEIGHTS = {
    "security": 5.0,
    "breaking_change": 4.0,
    "data_schema": 3.5,
    "performance": 3.0,
    "dependency": 2.5,
    "code_quality": 1.5,
    "configuration": 2.0,
    "secrets_exposure": 5.0,
}

# Pattern-based security detectors
_SECURITY_PATTERNS = [
    (r'(?:password|secret|token|api_key)\s*=\s*["\']', "Hardcoded secret detected", "secrets_exposure"),
    (r'eval\s*\(', "Dangerous eval() usage", "security"),
    (r'exec\s*\(', "Dangerous exec() usage", "security"),
    (r'subprocess\.(?:call|run|Popen)\s*\(.*shell\s*=\s*True', "Shell injection risk (shell=True)", "security"),
    (r'__import__\s*\(', "Dynamic import — possible code injection", "security"),
    (r'pickle\.loads?\s*\(', "Unsafe pickle deserialization", "security"),
    (r'yaml\.(?:load|unsafe_load)\s*\(', "Unsafe YAML loading", "security"),
    (r'(?:ALTER|DROP|CREATE)\s+TABLE', "Database schema change detected", "data_schema"),
    (r'\.raw\s*\(|\.execute\s*\(.*%s', "Raw SQL — possible injection", "security"),
    (r'CORS\s*\(.*allow_origins.*\*', "CORS wildcard origin", "security"),
    (r'verify\s*=\s*False', "SSL verification disabled", "security"),
    (r'chmod\s+777', "Overly permissive file permissions", "security"),
]

_DEPENDENCY_FILES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "pyproject.toml", "Pipfile", "Pipfile.lock", "requirements.txt",
    "Cargo.toml", "Cargo.lock", "go.mod", "go.sum",
}

_BREAKING_PATTERNS = [
    (r'(?:DELETE|DEPRECATED|BREAKING)', "Potential breaking change keyword"),
    (r'(?:removed|dropped|eliminated)\s+(?:support|compatibility)', "Compatibility removal"),
]


class SentinelACKBridge:
    """
    Enhanced risk analysis that combines pattern-matching with AI council evaluation.

    analyze_change():  Regex-based fast scan (synchronous)
    security_scan():   Deep AI-powered security review via ACK SENTINEL council
    detect_drift():    ADR compliance drift detection
    """

    def _client(self):
        from ...db.supabase_client import get_supabase_client
        return get_supabase_client()

    async def analyze_change(
        self,
        workspace_id: str,
        change: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Pattern-based risk analysis of a code change.

        Args:
            change: Dict with 'content' (str), 'files' (list), 'message' (str)

        Returns:
            risk_score:        Composite score (0.0 – 1.0)
            signals:           List of detected risk signals
            recommended_tier:  T0-T3 recommendation
        """
        signals = []
        content = str(change.get("content", ""))
        files = change.get("files", [])
        message = str(change.get("message", ""))

        # Security pattern scan
        for pattern, desc, signal_type in _SECURITY_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                signals.append(self._signal(workspace_id, signal_type, "high", desc))

        # Dependency file changes
        changed_deps = [f for f in files if any(f.endswith(d) for d in _DEPENDENCY_FILES)]
        if changed_deps:
            signals.append(self._signal(
                workspace_id, "dependency", "medium",
                f"Dependency files modified: {', '.join(changed_deps[:3])}",
            ))

        # Breaking change detection
        for pattern, desc in _BREAKING_PATTERNS:
            if re.search(pattern, content + " " + message, re.IGNORECASE):
                signals.append(self._signal(workspace_id, "breaking_change", "high", desc))

        # Large change detection
        lines = content.count("\n")
        if lines > 500:
            signals.append(self._signal(
                workspace_id, "code_quality", "medium",
                f"Large change ({lines} lines) — review carefully",
            ))

        # Persist signals (best-effort)
        for signal in signals:
            try:
                self._client().table("risk_signals").insert(signal).execute()
            except Exception:
                pass

        risk_score = min(1.0, sum(
            RISK_WEIGHTS.get(s["signal_type"], 1.0) for s in signals
        ) / 10.0)

        return {
            "risk_score": risk_score,
            "signals": signals,
            "signal_count": len(signals),
            "recommended_tier": self._recommend_tier(risk_score),
        }

    async def security_scan(
        self,
        workspace_id: str,
        code: str,
        language: str = "python",
    ) -> Dict[str, Any]:
        """
        Deep AI-powered security review via ACK SENTINEL council.

        Sends code to the council with security-focused personas and rubric scoring.
        """
        try:
            from ..council_kernel.engine import get_council_engine
            from ..council_kernel.types import CouncilType

            engine = get_council_engine()
            result = await engine.consult(
                workspace_id=workspace_id,
                query=(
                    f"Perform a comprehensive security audit of this {language} code. "
                    "Check for: injection attacks, authentication flaws, data exposure, "
                    "privilege escalation, OWASP Top 10, and supply chain risks.\n\n"
                    f"```{language}\n{code[:8000]}\n```"
                ),
                council_type=CouncilType.SENTINEL,
            )

            # Also run pattern scan for fast signals
            pattern_result = await self.analyze_change(workspace_id, {"content": code, "files": []})

            return {
                "ai_review": result.model_dump(),
                "pattern_signals": pattern_result["signals"],
                "combined_risk_score": max(
                    result.consensus_score, pattern_result["risk_score"]
                ),
            }
        except Exception as exc:
            logger.warning(f"AI security scan failed: {exc}")
            # Fallback to pattern-only scan
            return await self.analyze_change(workspace_id, {"content": code, "files": []})

    async def detect_drift(
        self,
        workspace_id: str,
    ) -> Dict[str, Any]:
        """
        Check if recent changes violate accepted Architecture Decision Records (ADRs).

        Compares recent timeline events against accepted ADRs using semantic similarity.
        """
        try:
            client = self._client()

            # Fetch accepted ADRs
            adrs_result = (
                client.table("adrs")
                .select("id,title,description,constraints")
                .eq("workspace_id", workspace_id)
                .eq("status", "accepted")
                .execute()
            )
            adrs = adrs_result.data or []

            # Fetch recent events
            events_result = (
                client.table("timeline_events")
                .select("id,event_type,entity_type,payload")
                .eq("workspace_id", workspace_id)
                .order("timestamp", desc=True)
                .limit(50)
                .execute()
            )
            events = events_result.data or []

            violations = []
            for adr in adrs:
                constraints = adr.get("constraints", [])
                if isinstance(constraints, str):
                    constraints = [constraints]
                for event in events:
                    event_desc = str(event.get("payload", {}))
                    for constraint in constraints:
                        if self._violates(event_desc, constraint):
                            violations.append({
                                "adr_id": adr["id"],
                                "adr_title": adr["title"],
                                "constraint": constraint,
                                "event_id": event["id"],
                                "event_type": event["event_type"],
                            })

            return {
                "drift_detected": len(violations) > 0,
                "violations": violations,
                "adrs_checked": len(adrs),
                "events_scanned": len(events),
            }
        except Exception as exc:
            logger.warning(f"Drift detection failed: {exc}")
            return {"drift_detected": False, "violations": [], "error": str(exc)}

    def _signal(self, workspace_id: str, signal_type: str, severity: str, description: str) -> Dict:
        return {
            "workspace_id": workspace_id,
            "signal_type": signal_type,
            "severity": severity,
            "source": "sentinel_auto",
            "description": description,
            "resolved": False,
        }

    def _recommend_tier(self, risk_score: float) -> int:
        if risk_score < 0.2:
            return 0
        if risk_score < 0.4:
            return 1
        if risk_score < 0.7:
            return 2
        return 3

    def _violates(self, event_description: str, constraint: str) -> bool:
        """
        Entity-based semantic drift detection.

        Two-tier check:
          1. Extract concepts (entities, tech terms, patterns) from both texts
          2. Compute Jaccard similarity on concepts — threshold 0.25
             (much more accurate than raw word overlap)
        """
        constraint_concepts = self._extract_concepts(constraint)
        event_concepts = self._extract_concepts(event_description)

        if not constraint_concepts or not event_concepts:
            # Fallback to word overlap if no concepts extracted
            c_words = set(constraint.lower().split())
            e_words = set(event_description.lower().split())
            return len(c_words & e_words) >= 3

        # Jaccard similarity on concept sets
        intersection = constraint_concepts & event_concepts
        union = constraint_concepts | event_concepts
        similarity = len(intersection) / max(len(union), 1)

        return similarity >= 0.25 or len(intersection) >= 2

    def _extract_concepts(self, text: str) -> set:
        """
        Extract meaningful concepts from text using entity-aware patterns.

        Targets: service names, technology terms, architectural patterns,
        file paths, API endpoints — the things that actually matter for drift.
        """
        concepts = set()
        lower = text.lower()

        # Service/component names (PascalCase, camelCase)
        for m in re.finditer(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', text):
            concepts.add(m.group(1).lower())

        # Technology terms
        tech_terms = {
            "redis", "kafka", "postgresql", "postgres", "mongodb", "mysql",
            "docker", "kubernetes", "k8s", "nginx", "graphql", "rest",
            "grpc", "websocket", "pgvector", "supabase", "firebase",
            "fastapi", "nextjs", "react", "typescript", "python",
            "microservice", "monolith", "serverless", "cloud run",
            "pubsub", "queue", "cache", "cdn", "s3", "gcs", "blob",
        }
        for term in tech_terms:
            if term in lower:
                concepts.add(term)

        # Architecture patterns
        patterns = {
            "event sourcing", "cqrs", "saga", "circuit breaker",
            "rate limit", "retry", "backoff", "idempotent", "eventual consistency",
            "strong consistency", "sharding", "replication", "failover",
            "blue-green", "canary", "rolling update", "a/b test",
        }
        for pattern in patterns:
            if pattern in lower:
                concepts.add(pattern)

        # Aegion-specific entity names
        aegion_entities = {
            "archon", "sentinel", "chronos", "noesis", "praxis",
            "council", "governance", "tier", "freeze", "drift",
            "knowledge graph", "decision pipeline", "reasoning chain",
        }
        for entity in aegion_entities:
            if entity in lower:
                concepts.add(entity)

        # File paths and module references
        for m in re.finditer(r'[\w/]+\.(?:py|ts|tsx|sql|yaml|json)\b', lower):
            concepts.add(m.group(0))

        # API endpoints
        for m in re.finditer(r'/api/v\d/[\w/-]+', lower):
            concepts.add(m.group(0))

        return concepts


# Singleton
_sentinel_bridge = None

def get_sentinel_bridge() -> SentinelACKBridge:
    global _sentinel_bridge
    if _sentinel_bridge is None:
        _sentinel_bridge = SentinelACKBridge()
    return _sentinel_bridge
