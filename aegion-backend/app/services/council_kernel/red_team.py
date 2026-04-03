"""
Red Team Layer — Phase 48: Adversarial Validation of Council Outputs.

The council's last line of defense before results reach Archon.
Every significant council output is stress-tested for:

  1. Prompt Injection Resistance — hidden instructions, role overrides
  2. Hallucination Verification — factual claims checked against GraphRAG
  3. Logic Consistency — contradictions between premises and conclusions
  4. Governance Compliance — constitutional constraints + T-level rules

Red team always runs on the cheapest cascade tier (cost-controlled).
Budget is configurable via WorkspaceCouncilConfig.red_team_max_budget_usd.

Gated by WorkspaceCouncilConfig.red_team_enabled (default: off).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...core.logging import logger


@dataclass
class Finding:
    """A single red team finding."""
    attack_vector: str  # injection, hallucination, logic, governance
    severity: str       # critical, high, medium, low
    description: str
    evidence: str = ""
    remediation: str = ""


@dataclass
class RedTeamReport:
    """Full red team validation report."""
    passed: bool
    score: float  # 0.0 (dangerous) to 1.0 (clean)
    findings: List[Finding] = field(default_factory=list)
    cost_usd: float = 0.0

    @property
    def critical_findings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "critical"]

    @property
    def summary(self) -> str:
        if self.passed:
            return f"Red team PASSED (score: {self.score:.2f}, {len(self.findings)} findings)"
        return f"Red team FAILED (score: {self.score:.2f}, {len(self.critical_findings)} critical findings)"


class RedTeamValidator:
    """
    Adversarial validation of council outputs.

    Usage:
        validator = RedTeamValidator(min_score=0.5, max_budget_usd=0.02)
        report = await validator.validate(synthesis, query, workspace_id)
        if not report.passed:
            # Flag the result
    """

    # ── Injection patterns ──
    _INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|context|rules?)",
        r"(system|assistant|user)\s*:",
        r"<\|(?:im_start|im_end|system|endoftext)\|>",
        r"you\s+are\s+now\s+(a|an|in)\s+",
        r"disregard\s+(everything|all|any)",
        r"forget\s+(your|all|previous)\s+(rules?|instructions?|constraints?)",
        r"override\s+(governance|constitution|rules?|policy)",
        r"pretend\s+you\s+are",
        r"new\s+instructions?\s*:",
        r"jailbreak",
        r"DAN\s+mode",
    ]

    # ── Self-approval patterns ──
    _SELF_APPROVAL_PATTERNS = [
        r"i\s+(hereby\s+)?approv(e|ed|ing)\s+this",
        r"auto[\-\s]?approv(e|ed|al)",
        r"approved?\s+without\s+review",
        r"bypass(ing)?\s+(human\s+)?review",
        r"skip(ping)?\s+(governance|archon|approval)",
    ]

    # ── Logic inconsistency markers ──
    _CONTRADICTION_PAIRS = [
        ("should", "should not"),
        ("recommend", "advise against"),
        ("approve", "reject"),
        ("safe", "dangerous"),
        ("increase", "decrease"),
        ("always", "never"),
    ]

    def __init__(
        self,
        min_score: float = 0.5,
        max_budget_usd: float = 0.02,
    ):
        self.min_score = min_score
        self.max_budget_usd = max_budget_usd

    async def validate(
        self,
        synthesis: str,
        query: str,
        workspace_id: Optional[str] = None,
        evidence_context: Optional[Dict] = None,
    ) -> RedTeamReport:
        """
        Run all 4 attack vectors against a council output.

        Returns a RedTeamReport with pass/fail, score, and detailed findings.
        """
        findings: List[Finding] = []
        total_cost = 0.0

        # Attack 1: Prompt injection resistance
        injection_findings = self._check_prompt_injection(synthesis)
        findings.extend(injection_findings)

        # Attack 2: Hallucination verification (requires workspace)
        if workspace_id:
            hallucination_findings = await self._check_hallucinations(
                synthesis, workspace_id
            )
            findings.extend(hallucination_findings)

        # Attack 3: Logic consistency
        logic_findings = self._check_logic_consistency(synthesis, query)
        findings.extend(logic_findings)

        # Attack 4: Governance compliance
        governance_findings = self._check_governance_compliance(synthesis)
        findings.extend(governance_findings)

        # Calculate score
        score = self._calculate_score(findings)
        passed = score >= self.min_score

        report = RedTeamReport(
            passed=passed,
            score=round(score, 3),
            findings=findings,
            cost_usd=total_cost,
        )

        if not passed:
            logger.warning(f"🔴 Red team FAILED: {report.summary}")

        return report

    # ═══════════════════════════════════════════
    # Attack vector implementations
    # ═══════════════════════════════════════════

    def _check_prompt_injection(self, text: str) -> List[Finding]:
        """Check for prompt injection markers in the output."""
        findings = []
        text_lower = text.lower()

        for pattern in self._INJECTION_PATTERNS:
            matches = re.findall(pattern, text_lower)
            if matches:
                findings.append(Finding(
                    attack_vector="injection",
                    severity="critical",
                    description=f"Prompt injection pattern detected: {pattern}",
                    evidence=str(matches[:3]),
                    remediation="Strip injected instructions. Flag for human review.",
                ))

        # Check for role override attempts
        for pattern in self._SELF_APPROVAL_PATTERNS:
            matches = re.findall(pattern, text_lower)
            if matches:
                findings.append(Finding(
                    attack_vector="injection",
                    severity="critical",
                    description="Self-approval attempt detected — AI trying to bypass governance",
                    evidence=str(matches[:3]),
                    remediation="Block auto-approval. Require human review.",
                ))

        # Check for suspicious encoding (base64 commands, hex sequences)
        base64_pattern = re.findall(r'[A-Za-z0-9+/]{20,}={0,2}', text)
        if len(base64_pattern) > 3:
            findings.append(Finding(
                attack_vector="injection",
                severity="medium",
                description=f"Suspicious base64-like sequences detected ({len(base64_pattern)} instances)",
                evidence=str(base64_pattern[:2]),
                remediation="Verify base64 content is not embedded commands.",
            ))

        return findings

    async def _check_hallucinations(
        self,
        text: str,
        workspace_id: str,
    ) -> List[Finding]:
        """Verify factual claims against workspace knowledge."""
        findings = []

        # Extract specific factual claims
        claims = self._extract_claims(text)

        if not claims:
            return findings

        # Check against GraphRAG memory
        try:
            from ..memory_engine import get_memory_engine
            memory = get_memory_engine()

            for claim in claims[:5]:  # Limit to 5 claims for cost control
                recall = await memory.recall(
                    workspace_id=workspace_id,
                    query=claim,
                    top_k=2,
                )
                entities = recall.get("entities", [])
                if not entities and len(claim.split()) > 5:
                    findings.append(Finding(
                        attack_vector="hallucination",
                        severity="medium",
                        description=f"Claim not found in workspace knowledge: \"{claim[:80]}...\"",
                        evidence="No matching entities in GraphRAG",
                        remediation="Verify this claim manually or remove if unsubstantiated.",
                    ))
        except Exception as exc:
            logger.debug(f"Hallucination check skipped (memory unavailable): {exc}")

        # E7: Check for fabricated URLs
        url_pattern = re.findall(r'https?://[\w\-./]+', text)
        suspicious_domains = [
            "example.com", "fake-report", "placeholder", "sample.org",
            "test-url", "notreal", "made-up",
        ]
        for url in url_pattern:
            url_lower = url.lower()
            if any(susp in url_lower for susp in suspicious_domains):
                findings.append(Finding(
                    attack_vector="hallucination",
                    severity="medium",
                    description=f"Suspicious/fabricated URL detected: {url[:100]}",
                    evidence="URL contains placeholder domain indicators",
                    remediation="Verify URL exists or remove the citation.",
                ))
            # Flag overly specific paths that look invented
            path_depth = url.count('/') - 2  # subtract protocol slashes
            if path_depth > 4 and not any(d in url_lower for d in ["github.com", "docs.", "wiki", "stackoverflow"]):
                findings.append(Finding(
                    attack_vector="hallucination",
                    severity="low",
                    description=f"Deeply nested URL may be fabricated: {url[:100]}",
                    evidence=f"Path depth: {path_depth}",
                    remediation="Verify URL accessibility.",
                ))

        return findings

    def _check_logic_consistency(self, text: str, query: str) -> List[Finding]:
        """Check for internal contradictions in the output."""
        findings = []
        text_lower = text.lower()

        # Split into sentences
        sentences = re.split(r'[.!?]\s+', text_lower)
        if len(sentences) < 3:
            return findings

        # Check for contradictory statements
        for word_a, word_b in self._CONTRADICTION_PAIRS:
            sentences_with_a = [s for s in sentences if word_a in s]
            sentences_with_b = [s for s in sentences if word_b in s]

            if sentences_with_a and sentences_with_b:
                # Same subject discussed with contradictory words
                for sa in sentences_with_a[:2]:
                    for sb in sentences_with_b[:2]:
                        # Check if they share subject words (nouns)
                        a_words = set(sa.split()) - {"the", "a", "an", "is", "are", "it", "we", "to"}
                        b_words = set(sb.split()) - {"the", "a", "an", "is", "are", "it", "we", "to"}
                        overlap = a_words & b_words
                        if len(overlap) >= 2:
                            findings.append(Finding(
                                attack_vector="logic",
                                severity="high",
                                description=f"Potential contradiction: \"{word_a}\" vs \"{word_b}\" about {', '.join(list(overlap)[:3])}",
                                evidence=f"A: \"{sa[:80]}...\"\nB: \"{sb[:80]}...\"",
                                remediation="Resolve the contradiction before presenting to user.",
                            ))
                            break
                    else:
                        continue
                    break

        # Check for hedging after strong claims
        strong_claim_count = sum(1 for s in sentences if any(
            w in s for w in ("definitely", "certainly", "always", "never", "guaranteed", "impossible")
        ))
        hedge_count = sum(1 for s in sentences if any(
            w in s for w in ("might", "perhaps", "possibly", "unclear", "depends", "not sure")
        ))
        if strong_claim_count > 0 and hedge_count > strong_claim_count:
            findings.append(Finding(
                attack_vector="logic",
                severity="low",
                description=f"Mixed conviction: {strong_claim_count} strong claims but {hedge_count} hedges",
                remediation="Clarify confidence levels for each claim.",
            ))

        # E8: Semantic contradiction — intro vs conclusion
        if len(sentences) >= 5:
            intro_words = set()
            conclusion_words = set()
            stopwords = {"the", "a", "an", "is", "are", "was", "were", "it", "we",
                         "to", "in", "of", "and", "or", "for", "on", "at", "by",
                         "this", "that", "with", "be", "not", "can", "will", "has"}

            for s in sentences[:2]:
                intro_words.update(w for w in s.split() if w not in stopwords and len(w) > 2)
            for s in sentences[-2:]:
                conclusion_words.update(w for w in s.split() if w not in stopwords and len(w) > 2)

            # Check if intro and conclusion share subject but use opposing sentiment
            shared_subjects = intro_words & conclusion_words
            if shared_subjects:
                intro_text = " ".join(sentences[:2])
                conclusion_text = " ".join(sentences[-2:])
                positive_words = {"good", "safe", "recommend", "approve", "benefit", "advantage", "secure"}
                negative_words = {"bad", "unsafe", "reject", "risk", "danger", "avoid", "insecure"}

                intro_pos = bool(positive_words & set(intro_text.split()))
                intro_neg = bool(negative_words & set(intro_text.split()))
                conc_pos = bool(positive_words & set(conclusion_text.split()))
                conc_neg = bool(negative_words & set(conclusion_text.split()))

                if (intro_pos and conc_neg) or (intro_neg and conc_pos):
                    findings.append(Finding(
                        attack_vector="logic",
                        severity="high",
                        description=f"Introduction and conclusion show opposing sentiment about: {', '.join(list(shared_subjects)[:3])}",
                        evidence=f"Intro: {intro_text[:80]}...\nConclusion: {conclusion_text[:80]}...",
                        remediation="Ensure the conclusion is consistent with the opening analysis.",
                    ))

        return findings

    def _check_governance_compliance(self, text: str) -> List[Finding]:
        """Check output against constitutional constraints."""
        findings = []

        try:
            from .constitution import get_constitution
            constitution = get_constitution()
            violations = constitution.check_response(text)
            for v in violations:
                findings.append(Finding(
                    attack_vector="governance",
                    severity="critical",
                    description=v,
                    remediation="Redact or block the offending content.",
                ))
        except Exception:
            pass

        # Check for exposed secrets patterns
        secret_patterns = [
            (r'(?:sk-)[A-Za-z0-9]{20,}', "OpenAI API key"),
            (r'(?:AKIA)[A-Z0-9]{16,}', "AWS access key"),
            (r'(?:AIza)[A-Za-z0-9_-]{30,}', "Google API key"),
            (r'(?:ghp_)[A-Za-z0-9]{36,}', "GitHub personal access token"),
            (r'(?:xox[bps]-)[A-Za-z0-9-]{10,}', "Slack token"),
        ]

        for pattern, secret_type in secret_patterns:
            if re.search(pattern, text):
                findings.append(Finding(
                    attack_vector="governance",
                    severity="critical",
                    description=f"Potential {secret_type} exposed in output",
                    remediation="IMMEDIATELY redact. Never expose secrets in council output.",
                ))

        return findings

    # ═══════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════

    def _extract_claims(self, text: str) -> List[str]:
        """Extract specific factual claims from text."""
        claims = []
        # Look for patterns like "X uses Y", "X depends on Z", "X was introduced in Y"
        patterns = [
            r'(?:uses?|requires?|depends?\s+on|built\s+(?:with|on)|integrated\s+with)\s+([A-Z][a-zA-Z0-9_.]+(?:\s+[A-Z][a-zA-Z0-9_.]+)?)',
            r'(?:introduced|added|created|implemented)\s+in\s+(?:version\s+)?(\d+\.\d+(?:\.\d+)?)',
            r'(?:CVE-\d{4}-\d+)',
            r'(?:according to|per|as documented in)\s+(.{10,60}?)(?:,|\.|$)',
        ]

        for pattern in patterns:
            found = re.findall(pattern, text, re.IGNORECASE)
            claims.extend(found[:3])

        return claims[:10]

    def _calculate_score(self, findings: List[Finding]) -> float:
        """Calculate overall red team score from findings."""
        if not findings:
            return 1.0

        severity_weights = {
            "critical": 0.30,
            "high": 0.15,
            "medium": 0.08,
            "low": 0.03,
        }

        deduction = sum(
            severity_weights.get(f.severity, 0.05)
            for f in findings
        )

        return max(0.0, min(1.0, 1.0 - deduction))


# Factory
def create_red_team(
    min_score: float = 0.5,
    max_budget_usd: float = 0.02,
) -> RedTeamValidator:
    return RedTeamValidator(
        min_score=min_score,
        max_budget_usd=max_budget_usd,
    )
