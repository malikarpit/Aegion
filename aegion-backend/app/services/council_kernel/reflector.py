"""
Cognitive Reflector — Phase 47: Real-Time Debate Pathology Detection.

Monitors council debates AS THEY HAPPEN and intervenes when reasoning
patterns degrade. The reflector is the council's immune system.

Detects 5 pathologies:
  1. Groupthink — all positions converge too early with high confidence
  2. Hallucination Cascade — multiple models cite the same non-existent fact
  3. Authority Bias — later models disproportionately agree with the first
  4. Circular Reasoning — model repeats its own argument from 2 rounds ago
  5. Anchoring — all quantitative estimates cluster around the first number

Gated by WorkspaceCouncilConfig.reflector_enabled (default: off).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ...core.logging import logger


class PathologyType(str, Enum):
    GROUPTHINK = "groupthink"
    HALLUCINATION_CASCADE = "hallucination_cascade"
    AUTHORITY_BIAS = "authority_bias"
    CIRCULAR_REASONING = "circular_reasoning"
    ANCHORING = "anchoring"


class InterventionAction(str, Enum):
    INJECT_CONTRARIAN = "inject_contrarian"       # Force a devil's advocate persona
    FLAG_CLAIMS = "flag_claims"                     # Mark specific claims for verification
    RANDOMIZE_ORDER = "randomize_order"             # Shuffle model ordering next round
    PRUNE_MODEL = "prune_model"                     # Remove the circular model
    PARALLEL_ESTIMATES = "parallel_estimates"        # Get independent estimates
    FLAG_FOR_HUMAN = "flag_for_human"                # Escalate to human review
    NO_ACTION = "no_action"


@dataclass
class Pathology:
    """A detected debate pathology."""
    type: PathologyType
    severity: float  # 0.0-1.0
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    intervention: InterventionAction = InterventionAction.NO_ACTION
    affected_models: List[str] = field(default_factory=list)


@dataclass
class ReflectionReport:
    """Post-debate summary of all detected pathologies."""
    debate_id: str
    rounds_analyzed: int
    pathologies: List[Pathology] = field(default_factory=list)
    interventions_taken: int = 0
    overall_health: float = 1.0  # 1.0 = healthy debate, 0.0 = severely pathological

    @property
    def has_issues(self) -> bool:
        return len(self.pathologies) > 0


class CognitiveReflector:
    """
    Monitors debates for pathological reasoning patterns and triggers interventions.

    Usage:
        reflector = CognitiveReflector(config)
        pathologies = reflector.analyze_round(round_responses, debate_history)
        for p in pathologies:
            intervention = reflector.intervene(p, debate_context)
    """

    def __init__(
        self,
        groupthink_threshold: float = 0.90,
        circular_window: int = 2,
    ):
        self.groupthink_threshold = groupthink_threshold
        self.circular_window = circular_window
        self._report_pathologies: List[Pathology] = []

    def analyze_round(
        self,
        round_responses: List[Dict[str, Any]],
        debate_history: List[List[Dict[str, Any]]],
        round_number: int,
    ) -> List[Pathology]:
        """
        Analyze a debate round for pathological patterns.

        Args:
            round_responses: Current round's responses [{model, position, confidence, ...}]
            debate_history:  All previous rounds
            round_number:    Current round (1-indexed)

        Returns list of detected pathologies.
        """
        pathologies = []

        # 1. Groupthink detection
        groupthink = self._detect_groupthink(round_responses, round_number)
        if groupthink:
            pathologies.append(groupthink)

        # 2. Authority bias
        authority = self._detect_authority_bias(round_responses, debate_history, round_number)
        if authority:
            pathologies.append(authority)

        # 3. Circular reasoning
        circular = self._detect_circular_reasoning(round_responses, debate_history, round_number)
        if circular:
            pathologies.extend(circular)

        # 4. Anchoring
        anchoring = self._detect_anchoring(round_responses)
        if anchoring:
            pathologies.append(anchoring)

        # 5. Hallucination cascade
        hallucination = self._detect_hallucination_cascade(round_responses)
        if hallucination:
            pathologies.append(hallucination)

        self._report_pathologies.extend(pathologies)
        return pathologies

    def intervene(self, pathology: Pathology) -> Dict[str, Any]:
        """
        Determine and return the intervention for a pathology.

        Returns a dict with instruction modifications for the next round.
        """
        interventions = {
            PathologyType.GROUPTHINK: {
                "action": InterventionAction.INJECT_CONTRARIAN,
                "prompt_prefix": (
                    "⚠️ GROUPTHINK ALERT: All models agreed too quickly in the previous round. "
                    "You MUST find at least one genuine flaw, risk, or alternative not yet discussed. "
                    "Do NOT agree with the majority unless you have NEW evidence. "
                    "Your job is to DISAGREE and find what others missed."
                ),
                "force_persona": "devils_advocate",
            },
            PathologyType.HALLUCINATION_CASCADE: {
                "action": InterventionAction.FLAG_CLAIMS,
                "prompt_prefix": (
                    "⚠️ VERIFICATION REQUIRED: The following claims from the previous round "
                    "could not be verified and may be hallucinated. "
                    "Do NOT repeat unverified claims. Only cite sources you are CERTAIN exist. "
                    f"Flagged claims: {', '.join(pathology.evidence.get('flagged_claims', []))}"
                ),
            },
            PathologyType.AUTHORITY_BIAS: {
                "action": InterventionAction.RANDOMIZE_ORDER,
                "prompt_prefix": (
                    "⚠️ INDEPENDENCE REQUIRED: You are answering INDEPENDENTLY. "
                    "Do NOT reference or agree with other models' positions. "
                    "Form your own position based ONLY on the evidence presented."
                ),
                "randomize_models": True,
            },
            PathologyType.CIRCULAR_REASONING: {
                "action": InterventionAction.PRUNE_MODEL,
                "prompt_prefix": (
                    "⚠️ CIRCULAR REASONING DETECTED: A model is repeating its previous argument "
                    "without adding new information. Advance the discussion with NEW evidence "
                    "or a DIFFERENT perspective."
                ),
                "prune_models": pathology.affected_models,
            },
            PathologyType.ANCHORING: {
                "action": InterventionAction.PARALLEL_ESTIMATES,
                "prompt_prefix": (
                    "⚠️ ANCHORING DETECTED: All estimates cluster around the same value. "
                    "Provide your estimate INDEPENDENTLY without considering other estimates. "
                    "Show your calculation methodology."
                ),
                "force_parallel": True,
            },
        }

        return interventions.get(pathology.type, {
            "action": InterventionAction.NO_ACTION,
        })

    def get_report(self, debate_id: str, rounds_analyzed: int) -> ReflectionReport:
        """Generate a post-debate reflection report."""
        health = 1.0
        for p in self._report_pathologies:
            health -= p.severity * 0.2  # Each pathology degrades health

        report = ReflectionReport(
            debate_id=debate_id,
            rounds_analyzed=rounds_analyzed,
            pathologies=self._report_pathologies,
            interventions_taken=sum(
                1 for p in self._report_pathologies
                if p.intervention != InterventionAction.NO_ACTION
            ),
            overall_health=max(0.0, round(health, 3)),
        )

        # Reset for next debate
        self._report_pathologies = []
        return report

    # ═══════════════════════════════════════════
    # Detection methods
    # ═══════════════════════════════════════════

    def _detect_groupthink(
        self,
        responses: List[Dict],
        round_number: int,
    ) -> Optional[Pathology]:
        """All positions converge to same verdict in early rounds."""
        if round_number > 2 or len(responses) < 3:
            return None

        # Extract verdicts/positions
        positions = []
        for r in responses:
            pos = r.get("position", r.get("response", "")).lower()
            if any(w in pos[:200] for w in ("approve", "agree", "yes", "support", "recommend")):
                positions.append("approve")
            elif any(w in pos[:200] for w in ("reject", "disagree", "no", "oppose", "against")):
                positions.append("reject")
            else:
                positions.append("neutral")

        if not positions:
            return None

        # Check if all positions are the same
        from collections import Counter
        counts = Counter(positions)
        majority_count = counts.most_common(1)[0][1]
        agreement_ratio = majority_count / len(positions)

        # Check confidence levels
        avg_confidence = sum(
            r.get("confidence", 0.5) for r in responses
        ) / len(responses)

        if agreement_ratio >= self.groupthink_threshold and avg_confidence > 0.75:
            return Pathology(
                type=PathologyType.GROUPTHINK,
                severity=agreement_ratio,
                description=(
                    f"All {len(responses)} models agreed ({counts.most_common(1)[0][0]}) "
                    f"in round {round_number} with avg confidence {avg_confidence:.2f}"
                ),
                evidence={
                    "agreement_ratio": agreement_ratio,
                    "avg_confidence": avg_confidence,
                    "positions": positions,
                },
                intervention=InterventionAction.INJECT_CONTRARIAN,
                affected_models=[r.get("model", "") for r in responses],
            )
        return None

    def _detect_authority_bias(
        self,
        responses: List[Dict],
        history: List[List[Dict]],
        round_number: int,
    ) -> Optional[Pathology]:
        """Later models disproportionately agree with the first model."""
        if round_number < 2 or len(responses) < 3:
            return None

        # Get the first model's position from round 1
        if not history or not history[0]:
            return None

        first_model_pos = history[0][0].get("position", history[0][0].get("response", ""))[:300].lower()

        # Check how many current responses echo the first model
        echo_count = 0
        for r in responses[1:]:  # Skip the first model itself
            current_pos = r.get("position", r.get("response", ""))[:300].lower()
            # Simple overlap check
            first_words = set(first_model_pos.split())
            current_words = set(current_pos.split())
            overlap = len(first_words & current_words) / max(len(first_words | current_words), 1)
            if overlap > 0.40:
                echo_count += 1

        echo_ratio = echo_count / max(len(responses) - 1, 1)
        if echo_ratio > 0.70:
            return Pathology(
                type=PathologyType.AUTHORITY_BIAS,
                severity=echo_ratio,
                description=f"{echo_count}/{len(responses)-1} models echoed the first model's position",
                evidence={"echo_ratio": echo_ratio, "echo_count": echo_count},
                intervention=InterventionAction.RANDOMIZE_ORDER,
                affected_models=[responses[0].get("model", "")],
            )
        return None

    def _detect_circular_reasoning(
        self,
        responses: List[Dict],
        history: List[List[Dict]],
        round_number: int,
    ) -> List[Pathology]:
        """Model repeats its own argument from N rounds ago."""
        if round_number <= self.circular_window or len(history) < self.circular_window:
            return []

        pathologies = []
        compare_round = history[round_number - 1 - self.circular_window]

        for current_resp in responses:
            model = current_resp.get("model", "")
            current_text = current_resp.get("position", current_resp.get("response", ""))[:500].lower()

            # Find this model's response from N rounds ago
            for old_resp in compare_round:
                if old_resp.get("model", "") == model:
                    old_text = old_resp.get("position", old_resp.get("response", ""))[:500].lower()

                    # Check similarity
                    current_words = set(current_text.split())
                    old_words = set(old_text.split())
                    if not current_words or not old_words:
                        continue

                    overlap = len(current_words & old_words) / max(len(current_words | old_words), 1)
                    if overlap > 0.60:
                        pathologies.append(Pathology(
                            type=PathologyType.CIRCULAR_REASONING,
                            severity=overlap,
                            description=f"Model {model} repeated its round {round_number - self.circular_window} argument (overlap: {overlap:.0%})",
                            evidence={"overlap": overlap, "window": self.circular_window},
                            intervention=InterventionAction.PRUNE_MODEL,
                            affected_models=[model],
                        ))
                    break

        return pathologies

    def _detect_anchoring(self, responses: List[Dict]) -> Optional[Pathology]:
        """All quantitative estimates cluster around the first number."""
        numbers = []
        for r in responses:
            text = r.get("position", r.get("response", ""))
            # Extract numbers that look like estimates
            found = re.findall(r'\b(\d+(?:\.\d+)?)\s*(?:%|ms|seconds|hours|days|usd|\$)', text.lower())
            if found:
                try:
                    numbers.append(float(found[0]))
                except (ValueError, IndexError):
                    pass

        if len(numbers) < 3:
            return None

        # Check if all numbers are within 20% of the first
        anchor = numbers[0]
        if anchor == 0:
            return None

        close_count = sum(1 for n in numbers[1:] if abs(n - anchor) / anchor < 0.20)
        close_ratio = close_count / max(len(numbers) - 1, 1)

        if close_ratio > 0.70:
            return Pathology(
                type=PathologyType.ANCHORING,
                severity=close_ratio,
                description=f"All estimates anchored around {anchor} (within 20%)",
                evidence={"anchor": anchor, "values": numbers, "close_ratio": close_ratio},
                intervention=InterventionAction.PARALLEL_ESTIMATES,
            )
        return None

    def _detect_hallucination_cascade(self, responses: List[Dict]) -> Optional[Pathology]:
        """Multiple models cite the same suspicious source/fact."""
        # Extract quoted sources and specific citations
        citations: Dict[str, int] = {}
        for r in responses:
            text = r.get("position", r.get("response", ""))
            # Find patterns like "according to [source]", "as stated in [doc]"
            found = re.findall(
                r'(?:according to|as (?:stated|documented|described) in|per|see|ref(?:erence)?:?)\s+["\']?([^"\'.,\n]{5,60})',
                text, re.IGNORECASE,
            )
            for citation in found:
                normalized = citation.strip().lower()
                citations[normalized] = citations.get(normalized, 0) + 1

        # Suspicious: same citation used by 3+ models (likely hallucinated)
        suspicious = {c: count for c, count in citations.items() if count >= 3}
        if suspicious:
            return Pathology(
                type=PathologyType.HALLUCINATION_CASCADE,
                severity=0.8,
                description=f"Potential hallucinated citations shared by multiple models",
                evidence={
                    "flagged_claims": list(suspicious.keys())[:5],
                    "citation_counts": suspicious,
                },
                intervention=InterventionAction.FLAG_CLAIMS,
            )
        return None


# Factory
def create_reflector(
    groupthink_threshold: float = 0.90,
    circular_window: int = 2,
) -> CognitiveReflector:
    return CognitiveReflector(
        groupthink_threshold=groupthink_threshold,
        circular_window=circular_window,
    )
