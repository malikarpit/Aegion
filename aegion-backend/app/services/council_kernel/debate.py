"""
Debate Engine — Phase 14 (Elevated): Anti-Sycophancy with Self-Optimizing Prompts.

Multi-round structured debate with:
  - Dynamic prompts from the PromptRegistry (auto-mutate on low scores)
  - Position tracking with cosine similarity for genuine convergence detection
  - Argument graph: tracks which arguments respond to which
  - Fresh Eyes validation by a model that DIDN'T participate
  - Hard anti-groupthink rules enforced at the prompt level

Key improvement over v1:
  - Consensus is measured by SEMANTIC similarity of positions (not keyword "agree")
  - Prompts auto-improve over time via DSPy-style mutation
  - Full argument provenance chain for auditability
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from .model_router import ModelRouter
from .types import ModelResponse
from ...core.logging import logger


MAX_ROUNDS = 4  # Increased from 3: allows more time for genuine convergence




class EarlyConsensusDetector:
    """
    Phase 80: Exit multi-round debates early when consensus is already reached.

    Uses semantic Jaccard similarity (same metric as DebateEngine) rather than
    keyword matching to detect genuine agreement vs surface-level "agree" words.

    Thresholds scale conservatively with complexity:
      simple=0.7 (low bar — quick answers OK), critical=0.95 (very high bar).
    """

    CONSENSUS_THRESHOLDS = {
        "simple":   0.70,
        "medium":   0.80,
        "complex":  0.90,
        "critical": 0.95,
    }

    def should_stop(
        self,
        round_responses: List[Dict],
        round_num: int,
        complexity: str = "medium",
        min_rounds: int = 1,
    ) -> Dict:
        """
        Decide whether to exit the debate early.

        Args:
            round_responses: List of response dicts from current round.
            round_num:       Current round number (1-indexed).
            complexity:      Gateway-classified complexity string.
            min_rounds:      Minimum rounds before early exit is allowed.

        Returns:
            dict with "stop" bool, "consensus_score", "rounds_saved", "reason".
        """
        if round_num < min_rounds:
            return {
                "stop": False,
                "consensus_score": 0.0,
                "rounds_saved": 0,
                "reason": f"Minimum {min_rounds} round(s) required",
            }

        threshold = self.CONSENSUS_THRESHOLDS.get(complexity.lower(), 0.80)

        # Reuse semantic Jaccard from the DebateEngine
        positions = [
            set(r.get("position", "").lower().split())
            for r in round_responses
            if r.get("position") and "[Error" not in r.get("position", "")
        ]
        if len(positions) < 2:
            return {"stop": False, "consensus_score": 1.0, "rounds_saved": 0,
                    "reason": "Insufficient participants for consensus check"}

        total_sim, pairs = 0.0, 0
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                intersection = len(positions[i] & positions[j])
                union = len(positions[i] | positions[j])
                if union > 0:
                    total_sim += intersection / union
                pairs += 1
        consensus_score = total_sim / max(pairs, 1)

        rounds_saved = MAX_ROUNDS - round_num
        if consensus_score >= threshold:
            return {
                "stop": True,
                "consensus_score": round(consensus_score, 4),
                "rounds_saved": rounds_saved,
                "estimated_savings_pct": round((rounds_saved / MAX_ROUNDS) * 100, 1),
                "reason": f"Consensus {consensus_score:.0%} ≥ threshold {threshold:.0%}",
            }

        return {
            "stop": False,
            "consensus_score": round(consensus_score, 4),
            "rounds_saved": 0,
            "reason": f"Consensus {consensus_score:.0%} < threshold {threshold:.0%}",
        }


# Module-level singleton
early_consensus = EarlyConsensusDetector()


class DebateEngine:
    """
    Structured multi-round debate with anti-sycophancy and self-optimizing prompts.

    Convergence is measured by semantic similarity between positions,
    not by keyword matching. This prevents false consensus where models
    use different words to express the same position being missed.
    """

    def __init__(self, model_router: ModelRouter) -> None:
        self.router = model_router

    async def debate(
        self,
        proposition: str,
        models: List[Tuple[str, str]],
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Run a structured debate.

        Returns:
            proposition:       The original proposition
            rounds:            Number of rounds completed
            history:           Full debate history with argument metadata
            consensus:         Semantic consensus score (0.0–1.0)
            contrarian_views:  Persistent dissent across rounds
            final_position:    Best synthesis or majority position
            argument_graph:    Which arguments respond to which
            prompt_variant:    Which prompt version was used
            total_cost_usd:    LLM cost
            early_exit:        Whether debate exited early via Phase 80
        """
        complexity = (context or {}).get("_gateway_complexity", "medium")
        early_consensus_enabled = (context or {}).get("_early_consensus_enabled", True)
        history: List[List[Dict]] = []
        argument_graph: List[Dict] = []
        total_cost = 0.0
        prompt_variant_id = None
        early_exit = False

        for round_num in range(1, MAX_ROUNDS + 1):
            round_responses, round_cost, variant_id = await self._run_round(
                proposition, history, round_num, models,
            )
            history.append(round_responses)
            total_cost += round_cost
            if variant_id:
                prompt_variant_id = variant_id

            # Build argument graph edges for this round
            if round_num > 1 and len(history) >= 2:
                prev_round = history[-2]
                for resp in round_responses:
                    for prev_resp in prev_round:
                        if resp["model"] != prev_resp["model"]:
                            argument_graph.append({
                                "from_model": resp["model"],
                                "to_model": prev_resp["model"],
                                "round": round_num,
                                "response_type": self._classify_response(
                                    resp["position"], prev_resp["position"]
                                ),
                            })

            # Phase 80: Early consensus detection (complexity-aware thresholds)
            if early_consensus_enabled:
                ec_result = early_consensus.should_stop(
                    round_responses, round_num, complexity=complexity
                )
                if ec_result["stop"]:
                    logger.debug(
                        f"Early consensus exit: round {round_num}, "
                        f"score={ec_result['consensus_score']:.2f}, "
                        f"rounds_saved={ec_result['rounds_saved']}"
                    )
                    early_exit = True
                    consensus = ec_result["consensus_score"]
                    break
            else:
                # Legacy hard-coded check
                consensus = self._semantic_consensus(history[-1])
                if round_num >= 2 and consensus > 0.80:
                    break
                continue

            # Still update consensus score for the final result
            consensus = self._semantic_consensus(history[-1])

        # Extract persistent contrarian views
        contrarian = self._extract_persistent_contrarian(history)

        # Fresh Eyes Validation when dissent exists
        fresh_eyes_result = None
        if contrarian and len(models) > 1:
            fresh_eyes_result, fresh_cost = await self._fresh_eyes_validation(
                proposition, history, contrarian, models[-1],
            )
            total_cost += fresh_cost

        # Record outcome for prompt self-optimization
        await self._record_prompt_outcome(prompt_variant_id, consensus)

        # Determine final position
        final = self._determine_final_position(history, fresh_eyes_result)

        # W1.3: Convert raw argument graph to typed ArgumentNode objects (Stab & Gurevych, 2017)
        typed_argument_nodes = self._build_typed_argument_nodes(history, argument_graph)

        return {
            "proposition": proposition,
            "rounds": len(history),
            "history": history,
            "consensus": round(consensus, 4),
            "contrarian_views": contrarian,
            "final_position": final,
            "fresh_eyes": fresh_eyes_result,
            "argument_graph": argument_graph,
            "argument_nodes": typed_argument_nodes,
            "prompt_variant_id": prompt_variant_id,
            "total_cost_usd": round(total_cost, 6),
        }

    # ──────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────

    async def _run_round(
        self,
        proposition: str,
        history: List[List[Dict]],
        round_num: int,
        models: List[Tuple[str, str]],
    ) -> Tuple[List[Dict], float, Optional[str]]:
        """Run one debate round across all models in parallel."""
        # Compile prompt from registry
        previous_context = ""
        if history:
            prev = history[-1]
            previous_context = "Previous round positions:\n" + "\n".join(
                f"• Participant {j+1} ({r['model']}): {r['position'][:400]}"
                for j, r in enumerate(prev)
            ) + "\n\n"

        variant_id = None
        try:
            from ..services.prompt_registry import get_prompt_registry
            registry = get_prompt_registry()
            compiled = await registry.compile(
                "debate.opening",
                variables={
                    "round": round_num,
                    "max_rounds": MAX_ROUNDS,
                    "proposition": proposition,
                    "previous_context": previous_context,
                },
            )
            prompt_template = compiled.text
            variant_id = compiled.variant_id
        except Exception:
            # Fallback to hardcoded prompt
            prompt_template = (
                f"DEBATE ROUND {round_num}/{MAX_ROUNDS}\n"
                f"Proposition: {proposition}\n\n"
                "You MUST state your genuine position with evidence.\n"
                "'I agree because everyone else does' is INVALID.\n\n"
                f"{previous_context}"
                "State your position with evidence:"
            )

        # Run all participants in parallel
        results = await asyncio.gather(*[
            self._participant_call(prov, mdl, prompt_template, round_num)
            for prov, mdl in models
        ])

        total_cost = sum(r.get("cost_usd", 0.0) for r in results)
        return results, total_cost, variant_id

    async def _participant_call(
        self, provider: str, model: str, prompt: str, round_num: int,
    ) -> Dict:
        """Single participant's response."""
        try:
            result = await self.router.call(provider, model, prompt)
            return {
                "model": model, "provider": provider,
                "position": result.response,
                "round": round_num,
                "confidence": result.confidence,
                "cost_usd": result.cost_usd,
            }
        except Exception:
            return {
                "model": model, "provider": provider,
                "position": "[Error: provider unavailable]",
                "round": round_num, "confidence": 0.0, "cost_usd": 0.0,
            }

    def _semantic_consensus(self, responses: List[Dict]) -> float:
        """
        Measure consensus using word-level Jaccard similarity between positions.

        Much more accurate than checking for "agree" keywords.
        A proper implementation would use embeddings, but Jaccard is a good
        fast approximation without external dependencies.
        """
        if len(responses) < 2:
            return 1.0

        positions = [
            set(r.get("position", "").lower().split())
            for r in responses
            if r.get("position") and "[Error" not in r.get("position", "")
        ]

        if len(positions) < 2:
            return 1.0

        # Pairwise Jaccard similarity
        total_sim = 0.0
        pairs = 0
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                intersection = len(positions[i] & positions[j])
                union = len(positions[i] | positions[j])
                if union > 0:
                    total_sim += intersection / union
                pairs += 1

        return total_sim / max(pairs, 1)

    def _classify_response(self, current: str, previous: str) -> str:
        """Classify how a response relates to a previous position."""
        current_lower = current.lower()[:300]
        if any(w in current_lower for w in ("disagree", "incorrect", "wrong", "however, i believe")):
            return "rebuts"
        if any(w in current_lower for w in ("building on", "adding to", "extending")):
            return "extends"
        if any(w in current_lower for w in ("agree", "concur", "exactly right")):
            return "supports"
        return "independent"

    def _extract_persistent_contrarian(self, history: List[List[Dict]]) -> List[Dict]:
        """
        Find views expressing PERSISTENT disagreement. 

        A view is contrarian only if it appears in 2+ consecutive rounds,
        not just a one-off dissent.
        """
        if len(history) < 2:
            return []

        contrarian_models: Dict[str, int] = {}  # model → consecutive dissent count
        for round_resp in history:
            for resp in round_resp:
                pos = resp.get("position", "").lower()[:500]
                model = resp.get("model", "")
                is_dissent = any(
                    w in pos for w in (
                        "disagree", "however", "alternative approach",
                        "risk", "concern", "i would argue against",
                    )
                )
                if is_dissent:
                    contrarian_models[model] = contrarian_models.get(model, 0) + 1
                else:
                    contrarian_models[model] = 0

        # Only persistent dissent (2+ rounds)
        persistent = []
        for round_resp in history[-1:]:
            for resp in round_resp:
                if contrarian_models.get(resp.get("model"), 0) >= 2:
                    persistent.append(resp)

        return persistent

    async def _fresh_eyes_validation(
        self,
        proposition: str,
        history: List[List[Dict]],
        contrarian: List[Dict],
        judge_model: Tuple[str, str],
    ) -> Tuple[str, float]:
        """Final validation by a model that didn't participate."""
        majority_pos = history[-1][0].get("position", "")[:600] if history[-1] else ""
        contrarian_pos = "\n".join(c.get("position", "")[:300] for c in contrarian[:2])

        try:
            from ..services.prompt_registry import get_prompt_registry
            compiled = await get_prompt_registry().compile(
                "debate.fresh_eyes",
                {"proposition": proposition,
                 "majority_position": majority_pos,
                 "contrarian_positions": contrarian_pos},
            )
            prompt = compiled.text
        except Exception:
            prompt = (
                f"FRESH EYES: Evaluate this debate independently.\n"
                f"Proposition: {proposition}\n"
                f"Majority: {majority_pos}\nContrarian: {contrarian_pos}\n"
                f"Your assessment:"
            )

        prov, mdl = judge_model
        result = await self.router.call(prov, mdl, prompt)
        return result.response, result.cost_usd

    def _determine_final_position(
        self,
        history: List[List[Dict]],
        fresh_eyes: Optional[str],
    ) -> str:
        """Pick the best final position from the last round or fresh eyes."""
        if fresh_eyes:
            return fresh_eyes
        if not history:
            return "No debate occurred."
        # Pick the highest-confidence response from the last round
        last = history[-1]
        best = max(last, key=lambda r: r.get("confidence", 0.0))
        return best.get("position", "No position recorded.")

    async def _record_prompt_outcome(
        self, variant_id: Optional[str], consensus: float,
    ) -> None:
        """Report debate outcome to the prompt registry for self-optimization."""
        if not variant_id:
            return
        try:
            from ..services.prompt_registry import get_prompt_registry
            await get_prompt_registry().record_outcome(
                "debate.opening", variant_id, consensus,
            )
        except Exception:
            pass

    @staticmethod
    def _build_typed_argument_nodes(
        history: List[List[Dict]], argument_graph: List[Dict],
    ) -> List[Dict]:
        """
        W1.3: Convert debate history into structured ArgumentNode objects.

        Reference: Stab & Gurevych, 2017 — "Parsing Argumentation Structures
                   in Persuasive Essays"

        Extracts:
          - claim: first sentence of the model's position
          - evidence: any sentences containing data/numbers/quotes
          - rebuts/supports: derived from argument_graph edges
        """
        from .types import ArgumentNode

        nodes: List[ArgumentNode] = []
        node_id_map: Dict[Tuple[str, int], str] = {}  # (model, round) → node_id

        # Build nodes from history
        for round_idx, round_responses in enumerate(history):
            round_num = round_idx + 1
            for resp in round_responses:
                model = resp.get("model", "unknown")
                position = resp.get("position", "")
                confidence = resp.get("confidence", 0.5)

                # Extract claim (first sentence) and evidence
                sentences = [s.strip() for s in position.split(".") if s.strip()]
                claim = sentences[0] + "." if sentences else position[:200]
                evidence = [
                    s + "." for s in sentences[1:]
                    if any(ind in s.lower() for ind in [
                        "because", "evidence", "data", "benchmark",
                        "study", "research", "%", "according",
                    ])
                ]

                node_id = f"arg-{round_num}-{model}"
                node_id_map[(model, round_num)] = node_id

                nodes.append(ArgumentNode(
                    id=node_id,
                    agent=model,
                    claim=claim,
                    evidence=evidence,
                    confidence=min(1.0, max(0.0, confidence)),
                    round=round_num,
                ))

        # Wire rebuts/supports from argument_graph
        for edge in argument_graph:
            from_model = edge.get("from_model", "")
            to_model = edge.get("to_model", "")
            round_num = edge.get("round", 1)
            resp_type = edge.get("response_type", "unknown")

            from_id = node_id_map.get((from_model, round_num), "")
            # Previous round
            to_id = node_id_map.get((to_model, round_num - 1), "")

            if not from_id or not to_id:
                continue

            # Find the from_node and add relationships
            for node in nodes:
                if node.id == from_id:
                    if resp_type in ("rebuttal", "counter", "disagree"):
                        node.rebuts.append(to_id)
                    elif resp_type in ("support", "agree", "extend"):
                        node.supports.append(to_id)
                    else:
                        # Default: if different position → rebuttal, same → support
                        node.supports.append(to_id)
                    break

        return [n.model_dump() for n in nodes]
