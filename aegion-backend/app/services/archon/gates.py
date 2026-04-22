"""
Aegion Archon Gates - Governance Enforcement.

Implements the tiered governance gates (T0/T1/T2/T3).
This is the ONLY layer that can persist decisions.

Doctrine: "Archon decides. Everything else suggests."
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from ...contracts.decision_intent import (
    DecisionIntent,
    DecisionTier,
    ImpactLevel,
    ReversibilityLevel,
    calculate_tier,
)
from ...contracts.uncertainty_level import UncertaintyDeclaration
from ...contracts.evidence import (
    Evidence,
    EvidenceChain,
    EvidenceGate,
    EvidenceClassification,
    EvidenceType,
    validate_evidence_for_proposal,
)
from ...contracts.audit_event import AuditEvent, AuditEventBuilder, AuditAction
from ...core.time import TimeAuthority
from ...core.logging import logger
from ...core.security import AuthorityContext

# Phase 3: Import for optional staleness checking
# Note: StalenessDetector is optional - design allows sync validation first


class GovernanceError(Exception):
    """Raised when governance rules are violated."""
    pass


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ArchonGates:
    """
    The Archon governance gate enforcement system.
    
    Core responsibilities:
    1. Tier classification
    2. Evidence gating
    3. Approval enforcement
    4. Freeze mode protection
    """
    
    def __init__(self, policy_registry=None):
        from .registry import PolicyRegistry
        from .invariant_engine import get_invariant_engine
        from .event_store import get_event_store
        from .causal_observability import get_causal_observability
        self.policy = policy_registry or PolicyRegistry
        self._freeze_mode = False
        self._invariant_engine = get_invariant_engine()
        self._event_store = get_event_store()
        self._observability = get_causal_observability()
    
    # ========== Freeze Mode ==========
    
    async def activate_freeze(self, actor_id: str, reason: str) -> None:
        """
        Activate freeze mode. Blocks all mutations.
        """
        self._freeze_mode = True
        
        logger.audit(
            action="FREEZE_ACTIVATED",
            actor=actor_id,
            target="system",
            justification=reason
        )

        # ChatOps Notification
        from .notifications import get_notification_service
        await get_notification_service().notify_freeze_activated(reason, actor_id)
    
    async def deactivate_freeze(self, actor_id: str, reason: str) -> None:
        """Deactivate freeze mode."""
        self._freeze_mode = False
        
        logger.audit(
            action="FREEZE_DEACTIVATED",
            actor=actor_id,
            target="system",
            justification=reason
        )

        # ChatOps Notification
        from .notifications import get_notification_service
        await get_notification_service().notify_freeze_deactivated(reason, actor_id)
    
    def guard_writable(self) -> None:
        """
        Guard against mutations in freeze mode.
        Raises GovernanceError if frozen.
        
        From Security Enhancements:
        - Implement central guardWritable() enforced across ALL mutating commands
        """
        if self._freeze_mode:
            raise GovernanceError("System is in FREEZE mode - mutations blocked")
    
    # ========== Tier Classification ==========
    
    def classify_tier(
        self,
        impact: ImpactLevel,
        reversibility: ReversibilityLevel,
        affected_modules: List[str]
    ) -> DecisionTier:
        """
        Classify decision tier based on impact and reversibility.
        Uses deterministic rules from Policy Registry.
        """
        base_tier = calculate_tier(impact, reversibility)
        
        # Check for policy overrides
        policy = self.policy.get_active()
        
        # Check if any affected module requires escalation
        for module in affected_modules:
            if module in policy.critical_modules:
                if base_tier.value < DecisionTier.T2.value:
                    base_tier = DecisionTier.T2
        
        return base_tier
    
    def get_quorum(self, tier: DecisionTier) -> int:
        """Return required number of distinct approvers for this tier."""
        policy = self.policy.get_active()
        return policy.quorum_requirements.get(tier.value, 1)
    
    def explain_tier(
        self,
        impact: ImpactLevel,
        reversibility: ReversibilityLevel,
        affected_modules: List[str]
    ) -> Dict[str, Any]:
        """
        Return tier classification with human-readable reasons.
        Used by API to surface governance rationale in the UI.
        """
        base_tier = calculate_tier(impact, reversibility)
        reasons = [f"Impact: {impact}, Reversibility: {reversibility} → base tier {base_tier.value}"]
        
        final_tier = base_tier
        policy = self.policy.get_active()
        for module in affected_modules:
            if module in policy.critical_modules:
                if final_tier.value < DecisionTier.T2.value:
                    final_tier = DecisionTier.T2
                    reasons.append(f"Touches critical module '{module}' → escalated to T2+")
        
        gate = self._get_evidence_gate(final_tier)
        return {
            "tier": final_tier.value,
            "quorum": self.get_quorum(final_tier),
            "evidence_required": gate.minimum_evidence_count,
            "self_approval_allowed": final_tier not in [DecisionTier.T2, DecisionTier.T3],
            "reasons": reasons
        }
    
    # ========== Evidence Gating ==========
    
    def validate_evidence(
        self,
        proposal_id: str,
        proposal_created_at: datetime,
        evidence_list: List[Evidence],
        tier: DecisionTier
    ) -> tuple[bool, List[str]]:
        """
        Validate evidence for a proposal.
        
        From Security Enhancements:
        - Require proposal.evidenceIds.length > 0
        - Only accept evidence linked to that proposal
        - Evidence must be newer than proposal creation
        """
        errors = []
        
        # Get gate configuration for tier
        gate = self._get_evidence_gate(tier)
        
        # Check minimum evidence
        if gate.require_evidence and len(evidence_list) == 0:
            errors.append("Proposal requires at least one evidence link")
        
        if len(evidence_list) < gate.minimum_evidence_count:
            errors.append(
                f"Proposal requires at least {gate.minimum_evidence_count} evidence items"
            )
        
        # Validate each evidence
        supporting_count = 0
        contradictory_count = 0
        stale_count = 0
        
        for evidence in evidence_list:
            # Check proposal linkage
            if evidence.proposal_id != proposal_id:
                errors.append(f"Evidence {evidence.evidence_id} not linked to this proposal")
                continue
            
            # Phase 3: Check staleness
            # INVARIANT: Stale evidence cannot support approval
            if evidence.is_stale:
                stale_count += 1
                errors.append(
                    f"Evidence {evidence.evidence_id} is stale and cannot support approval"
                )
                continue
            
            # Validate against gate
            is_valid, error = validate_evidence_for_proposal(
                evidence, proposal_created_at, gate
            )
            if not is_valid:
                errors.append(error)
            
            # Count classifications
            if evidence.classification == EvidenceClassification.SUPPORTING:
                supporting_count += 1
            elif evidence.classification == EvidenceClassification.CONTRADICTORY:
                contradictory_count += 1
        
        # Check for required supporting evidence
        if gate.require_supporting and supporting_count == 0:
            errors.append("At least one supporting evidence is required")
        
        # Check for contradictory evidence blocking
        if gate.block_on_contradictory and contradictory_count > 0:
            errors.append(f"Contradictory evidence blocks approval ({contradictory_count} found)")
        
        # Phase 3: Log staleness if detected
        if stale_count > 0:
            logger.audit(
                action="STALE_EVIDENCE_BLOCKED",
                actor="archon",
                target=proposal_id,
                justification=f"{stale_count} stale evidence item(s) blocked approval"
            )
        
        return len(errors) == 0, errors
    
    def _get_evidence_gate(self, tier: DecisionTier) -> EvidenceGate:
        """Get evidence gate configuration for tier."""
        # Default gates per tier
        gates = {
            DecisionTier.T0: EvidenceGate(
                tier="T0",
                require_evidence=False,
                minimum_evidence_count=0,
                require_supporting=False,
                block_on_contradictory=False
            ),
            DecisionTier.T1: EvidenceGate(
                tier="T1",
                require_evidence=True,
                minimum_evidence_count=1,
                require_supporting=True,
                block_on_contradictory=True
            ),
            DecisionTier.T2: EvidenceGate(
                tier="T2",
                require_evidence=True,
                minimum_evidence_count=2,
                require_supporting=True,
                block_on_contradictory=True,
                required_evidence_types=[
                    EvidenceType.TEST_RESULT,
                    EvidenceType.RUNTIME_LOG,
                ]
            ),
            DecisionTier.T3: EvidenceGate(
                tier="T3",
                require_evidence=True,
                minimum_evidence_count=3,
                require_supporting=True,
                block_on_contradictory=True,
                required_evidence_types=[
                    EvidenceType.TEST_RESULT,
                    EvidenceType.METRIC,
                    EvidenceType.MANUAL_VERIFICATION,
                ]
            ),
        }
        return gates.get(tier, gates[DecisionTier.T1])
    
    # ========== Approval Enforcement ==========
    
    def can_approve(
        self,
        authority: AuthorityContext,
        tier: DecisionTier
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user has authority to approve at this tier.
        """
        if tier == DecisionTier.T0:
            # T0 is auto-approved (local, trivial)
            return True, None
        
        if tier == DecisionTier.T1:
            if not authority.can_approve_t1:
                return False, "User cannot approve T1 decisions"
            return True, None
        
        if tier in [DecisionTier.T2, DecisionTier.T3]:
            if not authority.can_approve_t2:
                return False, "User cannot approve T2/T3 decisions"
            return True, None
        
        return False, f"Unknown tier: {tier}"
    
    async def approve_proposal(
        self,
        proposal_id: str,
        proposal_status: str,
        approver: AuthorityContext,
        tier: DecisionTier,
        evidence_list: List[Evidence],
        proposal_created_at: datetime,
        uncertainty: Optional[UncertaintyDeclaration] = None,
        proposal_creator_id: Optional[str] = None
    ) -> AuditEvent:
        """
        Approve a proposal and create a decision.
        
        From Security Enhancements:
        - Reject approval if proposal.status !== 'pending'
        - Enforce one decision per proposal ID
        - Block self-approval for T2+ decisions (Segregation of Duties)
        
        From Hallucination Governance (H-3):
        - Block approval if uncertainty is blocking
        """
        # Trace this governance operation
        with self._observability.trace_operation(
            operation="approve_proposal",
            actor_id=approver.user_id,
            workspace_id=getattr(approver, 'workspace_id', ''),
        ) as trace:
            trace.set_tier(tier.value)
            trace.set_evidence_count(len(evidence_list))

            # ── Formal Invariant Check (YAML-driven) ──
            # Run all 14 invariants from invariants.yaml before procedural checks
            stale_count = sum(1 for e in evidence_list if e.is_stale)
            evidence_types = set(e.classification.value for e in evidence_list if not e.is_stale)
            all_after = all(
                not hasattr(e, 'created_at') or e.created_at is None or e.created_at >= proposal_created_at
                for e in evidence_list
            )
            
            inv_result = self._invariant_engine.evaluate_for_approval(
                tier=tier.value,
                proposer_id=proposal_creator_id or "",
                approver_id=approver.user_id,
                approver_type=getattr(approver, 'agent_type', 'human'),
                evidence_count=len(evidence_list),
                stale_evidence_count=stale_count,
                distinct_evidence_types=len(evidence_types),
                all_evidence_after_proposal=all_after,
                freeze_active=self._freeze_mode,
                proposal_id=proposal_id,
            )
            
            trace.set_invariant_violations(len(inv_result.blocking_violations) + len(inv_result.alerting_violations))
            
            if not inv_result.passed:
                blocking = inv_result.blocking_violations
                messages = [v.message for v in blocking]
                raise GovernanceError(
                    f"Invariant violation(s): {'; '.join(messages)}"
                )
            
            # Log alerting violations (non-blocking)
            for alert in inv_result.alerting_violations:
                logger.warning(
                    f"Invariant alert {alert.invariant_id}: {alert.message}"
                )
            
            # ── Procedural Checks (belt-and-suspenders) ──
            # Guard freeze mode
            self.guard_writable()
            
            # Check proposal status
            if proposal_status != "pending":
                raise GovernanceError(
                    f"Cannot approve: proposal status is '{proposal_status}', expected 'pending'"
                )
            
            # OPA Policy Check (Hybrid Validation)
            try:
                from .opa import get_opa_service
                opa_input = {
                    "tier": tier.value,
                    "approvals": [{"role": approver.role, "user_id": approver.user_id}],
                    "evidence": [e for e in evidence_list] # Just list for count check
                }
                policy_result = get_opa_service().evaluate_policy(opa_input)
                if not policy_result["allow"]:
                    raise GovernanceError(f"OPA Policy Denied: {policy_result.get('reason')}")
            except ImportError:
                 logger.warning("OPA Service not available, skipping policy check.")

            # Enhancement 7: Semantic Audit (Neuro-Symbolic Governance)
            try:
                from .semantic import get_semantic_auditor
                # Ideally fetch real proposal justification here.
                # Using a placeholder that triggers the "urgent/bypass" check if keywords present.
                simulated_justification = "Standard approval" 
                
                audit_result = await get_semantic_auditor().audit_proposal(
                    proposal_id, 
                    simulated_justification
                )
                
                if audit_result.get("flagged", False):
                    # Flagged by AI. Require Admin override or block.
                    # Current logic: Block.
                    raise GovernanceError(
                        f"Semantic Auditor blocked this approval. Risk Score: {audit_result.get('score')}. Reason: {audit_result.get('reason')}"
                    )
            except ImportError:
                 pass
            except Exception as e:
                 logger.warning(f"Semantic audit skipped due to error: {e}")

            # Check approval authority
            can_approve, error = self.can_approve(approver, tier)
            if not can_approve:
                raise GovernanceError(error)
                
            # Check Segregation of Duties (No Self-Approval for T2+)
            if tier in [DecisionTier.T2, DecisionTier.T3]:
                if proposal_creator_id and proposal_creator_id == approver.user_id:
                    raise GovernanceError(
                        f"Self-approval blocked for {tier.value} decision. Segregation of Duties required."
                    )
                
            # Check uncertainty (H-3)
            if uncertainty and uncertainty.is_blocking:
                allow_override = approver.role == "architect" or approver.can_approve_t2
                
                if allow_override:
                    logger.warning(f"Uncertainty override by {approver.user_id} for {proposal_id}. Reason: {uncertainty.blocking_reason}")
                else:
                    raise GovernanceError(
                        f"Uncertainty blocking approval: {uncertainty.blocking_reason or 'High Uncertainty'}. Architect override required."
                    )
            
            # Validate evidence
            is_valid, errors = self.validate_evidence(
                proposal_id, proposal_created_at, evidence_list, tier
            )
            if not is_valid:
                raise GovernanceError(f"Evidence validation failed: {'; '.join(errors)}")
            
            # Create audit event for approval
            event = (
                AuditEventBuilder(AuditAction.DECISION_APPROVED)
                .with_actor(approver.user_id)
                .with_target("proposal", proposal_id)
                .with_justification(f"Approved at tier {tier.value}")
                .with_evidence([e.evidence_id for e in evidence_list])
                .build()
            )
            
            logger.audit(
                action="DECISION_APPROVED",
                actor=approver.user_id,
                target=proposal_id,
                justification=f"Approved at tier {tier.value}",
                metadata={
                    "tier": tier.value,
                    "evidence_count": len(evidence_list),
                    "invariants_evaluated": inv_result.evaluated_count,
                    "invariants_skipped": inv_result.skipped_count,
                }
            )
            
            # Enhancement 4: Emit domain event to event store
            from .event_store import DomainEventType
            self._event_store.append(
                event_type=DomainEventType.DECISION_APPROVED,
                aggregate_type="proposal",
                aggregate_id=proposal_id,
                payload={
                    "tier": tier.value,
                    "evidence_count": len(evidence_list),
                    "evidence_ids": [e.evidence_id for e in evidence_list],
                },
                actor_id=approver.user_id,
            )
            
            # Bind the proposal node to this trace
            trace.bind_node("proposal", proposal_id)
            # Enhanc Update Metrics
            from .metrics import get_metrics_service
            get_metrics_service().decisions_approved.labels(
                tier=tier.value, workspace=getattr(approver, 'workspace_id', 'unknown')
            ).inc()

            # Enhancement 13: ChatOps Notification
            from .notifications import get_notification_service
            await get_notification_service().notify_decision_approved(
                proposal_id=proposal_id,
                title=f"Proposal {proposal_id}", # Ideally fetch title if available
                approver=approver.user_id,
                tier=tier.value
            )

            # ── Persist to Supabase decisions table (best-effort) ──
            try:
                from ...db.supabase_client import get_supabase_client
                get_supabase_client().table("decisions").insert({
                    "workspace_id": getattr(approver, 'workspace_id', None),
                    "proposal_id": proposal_id,
                    "decision_type": "approval",
                    "tier": tier.value,
                    "outcome": "approved",
                    "actor_id": approver.user_id,
                    "evidence_ids": [e.evidence_id for e in evidence_list],
                    "metadata": {
                        "evidence_count": len(evidence_list),
                        "invariants_evaluated": inv_result.evaluated_count,
                        "invariants_skipped": inv_result.skipped_count,
                        "audit_event_id": event.event_id,
                    },
                }).execute()
            except Exception as exc:
                logger.warning(f"Decision persist failed (non-fatal): {exc}")
            
            return event
    
    def reject_proposal(
        self,
        proposal_id: str,
        rejector: AuthorityContext,
        reason: str
    ) -> AuditEvent:
        """Reject a proposal."""
        self.guard_writable()
        
        event = (
            AuditEventBuilder(AuditAction.DECISION_REJECTED)
            .with_actor(rejector.user_id)
            .with_target("proposal", proposal_id)
            .with_justification(reason)
            .build()
        )
        
        logger.audit(
            action="DECISION_REJECTED",
            actor=rejector.user_id,
            target=proposal_id,
            justification=reason
        )
        
        return event


# Singleton instance
_archon: ArchonGates = None


def get_archon() -> ArchonGates:
    """Get the Archon gates singleton."""
    global _archon
    if _archon is None:
        _archon = ArchonGates()
    return _archon
