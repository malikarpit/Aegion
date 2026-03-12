"""
Rejection Learning — Phase 43 (Elevated): Closed-Loop Self-Improvement.

When proposals are rejected, this system:
  1. Stores the rejection context (reason, proposal, council output)
  2. Identifies rejection patterns over time
  3. CLOSES THE FEEDBACK LOOP: injects rejection patterns as few-shot
     negative examples into the PromptRegistry, so debate and peer review
     prompts automatically learn to avoid past mistakes
  4. Builds avoidance prompts for direct injection into council context
  5. Tracks improvement metrics (rejection rate over time)

The critical upgrade from v1: `record_rejection()` now automatically calls
`_close_feedback_loop()` which feeds the rejection data into the DSPy-style
PromptRegistry as negative few-shot examples.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.logging import logger


class RejectionLearning:
    """
    Learns from rejected proposals to improve future council recommendations.
    """

    def _client(self):
        from ..db.supabase_client import get_supabase_client
        return get_supabase_client()

    async def record_rejection(
        self,
        workspace_id: str,
        proposal_id: str,
        rejection_reason: str,
        proposal_context: Dict[str, Any],
        council_output: Optional[Dict] = None,
    ) -> bool:
        """
        Record a rejection AND close the feedback loop.

        After storing the rejection, automatically injects the rejection
        pattern into the PromptRegistry as a negative few-shot example.
        """
        try:
            self._client().table("rejection_log").insert({
                "workspace_id": workspace_id,
                "proposal_id": proposal_id,
                "rejection_reason": rejection_reason,
                "proposal_context": proposal_context,
                "council_output": council_output,
            }).execute()

            # CLOSE THE FEEDBACK LOOP — the critical missing piece
            await self._close_feedback_loop(
                workspace_id, rejection_reason, proposal_context, council_output,
            )

            return True
        except Exception as exc:
            logger.warning(f"Rejection recording failed: {exc}")
            return False

    async def _close_feedback_loop(
        self,
        workspace_id: str,
        rejection_reason: str,
        proposal_context: Dict[str, Any],
        council_output: Optional[Dict],
    ) -> None:
        """
        Feed the rejection into the PromptRegistry as a negative few-shot example.

        This is the critical bridge between rejection data and prompt self-optimization.
        The PromptRegistry will prepend these examples to future debate/review prompts,
        teaching the council to avoid known rejection patterns.
        """
        try:
            from .prompt_registry import get_prompt_registry
            registry = get_prompt_registry()

            # Build the negative example
            proposal_summary = ""
            if isinstance(proposal_context, dict):
                proposal_summary = proposal_context.get("title", "")
                if proposal_context.get("description"):
                    proposal_summary += f": {str(proposal_context['description'])[:200]}"
            elif isinstance(proposal_context, str):
                proposal_summary = proposal_context[:300]

            council_response = ""
            if council_output:
                council_response = str(council_output.get("synthesis", council_output.get("response", "")))[:300]

            negative_example = {
                "input": f"Proposal: {proposal_summary}",
                "output": (
                    f"REJECTED — {rejection_reason}\n"
                    f"Council had recommended: {council_response}\n"
                    f"This recommendation was wrong. Avoid similar patterns."
                ),
            }

            # Inject into relevant prompt templates
            templates_to_update = [
                "debate.opening",
                "peer_review.independent",
                "peer_review.synthesis",
            ]
            for template_name in templates_to_update:
                try:
                    await registry.inject_few_shot(template_name, [negative_example])
                except KeyError:
                    pass  # Template may not exist yet

            logger.info(
                f"Rejection feedback loop closed: injected into {len(templates_to_update)} "
                f"prompt templates (workspace={workspace_id})"
            )
        except Exception as exc:
            # Non-fatal — don't break rejection recording if prompt injection fails
            logger.warning(f"Feedback loop injection failed (non-fatal): {exc}")

    async def get_rejection_patterns(
        self,
        workspace_id: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Analyze rejection patterns for a workspace."""
        try:
            result = (
                self._client()
                .table("rejection_log")
                .select("rejection_reason,proposal_context,council_output")
                .eq("workspace_id", workspace_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rejections = result.data or []

            # Count rejection reasons
            reason_counts: Dict[str, int] = {}
            for r in rejections:
                reason = r.get("rejection_reason", "unknown")
                # Bucket by first 50 chars for clustering
                key = reason[:50]
                reason_counts[key] = reason_counts.get(key, 0) + 1

            # Sort by frequency
            top_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:5]

            # Improvement metric: rejection rate trend
            total = len(rejections)
            recent_half = rejections[:total // 2] if total > 4 else rejections
            older_half = rejections[total // 2:] if total > 4 else []
            trend = "insufficient_data"
            if len(recent_half) > 2 and len(older_half) > 2:
                trend = "improving" if len(recent_half) < len(older_half) else "worsening"

            return {
                "total_rejections": total,
                "top_rejection_reasons": [
                    {"reason": r, "count": c} for r, c in top_reasons
                ],
                "recent_rejections": rejections[:5],
                "trend": trend,
            }
        except Exception as exc:
            logger.warning(f"Rejection pattern analysis failed: {exc}")
            return {"total_rejections": 0, "top_rejection_reasons": [], "recent_rejections": [], "trend": "unknown"}

    async def build_avoidance_prompt(
        self,
        workspace_id: str,
    ) -> str:
        """
        Build a prompt injection block that tells the council to avoid
        repeating past rejection patterns.
        """
        patterns = await self.get_rejection_patterns(workspace_id)
        if not patterns["top_rejection_reasons"]:
            return ""

        reasons_block = "\n".join(
            f"  - {r['reason']} (rejected {r['count']}x)"
            for r in patterns["top_rejection_reasons"]
        )

        return (
            "\n\n[LEARNING FROM PAST REJECTIONS]\n"
            "The following proposal patterns have been rejected previously. "
            "Avoid making similar recommendations:\n"
            f"{reasons_block}\n"
        )

    async def bulk_sync_to_prompts(self, workspace_id: str) -> int:
        """
        One-time sync: load all historical rejections and inject them
        as few-shot examples into the prompt registry.

        Call this on startup or migration to backfill.
        Returns count of examples injected.
        """
        try:
            from .prompt_registry import get_prompt_registry
            registry = get_prompt_registry()

            result = (
                self._client()
                .table("rejection_log")
                .select("rejection_reason,proposal_context,council_output")
                .eq("workspace_id", workspace_id)
                .order("created_at", desc=True)
                .limit(10)  # Only most recent 10 to avoid prompt bloat
                .execute()
            )
            rejections = result.data or []

            examples = []
            for r in rejections:
                context = r.get("proposal_context", {})
                summary = context.get("title", str(context)[:200]) if isinstance(context, dict) else str(context)[:200]
                examples.append({
                    "input": f"Proposal: {summary}",
                    "output": f"REJECTED — {r.get('rejection_reason', 'unknown')}",
                })

            for template in ["debate.opening", "peer_review.independent"]:
                try:
                    await registry.inject_few_shot(template, examples)
                except KeyError:
                    pass

            logger.info(f"Bulk synced {len(examples)} rejection examples to prompts")
            return len(examples)
        except Exception as exc:
            logger.warning(f"Bulk sync failed: {exc}")
            return 0


# Singleton
_rejection_learning: Optional[RejectionLearning] = None

def get_rejection_learning() -> RejectionLearning:
    global _rejection_learning
    if _rejection_learning is None:
        _rejection_learning = RejectionLearning()
    return _rejection_learning
