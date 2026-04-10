"""
Core Council Engine — Phase 8 (Enhanced): ACK Orchestrator.

The single entry point for all AEGION Council operations. Ties together:
  1. SemanticCache       — pgvector-backed semantic dedup (Phase 11)
  2. PromptCompressor    — LLMLingua-2 token reduction (Phase 12)
  3. Complexity Classifier → CouncilProfile (Phase 8 heuristic → Phase 77 DistilBERT)
  4. ModelRouter          — 9 provider abstraction (Phase 9 Enhanced)
  5. LLMCascade           — FrugalGPT multi-tier cost optimization (Phase 10 Enhanced)
  6. PeerReviewEngine     — 3-stage adversarial hallucination reduction (Phase 13)
  7. DebateEngine         — Anti-sycophancy structured debate (Phase 14)
  8. RubricEngine         — Weighted rubric scoring (Phase 15)
  9. PersonaEngine        — 6 AEGION expert personas (Phase 16)
 10. EvidenceManager      — Workspace context from knowledge graph + timeline + risks (Phase 17)
 11. ConstitutionalAI     — Hard constraint enforcement (Phase 46)
 12. CognitiveReflector   — Debate pathology detection (Phase 47)
 13. RedTeamValidator     — Adversarial output validation (Phase 48)
 14. TemporalMemory       — Historical decision context (Phase 49)
 15. CrossCouncilOrchestrator — Sub-council spawning (Phase 50)
 16. PromptRegistry       — DSPy-style self-optimizing prompts
 17. WorkspaceCouncilConfig — Per-workspace feature toggles

Council routing strategy:
  CHILD        → FrugalGPT cascade (cost-optimized single model)
  DISTILLATION → Single frontier model with managed prompts
  PARENT       → Full council: constitution → evidence → temporal → MCTS → persona → debate → reflector → peer review → rubric → red team → synthesis
  SENTINEL     → Parallel security-focused models + persona + rubric + red team

All advanced features are gated by WorkspaceCouncilConfig (per-workspace settings).
Nothing is hardcoded — everything configurable through the settings page.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from ...core.logging import logger
from .cascade import LLMCascade
from .model_router import ModelRouter, MODEL_CATALOG
from .types import CouncilProfile, CouncilResult, CouncilType, ModelResponse


# ──────────────────────────────────────────────────────────────────────────────
# Lightweight in-process semantic cache (Phase 11 upgrades to pgvector)
# ──────────────────────────────────────────────────────────────────────────────

class _InProcessCache:
    """
    Simple in-process semantic cache using exact + normalised key matching.

    Phase 11 (SemanticCache) backs this with pgvector cosine similarity in Supabase.
    This exists as a zero-dependency fallback when sentence-transformers isn't installed.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict] = {}

    def _key(self, workspace_id: str, query: str) -> str:
        return f"{workspace_id}::{query.strip().lower()}"

    def get(self, workspace_id: str, query: str) -> Optional[Dict]:
        return self._store.get(self._key(workspace_id, query))

    def put(self, workspace_id: str, query: str, response_text: str, model: str) -> None:
        self._store[self._key(workspace_id, query)] = {
            "response_text": response_text,
            "response_model": model,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Council Engine
# ──────────────────────────────────────────────────────────────────────────────

class CouncilEngine:
    """
    Main orchestrator for all ACK operations.

    Usage:
        engine = CouncilEngine()
        await engine.configure({"openai_key": "sk-...", "deepseek_key": "..."})
        result = await engine.consult(workspace_id, query, CouncilType.CHILD)
    """

    def __init__(self) -> None:
        self.model_router = ModelRouter()
        self.cascade = LLMCascade(self.model_router)
        self._cache = _InProcessCache()

    async def configure(self, user_api_keys: Dict[str, Any]) -> None:
        """Configure LLM providers from user-supplied keys (call at startup or on key update)."""
        await self.model_router.configure_from_user_keys(user_api_keys)
        logger.info(
            f"CouncilEngine configured with providers: {list(self.model_router.providers.keys())}"
        )

    # ──────────────────────────────────────────────
    # Primary public API
    # ──────────────────────────────────────────────

    def _get_config(self, workspace_id: str):
        """Get the workspace council config (all feature toggles + budgets)."""
        try:
            from ..model_registry import get_model_registry
            return get_model_registry().get_council_config(workspace_id)
        except Exception:
            from ..model_registry import WorkspaceCouncilConfig
            return WorkspaceCouncilConfig()

    async def consult(
        self,
        workspace_id: str,
        query: str,
        council_type: CouncilType,
        context: Optional[Dict] = None,
        is_sub_council: bool = False,
    ) -> CouncilResult:
        """
        Run a full council consultation.

        Pipeline:
          0. Constitutional AI check (if enabled)
          1. Semantic cache lookup
          2. Classify complexity
          3. Route: CHILD | DISTILLATION | PARENT | SENTINEL
          4. Cache result
          5. Cost tracking

        All advanced features gated by WorkspaceCouncilConfig.
        """
        start_ms = int(time.monotonic() * 1000)
        context = context or {}
        context["_is_sub_council"] = is_sub_council
        config = self._get_config(workspace_id)

        # Step 0 — Constitutional AI pre-check (safety-critical, ON by default)
        if config.constitution_enforcement:
            try:
                from .constitution import get_constitution
                violations = get_constitution().check_query(query)
                if violations and config.constitution_block_on_violation:
                    logger.warning(f"Constitutional BLOCK: {violations}")
                    return CouncilResult(
                        council_type=council_type,
                        profile=CouncilProfile.TRIVIAL,
                        query=query,
                        synthesis="⛔ BLOCKED BY CONSTITUTIONAL AI: " + "; ".join(violations),
                        individual_responses=[],
                        consensus_score=0.0,
                        dissenting_views=[],
                        total_cost_usd=0.0,
                        total_tokens=0,
                        total_latency_ms=int(time.monotonic() * 1000) - start_ms,
                        cache_hit=False,
                        models_used=[],
                        providers_used=[],
                        rounds_completed=0,
                    )
            except Exception as exc:
                logger.debug(f"Constitution check skipped: {exc}")

        # Step 0.5 — Prompt Gateway & Intent Clarification (Phase 76)
        if config.gateway_enabled:
            try:
                from .prompt_gateway import prompt_gateway
                
                # Check for explicit skip flag in context
                if not context.get("skip_gateway", False):
                    # We inject the engine's model_router so it shares the global registered providers
                    prompt_gateway.router = self.model_router
                    
                    gateway_result = await prompt_gateway.process(workspace_id, query)
                    if gateway_result["needs_clarification"]:
                        logger.info(f"Gateway intercepted query. Ambiguity score: {gateway_result['analysis'].get('ambiguity_score', 'N/A')}")
                        return CouncilResult(
                            council_type=council_type,
                            profile=CouncilProfile.TRIVIAL,
                            query=query,
                            synthesis="⛔ NEEDS CLARIFICATION: " + " ".join(gateway_result["clarifying_questions"]),
                            individual_responses=[],
                            consensus_score=0.0,
                            dissenting_views=[],
                            total_cost_usd=gateway_result["gateway_cost_usd"],
                            total_tokens=0,
                            total_latency_ms=int(time.monotonic() * 1000) - start_ms,
                            cache_hit=False,
                            models_used=list(prompt_gateway.GATEWAY_MODEL),  # Fix: tuple → List[str]
                            providers_used=[],
                            rounds_completed=0,
                        )

                    # Forward Gateway analysis downstream so _classify() and AdaptiveCouncil can use it
                    context["_gateway_complexity"] = gateway_result.get("complexity", "medium")
                    context["_gateway_intent"] = gateway_result["analysis"].get("intent", "general")

                    # Update query to the optimized token-efficient version
                    query = gateway_result["optimized_prompt"]
                    logger.debug(f"Gateway optimization savings: ~{gateway_result['token_savings_estimate']} tokens")
            except Exception as exc:
                logger.warning(f"Gateway preprocessing failed/skipped: {exc}")

        # Step 0.7 — Context Window Pruning (Phase 79)
        if config.context_pruning_enabled and context.get("conversation"):
            try:
                from ..services.context_pruner import context_pruner
                pruned = await context_pruner.prune(
                    context["conversation"],
                    model_router=self.model_router,
                    keep_recent=config.context_keep_recent,
                )
                context["conversation"] = pruned["context"]
                if pruned["pruned"]:
                    logger.debug(
                        f"Context pruned: {pruned['compressed_turns']} turns compressed, "
                        f"~{pruned['saved_tokens']} tokens saved"
                    )
            except Exception as exc:
                logger.warning(f"Context pruning failed (non-fatal): {exc}")

        # Step 1 — Check pgvector semantic cache first, fallback to in-process
        cached = await self._check_semantic_cache(workspace_id, query)
        if cached is None:
            cached = self._cache.get(workspace_id, query)
        if cached:
            logger.info(f"Cache HIT for workspace={workspace_id}")
            return CouncilResult(
                council_type=council_type,
                profile=CouncilProfile.TRIVIAL,
                query=query,
                synthesis=cached["response_text"],
                individual_responses=[],
                consensus_score=1.0,
                dissenting_views=[],
                total_cost_usd=0.0,
                total_tokens=0,
                total_latency_ms=0,
                cache_hit=True,
                models_used=[cached["response_model"]],
                providers_used=[],
                rounds_completed=0,
            )

        # Step 1.9 — RAG Enrichment (Phase 83): inject workspace knowledge into query
        if config.rag_enabled:
            try:
                from .rag_enricher import rag_enricher
                enriched = await rag_enricher.enrich(
                    workspace_id, query,
                    max_context_tokens=config.rag_max_context_tokens,
                )
                if enriched != query:
                    logger.debug("RAG: query enriched with workspace knowledge")
                    query = enriched
            except Exception as exc:
                logger.warning(f"RAG enrichment failed (non-fatal): {exc}")

        # Step 2 — Classify complexity (Phase 77: Gateway-aware)
        profile = self._classify(query, council_type, context)

        # Step 2.5 — Token budget (Phase 78)
        if config.token_budget_enabled:
            from .token_budget import token_budget
            budget = token_budget.get_budget(
                intent=context.get("_gateway_intent", "general"),
                complexity=context.get("_gateway_complexity", "medium"),
                user_override=getattr(config, "token_budget_override", None),
            )
            context["_token_budget"] = budget
            logger.debug(
                f"Token budget: max_tokens={budget['max_tokens']}, "
                f"temperature={budget['temperature']} "
                f"(intent={context.get('_gateway_intent')}, "
                f"complexity={context.get('_gateway_complexity')})"
            )

        # Step 3 — Route to the appropriate engine based on council_type
        if council_type == CouncilType.CHILD:
            result = await self._child_council(workspace_id, query, profile, context, start_ms)
        elif council_type == CouncilType.DISTILLATION:
            result = await self._distillation_council(workspace_id, query, profile, context, start_ms, config)
        elif council_type == CouncilType.PARENT:
            # E5: Route to DAG pipeline if enabled, else sequential
            if config.dag_pipeline_enabled:
                result = await self._dag_parent_council(workspace_id, query, profile, context, start_ms, config)
            else:
                result = await self._parent_council(workspace_id, query, profile, context, start_ms, config)
        elif council_type == CouncilType.SENTINEL:
            result = await self._sentinel_council(workspace_id, query, profile, context, start_ms, config)
        else:
            result = await self._child_council(workspace_id, query, profile, context, start_ms)

        # Step 4 — Cache the result
        if result.synthesis and not result.synthesis.startswith("⛔"):
            # pgvector cache
            await self._store_semantic_cache(
                workspace_id, query, result.synthesis,
                result.models_used[0] if result.models_used else "unknown",
            )
            # In-process fallback
            self._cache.put(
                workspace_id, query, result.synthesis,
                result.models_used[0] if result.models_used else "unknown",
            )

        # Step 5 — Cost tracking (best-effort, non-blocking)
        asyncio.create_task(self._track_cost(workspace_id, result, council_type))

        return result

    # ──────────────────────────────────────────────
    # Council-type specific pipelines
    # ──────────────────────────────────────────────

    async def _child_council(
        self, workspace_id: str, query: str, profile: CouncilProfile,
        context: Dict, start_ms: int,
    ) -> CouncilResult:
        """CHILD: Cost-optimized response — model count determined by AdaptiveCouncil (Phase 77)."""
        from .adaptive_council import adaptive_council

        config = self._get_config(workspace_id)

        # Phase 81: Speculative decoding for code-heavy intents (opt-in)
        if config.speculative_enabled:
            intent = context.get("_gateway_intent", "general")
            from .speculative import speculative_decoder, SPECULATIVE_INTENTS
            if intent in SPECULATIVE_INTENTS:
                try:
                    spec_result = await speculative_decoder.generate(
                        query, self.model_router, context
                    )
                    if not spec_result.get("error"):
                        latency = int(time.monotonic() * 1000) - start_ms
                        return CouncilResult(
                            council_type=CouncilType.CHILD, profile=profile, query=query,
                            synthesis=spec_result["response"], individual_responses=[],
                            consensus_score=1.0 if spec_result["draft_approved"] else 0.8,
                            dissenting_views=[],
                            total_cost_usd=spec_result["total_cost"],
                            total_tokens=0, total_latency_ms=latency, cache_hit=False,
                            models_used=[spec_result["draft_model"], spec_result.get("verify_model", "")],
                            providers_used=[spec_result.get("draft_provider", ""), spec_result.get("verify_provider", "")],
                            rounds_completed=2,
                        )
                except Exception as exc:
                    logger.warning(f"Speculative decoding failed, falling back: {exc}")

        if config.adaptive_council_enabled:
            complexity = context.get("_gateway_complexity", adaptive_council.profile_to_complexity(profile))
            policy = adaptive_council.get_council_config(complexity)
            model_count = policy["model_count"]
            prefer_cheap = policy["prefer_cheap"]
        else:
            # Legacy: single cascade model
            model_count = 1
            prefer_cheap = True

        if model_count == 1:
            # Fast path: cascade (cheapest single model, unchanged behaviour)
            response = await self.cascade.query(query, context)
            latency = int(time.monotonic() * 1000) - start_ms
            return CouncilResult(
                council_type=CouncilType.CHILD,
                profile=profile,
                query=query,
                synthesis=response.response,
                individual_responses=[response],
                consensus_score=response.confidence,
                dissenting_views=[],
                total_cost_usd=response.cost_usd,
                total_tokens=response.tokens_in + response.tokens_out,
                total_latency_ms=latency,
                cache_hit=False,
                models_used=[response.model],
                providers_used=[response.provider],
                rounds_completed=1,
            )

        # Multi-model path (medium/complex CHILD): select cheapest N models and run in parallel
        model_slots = adaptive_council.select_models(
            self.model_router, count=model_count, prefer_cheap=prefer_cheap,
        )
        if not model_slots:
            # Fallback to single cascade if no providers registered
            response = await self.cascade.query(query, context)
            latency = int(time.monotonic() * 1000) - start_ms
            return CouncilResult(
                council_type=CouncilType.CHILD, profile=profile, query=query,
                synthesis=response.response, individual_responses=[response],
                consensus_score=response.confidence, dissenting_views=[],
                total_cost_usd=response.cost_usd,
                total_tokens=response.tokens_in + response.tokens_out,
                total_latency_ms=latency, cache_hit=False,
                models_used=[response.model], providers_used=[response.provider],
                rounds_completed=1,
            )

        responses = await self._run_parallel(query, model_slots)
        if not responses:
            raise RuntimeError("All adaptive council models failed")

        return self._synthesize(query, CouncilType.CHILD, profile, responses, start_ms)


    async def _distillation_council(
        self, workspace_id: str, query: str, profile: CouncilProfile,
        context: Dict, start_ms: int, config=None,
    ) -> CouncilResult:
        """DISTILLATION: Use a single high-quality model with managed prompts."""
        # Pick the best available model
        model_slots = await self.model_router.select_models(
            workspace_id, CouncilType.DISTILLATION, CouncilProfile.SIMPLE,
        )
        if not model_slots:
            raise RuntimeError("No providers available for distillation")

        # Use PromptRegistry for system prompt (auto-optimizes over time)
        system_prompt = None
        try:
            from ..prompt_registry import get_prompt_registry
            registry = get_prompt_registry()
            compiled = await registry.compile(
                "distillation.summarize",
                variables={"query": query, "context": context.get("evidence", "")},
                workspace_id=workspace_id,
            )
            system_prompt = compiled.text
        except Exception:
            # Fallback to basic prompt if registry fails
            system_prompt = (
                "You are a technical summariser. Produce clear, concise summaries "
                "of development session artifacts. Preserve key decisions, code changes, "
                "and unresolved issues."
            )

        provider, model = model_slots[0]
        response = await self.model_router.call(
            provider, model, query, system_prompt=system_prompt,
        )
        latency = int(time.monotonic() * 1000) - start_ms

        return CouncilResult(
            council_type=CouncilType.DISTILLATION,
            profile=profile,
            query=query,
            synthesis=response.response,
            individual_responses=[response],
            consensus_score=response.confidence,
            total_cost_usd=response.cost_usd,
            total_tokens=response.tokens_in + response.tokens_out,
            total_latency_ms=latency,
            models_used=[response.model],
            providers_used=[response.provider],
            rounds_completed=1,
        )

    async def _parent_council(
        self, workspace_id: str, query: str, profile: CouncilProfile,
        context: Dict, start_ms: int, config=None,
    ) -> CouncilResult:
        """
        PARENT: Full multi-model council.

        Pipeline (all advanced stages gated by WorkspaceCouncilConfig):
          1. Constitution preamble injection
          2. Evidence gathering (GraphRAG + workspace context)
          3. Temporal memory recall (if enabled)
          4. Cross-council sub-spawning (if enabled)
          5. MCTS deep reasoning (if enabled + CRITICAL profile)
          6. Persona-driven debate (with reflector if enabled)
          7. Adversarial peer review
          8. Rubric scoring + prompt registry feedback
          9. Red team validation (if enabled)
         10. Constitutional response check
         11. Synthesis (weighted if enabled, else pick-best)
        """
        if config is None:
            config = self._get_config(workspace_id)

        model_slots = await self.model_router.select_models(
            workspace_id, CouncilType.PARENT, profile,
        )

        all_responses: List[ModelResponse] = []
        debate_history = None
        persona_perspectives = None
        rubric_scores = None
        evidence_used = False

        # ── 1. Constitution preamble ──
        constitution_preamble = ""
        if config.constitution_enforcement:
            try:
                from .constitution import get_constitution
                constitution_preamble = get_constitution().build_system_prompt_preamble()
            except Exception as exc:
                logger.debug(f"Constitution preamble skipped: {exc}")

        # ── 2. Evidence gathering (best-effort) ──
        evidence_prompt_block = ""
        if context.get("evidence"):
            evidence_prompt_block = f"\n\nWORKSPACE CONTEXT:\n{context['evidence']}"
            evidence_used = True
        else:
            try:
                from .evidence import get_evidence_manager
                ev = get_evidence_manager()
                evidence = await ev.gather_evidence(workspace_id, query)
                evidence_prompt_block = ev.format_for_prompt(evidence)
                if evidence_prompt_block:
                    evidence_prompt_block = f"\n\nWORKSPACE CONTEXT:\n{evidence_prompt_block}"
                    evidence_used = True
            except Exception as exc:
                logger.debug(f"Evidence gathering skipped: {exc}")

        # ── 3. Temporal memory recall (if enabled) ──
        temporal_block = ""
        if config.temporal_memory_enabled:
            try:
                from .temporal_memory import create_temporal_memory
                tm = create_temporal_memory(
                    top_k=config.temporal_recall_top_k,
                    outcome_window_days=config.temporal_outcome_window_days,
                )
                past_decisions = await tm.recall_similar_decisions(workspace_id, query)
                temporal_block = tm.format_for_prompt(past_decisions)
                if temporal_block:
                    temporal_block = f"\n\n{temporal_block}"
            except Exception as exc:
                logger.debug(f"Temporal memory skipped: {exc}")

        # ── 4. Cross-council sub-spawning (if enabled, not a sub-council) ──
        sub_council_block = ""
        if (
            config.cross_council_enabled
            and not context.get("_is_sub_council")
            and profile in (CouncilProfile.COMPLEX, CouncilProfile.CRITICAL)
        ):
            try:
                from .orchestrator import create_orchestrator
                orch = create_orchestrator(
                    max_sub_councils=config.cross_council_max_sub_councils,
                    sub_budget_usd=config.cross_council_sub_budget_usd,
                    total_budget_usd=config.cross_council_total_budget_usd,
                )
                specs = orch.analyze_spawn_needs(query)
                if specs:
                    sub_results = await orch.spawn_sub_councils(specs, workspace_id)
                    sub_council_block = orch.format_for_prompt(sub_results)
                    if sub_council_block:
                        sub_council_block = f"\n\n{sub_council_block}"
            except Exception as exc:
                logger.debug(f"Cross-council skipped: {exc}")

        # ── 5. MCTS deep reasoning (if enabled + CRITICAL) ──
        mcts_block = ""
        if config.mcts_enabled and profile == CouncilProfile.CRITICAL:
            try:
                from ..reasoning_chain import ReasoningChain
                mcts = ReasoningChain(model_router=self.model_router)
                mcts_result = await mcts.search(
                    query=query,
                    max_iterations=config.mcts_max_iterations,
                    branch_factor=config.mcts_branch_factor,
                    max_depth=config.mcts_max_depth,
                    exploration_c=config.mcts_exploration_c,
                    max_budget_usd=config.mcts_max_budget_usd,
                )
                best_chain = mcts_result.get("best_chain", [])
                if best_chain:
                    chain_text = "\n→ ".join(
                        step.get("thought", "")[:200] for step in best_chain
                    )
                    mcts_block = f"\n\nDEEP REASONING (MCTS):\n→ {chain_text}"
            except Exception as exc:
                logger.debug(f"MCTS reasoning skipped: {exc}")

        # Build the enriched query with all context blocks
        enriched_query = constitution_preamble + query + evidence_prompt_block + temporal_block + sub_council_block + mcts_block

        # ── 6. Persona debate (with reflector if enabled) ──
        if len(model_slots) >= 3:
            try:
                from .persona import get_persona_engine
                pe = get_persona_engine()
                persona_result = await pe.debate_with_personas(
                    enriched_query,
                    ["security_auditor", "cost_analyst", "governance_advisor", "devils_advocate"],
                    model_slots,
                    self.model_router,
                )
                persona_perspectives = persona_result.get("persona_responses", [])

                # E4: Cognitive reflector with full debate history
                if config.reflector_enabled and persona_perspectives:
                    try:
                        from .reflector import create_reflector
                        reflector = create_reflector(
                            groupthink_threshold=config.reflector_groupthink_threshold,
                            circular_window=config.reflector_circular_window,
                        )
                        # Extract debate rounds from persona result
                        debate_history = persona_result.get("debate_rounds", [])
                        pathologies = reflector.analyze_round(
                            persona_perspectives, debate_history, round_number=1,
                        )
                        if pathologies:
                            logger.info(
                                f"Reflector detected {len(pathologies)} pathologies: "
                                f"{[p.type.value for p in pathologies]}"
                            )
                            # Attach pathology warnings to context
                            context["_pathologies"] = [
                                {"type": p.type.value, "severity": p.severity,
                                 "description": p.description, "intervention": p.intervention}
                                for p in pathologies
                            ]
                    except Exception as exc:
                        logger.debug(f"Reflector skipped: {exc}")

            except Exception as exc:
                logger.warning(f"Persona debate failed (non-fatal): {exc}")

        # ── 7. Peer review (if >= 2 models) ──
        if len(model_slots) >= 2:
            try:
                from .peer_review import PeerReviewEngine
                pr = PeerReviewEngine(self.model_router)
                pr_result = await pr.run(enriched_query, model_slots)
                all_responses.extend(pr_result.individual_responses)
            except Exception as exc:
                logger.warning(f"Peer review failed, falling back to parallel: {exc}")
                all_responses = await self._run_parallel(enriched_query, model_slots)
        else:
            all_responses = await self._run_parallel(enriched_query, model_slots)

        # ── 8. Rubric scoring + prompt registry feedback ──
        if all_responses:
            try:
                from .rubric import get_rubric_engine
                re_engine = get_rubric_engine()
                best = max(all_responses, key=lambda r: r.confidence)
                rubric_scores = await re_engine.score(best.response, rubric_name="architecture")

                # Close the prompt auto-mutation feedback loop
                rubric_overall = rubric_scores.get("overall", 0.0) if isinstance(rubric_scores, dict) else 0.0
                if rubric_overall > 0:
                    try:
                        from ..prompt_registry import get_prompt_registry
                        registry = get_prompt_registry()
                        # Record outcome for both debate and peer review prompts
                        for template_name in ("debate.opening", "peer_review.synthesis"):
                            await registry.record_outcome(
                                template_name,
                                variant_id="",  # Active variant
                                rubric_score=rubric_overall,
                            )
                    except Exception as exc:
                        logger.debug(f"Prompt registry feedback loop failed (non-fatal): {exc}")
            except Exception as exc:
                logger.warning(f"Rubric scoring failed (non-fatal): {exc}")

        # ── 9. Synthesize ──
        if config.weighted_synthesis_enabled:
            result = await self._weighted_synthesize(
                query, CouncilType.PARENT, profile, all_responses, start_ms, config,
            )
        else:
            result = self._synthesize(
                query, CouncilType.PARENT, profile, all_responses, start_ms,
            )

        result.evidence_used = evidence_used
        result.rubric_scores = rubric_scores
        result.persona_perspectives = persona_perspectives

        # ── 10. Red team validation (if enabled) ──
        if config.red_team_enabled:
            try:
                from .red_team import create_red_team
                rt = create_red_team(
                    min_score=config.red_team_min_score,
                    max_budget_usd=config.red_team_max_budget_usd,
                )
                rt_report = await rt.validate(
                    result.synthesis, query, workspace_id,
                )
                if not rt_report.passed:
                    result.synthesis = (
                        f"⚠️ RED TEAM WARNING (score: {rt_report.score:.2f}): "
                        f"{'; '.join(f.description for f in rt_report.critical_findings[:3])}\n\n"
                        f"---\n\n{result.synthesis}"
                    )
            except Exception as exc:
                logger.debug(f"Red team skipped: {exc}")

        # ── 11. Constitutional response check ──
        if config.constitution_enforcement:
            try:
                from .constitution import get_constitution
                violations = get_constitution().check_response(result.synthesis)
                if violations:
                    result.synthesis = (
                        "[CONSTITUTIONAL REDACTION] Output contained governance violations: "
                        f"{'; '.join(violations)}\n\n{result.synthesis}"
                    )
            except Exception as exc:
                logger.debug(f"Parent constitutional response check skipped: {exc}")

        return result

    async def _dag_parent_council(
        self, workspace_id: str, query: str, profile: CouncilProfile,
        context: Dict, start_ms: int, config=None,
    ) -> CouncilResult:
        """
        E5: DAG-based parent council pipeline.

        Organizes the parent council stages into a directed acyclic graph
        where independent stages run in parallel. Stages:
          Layer 0 (parallel): constitution_preamble, evidence, temporal_memory
          Layer 1 (parallel): cross_council, mcts (depends on layer 0)
          Layer 2 (sequential): persona + reflector (depends on layer 1)
          Layer 3 (parallel): peer_review, parallel_models
          Layer 4 (sequential): rubric + feedback + synthesis
          Layer 5 (sequential): red_team + constitutional_check

        Falls back to sequential _parent_council on any DAG error.
        """
        if config is None:
            config = self._get_config(workspace_id)

        try:
            model_slots = await self.model_router.select_models(
                workspace_id, CouncilType.PARENT, profile,
            )
            enriched_blocks = {}
            all_responses = []

            # ── Layer 0: Parallel context gathering ──
            async def gather_constitution():
                if config.constitution_enforcement:
                    try:
                        from .constitution import get_constitution
                        return get_constitution().build_system_prompt_preamble()
                    except Exception as exc:
                        logger.debug(f"DAG constitution preamble skipped: {exc}")
                return ""

            async def gather_evidence():
                try:
                    from .evidence import get_evidence_manager
                    em = get_evidence_manager()
                    evidence = await em.gather(workspace_id, query)
                    if evidence:
                        return "\n\n[EVIDENCE CONTEXT]\n" + evidence[:3000]
                except Exception as exc:
                    logger.debug(f"DAG evidence gathering skipped: {exc}")
                return ""

            async def gather_temporal():
                if not config.temporal_memory_enabled:
                    return ""
                try:
                    from .temporal_memory import create_temporal_memory
                    tm = create_temporal_memory(top_k=config.temporal_recall_top_k)
                    recall = await tm.recall(workspace_id, query)
                    if recall.relevant_decisions:
                        lines = [f"  - {d['summary']} (outcome: {d.get('outcome', 'pending')})"
                                 for d in recall.relevant_decisions[:3]]
                        return "\n\n[HISTORICAL CONTEXT]\n" + "\n".join(lines)
                except Exception as exc:
                    logger.debug(f"DAG temporal memory skipped: {exc}")
                return ""

            preamble, evidence_block, temporal_block = await asyncio.gather(
                gather_constitution(), gather_evidence(), gather_temporal(),
            )
            enriched_blocks["preamble"] = preamble
            enriched_blocks["evidence"] = evidence_block
            enriched_blocks["temporal"] = temporal_block

            # ── Layer 1: Parallel deep reasoning ──
            async def run_mcts():
                if not (config.mcts_enabled and profile == CouncilProfile.CRITICAL):
                    return ""
                try:
                    from .mcts import get_mcts_engine
                    mcts = get_mcts_engine()
                    result = await mcts.search(
                        query, max_iterations=config.mcts_max_iterations,
                        branch_factor=config.mcts_branch_factor,
                    )
                    chain = result.get("best_chain", [])
                    if chain:
                        text = "\n→ ".join(s.get("thought", "")[:200] for s in chain)
                        return f"\n\nDEEP REASONING (MCTS):\n→ {text}"
                except Exception as exc:
                    logger.debug(f"DAG MCTS reasoning skipped: {exc}")
                return ""

            async def run_cross_council():
                if not config.cross_council_enabled or context.get("_is_sub_council"):
                    return ""
                try:
                    from .orchestrator import create_orchestrator
                    orch = create_orchestrator(
                        max_sub_councils=config.cross_council_max_sub_councils,
                        sub_budget_usd=config.cross_council_sub_budget_usd,
                    )
                    result = await orch.orchestrate(
                        workspace_id, query, self,
                        total_budget_usd=config.cross_council_total_budget_usd,
                    )
                    if result.sub_results:
                        lines = [f"  [{r.domain}]: {r.summary[:200]}" for r in result.sub_results[:3]]
                        return "\n\n[SUB-COUNCIL INSIGHTS]\n" + "\n".join(lines)
                except Exception as exc:
                    logger.debug(f"DAG cross-council skipped: {exc}")
                return ""

            mcts_block, sub_council_block = await asyncio.gather(
                run_mcts(), run_cross_council(),
            )

            # ── Layer 2: Build enriched query ──
            enriched_query = (
                enriched_blocks["preamble"] + query
                + enriched_blocks["evidence"] + enriched_blocks["temporal"]
                + sub_council_block + mcts_block
            )

            # ── Layer 3: Parallel — persona debate + model calls ──
            persona_perspectives = None

            async def run_persona():
                nonlocal persona_perspectives
                if len(model_slots) >= 3:
                    try:
                        from .persona import get_persona_engine
                        pe = get_persona_engine()
                        result = await pe.debate_with_personas(
                            enriched_query,
                            ["security_auditor", "cost_analyst", "governance_advisor", "devils_advocate"],
                            model_slots, self.model_router,
                        )
                        persona_perspectives = result.get("persona_responses", [])
                    except Exception as exc:
                        logger.debug(f"DAG persona debate skipped: {exc}")

            async def run_parallel_models():
                nonlocal all_responses
                if len(model_slots) >= 2:
                    try:
                        from .peer_review import PeerReviewEngine
                        pr = PeerReviewEngine(self.model_router)
                        pr_result = await pr.run(enriched_query, model_slots)
                        all_responses.extend(pr_result.individual_responses)
                    except Exception:
                        all_responses = await self._run_parallel(enriched_query, model_slots)
                else:
                    all_responses = await self._run_parallel(enriched_query, model_slots)

            await asyncio.gather(run_persona(), run_parallel_models())

            # ── Layer 4: Synthesis ──
            if config.weighted_synthesis_enabled and len(all_responses) >= 2:
                result = await self._weighted_synthesize(
                    query, CouncilType.PARENT, profile, all_responses, start_ms, config,
                )
            else:
                result = self._synthesize(
                    query, CouncilType.PARENT, profile, all_responses, start_ms,
                )
            result.persona_perspectives = persona_perspectives

            # ── Layer 5: Validation ──
            if config.red_team_enabled:
                try:
                    from .red_team import create_red_team
                    rt = create_red_team(
                        min_score=config.red_team_min_score,
                        max_budget_usd=config.red_team_max_budget_usd,
                    )
                    rt_report = await rt.validate(result.synthesis, query, workspace_id)
                    if not rt_report.passed:
                        result.synthesis = (
                            f"⚠️ RED TEAM WARNING (score: {rt_report.score:.2f}): "
                            f"{'; '.join(f.description for f in rt_report.critical_findings[:3])}\n\n"
                            f"---\n\n{result.synthesis}"
                        )
                except Exception as exc:
                    logger.debug(f"DAG red team validation skipped: {exc}")

            if config.constitution_enforcement:
                try:
                    from .constitution import get_constitution
                    violations = get_constitution().check_response(result.synthesis)
                    if violations:
                        result.synthesis = (
                            "[CONSTITUTIONAL REDACTION] " + "; ".join(violations)
                            + "\n\n" + result.synthesis
                        )
                except Exception as exc:
                    logger.debug(f"DAG constitutional response check skipped: {exc}")

            return result

        except Exception as exc:
            logger.warning(f"DAG pipeline failed, falling back to sequential: {exc}")
            return await self._parent_council(
                workspace_id, query, profile, context, start_ms, config,
            )

    async def _sentinel_council(
        self, workspace_id: str, query: str, profile: CouncilProfile,
        context: Dict, start_ms: int, config=None,
    ) -> CouncilResult:
        """
        SENTINEL: Security-focused parallel models + persona + rubric + red team.

        Pipeline:
          1. Managed security system prompt from PromptRegistry
          2. Persona debate (security_auditor + governance_advisor) if enough models
          3. Parallel model calls with security system prompt
          4. Rubric scoring (code_review rubric)
          5. Red team validation (if enabled)
          6. Constitutional response check
        """
        if config is None:
            config = self._get_config(workspace_id)

        model_slots = await self.model_router.select_models(
            workspace_id, CouncilType.SENTINEL, CouncilProfile.MODERATE,
        )

        # ── 1. Managed system prompt from PromptRegistry ──
        security_system_prompt = None
        try:
            from ..prompt_registry import get_prompt_registry
            registry = get_prompt_registry()
            compiled = await registry.compile(
                "sentinel.threat_assessment",
                variables={"query": query, "context": context.get("evidence", "")},
                workspace_id=workspace_id,
            )
            security_system_prompt = compiled.text
        except Exception:
            security_system_prompt = (
                "You are a security analyst performing a threat assessment. "
                "Focus exclusively on: vulnerabilities, injection risks, authentication gaps, "
                "data exposure, privilege escalation, supply chain risks, and OWASP Top 10. "
                "Be paranoid. Assume attackers are actively probing."
            )

        # ── 2. Persona perspectives (if enough models) ──
        persona_perspectives = None
        if len(model_slots) >= 3:
            try:
                from .persona import get_persona_engine
                pe = get_persona_engine()
                persona_result = await pe.debate_with_personas(
                    query,
                    ["security_auditor", "governance_advisor"],
                    model_slots[:2],
                    self.model_router,
                )
                persona_perspectives = persona_result.get("persona_responses", [])
            except Exception as exc:
                logger.debug(f"Sentinel persona debate skipped: {exc}")

        # ── 3. Parallel model calls ──
        responses = await self._run_parallel(
            query, model_slots, system_prompt=security_system_prompt,
        )

        # ── 4. Rubric scoring ──
        rubric_scores = None
        try:
            from .rubric import get_rubric_engine
            re_engine = get_rubric_engine()
            if responses:
                best = max(responses, key=lambda r: r.confidence)
                rubric_scores = await re_engine.score(best.response, rubric_name="code_review")
        except Exception as exc:
            logger.debug(f"Sentinel rubric scoring skipped: {exc}")

        result = self._synthesize(
            query, CouncilType.SENTINEL, profile, responses, start_ms,
        )
        result.rubric_scores = rubric_scores
        result.persona_perspectives = persona_perspectives

        # ── 5. Red team validation (if enabled) ──
        if config.red_team_enabled:
            try:
                from .red_team import create_red_team
                rt = create_red_team(
                    min_score=config.red_team_min_score,
                    max_budget_usd=config.red_team_max_budget_usd,
                )
                rt_report = await rt.validate(result.synthesis, query, workspace_id)
                if not rt_report.passed:
                    result.synthesis = (
                        f"⚠️ RED TEAM WARNING (score: {rt_report.score:.2f}): "
                        f"{'; '.join(f.description for f in rt_report.critical_findings[:3])}\n\n"
                        f"---\n\n{result.synthesis}"
                    )
            except Exception as exc:
                logger.debug(f"Sentinel red team validation skipped: {exc}")

        # ── 6. Constitutional response check ──
        if config.constitution_enforcement:
            try:
                from .constitution import get_constitution
                violations = get_constitution().check_response(result.synthesis)
                if violations:
                    result.synthesis = (
                        "[CONSTITUTIONAL REDACTION] " + "; ".join(violations)
                        + "\n\n" + result.synthesis
                    )
            except Exception as exc:
                logger.debug(f"Sentinel constitutional check skipped: {exc}")

        return result

    # ──────────────────────────────────────────────
    # Cascade entry point (single-model path)
    # ──────────────────────────────────────────────

    async def cascade_query(
        self,
        workspace_id: str,
        prompt: str,
        max_budget_usd: Optional[float] = None,
    ) -> ModelResponse:
        """
        Single-model cost-optimised query via FrugalGPT cascade.

        Use this for simple one-off prompts that don't need a full council.
        """
        return await self.cascade.query(prompt, max_budget_usd=max_budget_usd)

    # ──────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────

    def _classify(self, query: str, council_type: CouncilType, context: Optional[Dict] = None) -> CouncilProfile:
        """
        Classify query complexity → CouncilProfile.

        Phase 77: Consumes Gateway `_gateway_complexity` when available.
        Falls back to word-count heuristic only if Gateway was skipped.
        """
        # Phase 77 — use Gateway's cheap LLM analysis first
        gateway_complexity = (context or {}).get("_gateway_complexity")
        if gateway_complexity:
            _mapping = {
                "simple":   CouncilProfile.SIMPLE,
                "medium":   CouncilProfile.MODERATE,
                "complex":  CouncilProfile.COMPLEX,
                "critical": CouncilProfile.CRITICAL,
            }
            if gateway_complexity in _mapping:
                return _mapping[gateway_complexity]

        # council_type overrides always win for PARENT/SENTINEL/DISTILLATION
        if council_type == CouncilType.PARENT:
            return CouncilProfile.CRITICAL
        if council_type == CouncilType.SENTINEL:
            return CouncilProfile.MODERATE
        if council_type == CouncilType.DISTILLATION:
            return CouncilProfile.SIMPLE

        # CHILD fallback — word-count heuristic (used only when Gateway is offline)
        word_count = len(query.split())
        has_code = "```" in query
        has_multi_question = query.count("?") > 1

        if word_count < 15 and not has_code:
            return CouncilProfile.TRIVIAL
        if word_count < 40 and not has_multi_question:
            return CouncilProfile.SIMPLE
        if word_count < 100:
            return CouncilProfile.MODERATE
        return CouncilProfile.COMPLEX

    async def _run_parallel(
        self,
        query: str,
        model_slots: List[tuple],
        system_prompt: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> List[ModelResponse]:
        """Call all selected models in parallel. Errors are caught per-model."""
        # Phase 78: pick up token budget from context if available
        budget_kwargs: Dict = {}
        if context:
            budget = context.get("_token_budget")
            if budget:
                budget_kwargs["max_tokens"] = budget.get("max_tokens")
                budget_kwargs["temperature"] = budget.get("temperature")
        # Strip None values so provider defaults are used when budget not set
        budget_kwargs = {k: v for k, v in budget_kwargs.items() if v is not None}

        async def _safe_call(provider_name: str, model: str) -> Optional[ModelResponse]:
            try:
                return await self.model_router.call(
                    provider_name, model, query,
                    system_prompt=system_prompt,
                    **budget_kwargs,
                )
            except Exception as exc:
                logger.warning(f"Provider '{provider_name}/{model}' failed: {exc}")
                return None

        results = await asyncio.gather(*[_safe_call(p, m) for p, m in model_slots])
        return [r for r in results if r is not None]

    def _synthesize(
        self,
        query: str,
        council_type: CouncilType,
        profile: CouncilProfile,
        responses: List[ModelResponse],
        start_ms: int,
    ) -> CouncilResult:
        """Aggregate individual model responses into a CouncilResult."""
        if not responses:
            raise RuntimeError("Council returned zero successful responses.")

        # Consensus: ratio of high-confidence responses
        high_conf = [r for r in responses if r.confidence >= 0.70]
        consensus_score = len(high_conf) / len(responses)

        # Dissenting views: responses below 0.50 confidence
        dissenting = [r.response[:500] for r in responses if r.confidence < 0.50]

        # Best synthesis: highest-confidence response
        best = max(responses, key=lambda r: r.confidence)

        total_latency = int(time.monotonic() * 1000) - start_ms
        total_cost = sum(r.cost_usd for r in responses)

        # Estimate savings vs always using frontier
        frontier_cost_estimate = sum(
            (r.tokens_in * 15.0 + r.tokens_out * 75.0) / 1_000_000
            for r in responses
        )

        return CouncilResult(
            council_type=council_type,
            profile=profile,
            query=query,
            synthesis=best.response,
            individual_responses=responses,
            consensus_score=round(consensus_score, 3),
            dissenting_views=dissenting,
            total_cost_usd=round(total_cost, 6),
            total_tokens=sum(r.tokens_in + r.tokens_out for r in responses),
            total_latency_ms=total_latency,
            cache_hit=False,
            models_used=[r.model for r in responses],
            providers_used=list(set(r.provider for r in responses)),
            rounds_completed=1,
            estimated_savings_vs_frontier=round(max(0, frontier_cost_estimate - total_cost), 6),
        )

    async def _weighted_synthesize(
        self,
        query: str,
        council_type: CouncilType,
        profile: CouncilProfile,
        responses: List[ModelResponse],
        start_ms: int,
        config=None,
    ) -> CouncilResult:
        """
        LLM-backed weighted multi-model response aggregation.

        Instead of just picking the highest-confidence response, uses the cheapest
        cascade tier to merge multiple responses into a single synthesis that:
          - Merges common claims from high-agreement responses
          - Preserves dissenting views with evidence
          - Weights by model tier × confidence

        Falls back to pick-best (_synthesize) on failure.
        """
        if not responses:
            raise RuntimeError("Council returned zero successful responses.")

        # If only one response, no merging needed
        if len(responses) == 1:
            return self._synthesize(query, council_type, profile, responses, start_ms)

        # Sort by confidence
        sorted_responses = sorted(responses, key=lambda r: r.confidence, reverse=True)

        # Build merge prompt
        response_block = "\n\n".join(
            f"--- MODEL {i+1} ({r.model}, confidence: {r.confidence:.2f}) ---\n{r.response[:1500]}"
            for i, r in enumerate(sorted_responses[:4])  # Limit to 4 best
        )

        merge_prompt = (
            f"SYNTHESIS TASK: Merge these {len(sorted_responses[:4])} expert responses into "
            f"a single definitive answer.\n\n"
            f"Original question: {query[:300]}\n\n"
            f"Expert responses:\n{response_block}\n\n"
            f"MERGE RULES:\n"
            f"1. KEEP claims that appear in 2+ responses.\n"
            f"2. PREFER higher-confidence responses for disputed claims.\n"
            f"3. PRESERVE dissenting views in a separate section if well-evidenced.\n"
            f"4. REMOVE contradictions — pick the better-supported position.\n"
            f"5. Produce a SINGLE coherent answer, not a list of opinions."
        )

        try:
            budget = config.synthesis_merge_budget_usd if config else 0.03
            merge_response = await self.cascade.query(
                merge_prompt, max_budget_usd=budget,
            )

            # Build result with merged synthesis
            total_latency = int(time.monotonic() * 1000) - start_ms
            total_cost = sum(r.cost_usd for r in responses) + merge_response.cost_usd
            high_conf = [r for r in responses if r.confidence >= 0.70]
            consensus_score = len(high_conf) / len(responses)
            dissenting = [r.response[:500] for r in responses if r.confidence < 0.50]

            frontier_cost_estimate = sum(
                (r.tokens_in * 15.0 + r.tokens_out * 75.0) / 1_000_000
                for r in responses
            )

            return CouncilResult(
                council_type=council_type,
                profile=profile,
                query=query,
                synthesis=merge_response.response,
                individual_responses=responses,
                consensus_score=round(consensus_score, 3),
                dissenting_views=dissenting,
                total_cost_usd=round(total_cost, 6),
                total_tokens=sum(r.tokens_in + r.tokens_out for r in responses) + merge_response.tokens_in + merge_response.tokens_out,
                total_latency_ms=total_latency,
                cache_hit=False,
                models_used=[r.model for r in responses] + [merge_response.model],
                providers_used=list(set(r.provider for r in responses)),
                rounds_completed=1,
                estimated_savings_vs_frontier=round(max(0, frontier_cost_estimate - total_cost), 6),
            )
        except Exception as exc:
            logger.warning(f"Weighted synthesis failed, falling back to pick-best: {exc}")
            return self._synthesize(query, council_type, profile, responses, start_ms)

    # ──────────────────────────────────────────────
    # Semantic cache integration
    # ──────────────────────────────────────────────

    async def _check_semantic_cache(self, workspace_id: str, query: str) -> Optional[Dict]:
        """Try pgvector semantic cache. Returns None if unavailable."""
        try:
            from .cache import get_semantic_cache
            return await get_semantic_cache().check(workspace_id, query)
        except Exception:
            return None

    async def _store_semantic_cache(
        self, workspace_id: str, query: str, response: str, model: str,
    ) -> None:
        """Store in pgvector cache. Best-effort."""
        try:
            from .cache import get_semantic_cache
            await get_semantic_cache().store(workspace_id, query, response, model)
        except Exception as exc:
            logger.debug(f"Semantic cache store failed (non-fatal): {exc}")

    # ──────────────────────────────────────────────
    # Cost tracking
    # ──────────────────────────────────────────────

    async def _track_cost(
        self,
        workspace_id: str,
        result: CouncilResult,
        council_type: CouncilType,
    ) -> None:
        """Persist cost to Supabase cost_tracking table (best-effort)."""
        try:
            from ...db.supabase_client import get_supabase_client
            client = get_supabase_client()
            client.table("cost_tracking").insert({
                "workspace_id": workspace_id,
                "models": ",".join(result.models_used),
                "purpose": council_type.value,
                "tokens_in": sum(r.tokens_in for r in result.individual_responses),
                "tokens_out": sum(r.tokens_out for r in result.individual_responses),
                "cost_usd": result.total_cost_usd,
                "cache_hit": result.cache_hit,
            }).execute()
        except Exception as exc:
            logger.warning(f"Cost tracking failed (non-fatal): {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_council_engine: Optional[CouncilEngine] = None


def get_council_engine() -> CouncilEngine:
    """Get the application-wide CouncilEngine singleton."""
    global _council_engine
    if _council_engine is None:
        _council_engine = CouncilEngine()
    return _council_engine
