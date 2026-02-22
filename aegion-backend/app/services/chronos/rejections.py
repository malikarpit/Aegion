"""
Aegion Chronos - Rejection Service.

Phase 3: The Cognitive Plane
Manages rejection artifacts and learning extraction.
"""

from typing import List, Optional
from datetime import datetime

from ...contracts.rejection import (
    RejectionArtifact, 
    RejectionReason, 
    RejectionQuery,
    RejectionStats,
    LessonLearned
)
from ...core.logging import logger
from ...core.time import TimeAuthority


class RejectionService:
    """
    Service for managing rejection artifacts.
    
    Responsibilities:
    - Store rejected proposals with structured metadata
    - Extract lessons learned from rejection patterns
    - Find similar past rejections
    - Generate rejection statistics
    """
    
    def __init__(self):
        # In-memory store for Phase 3 (migrate to Firestore/Postgres later)
        self._rejections: dict[str, RejectionArtifact] = {}
    
    async def record_rejection(
        self,
        proposal_id: str,
        proposal_title: str,
        proposal_tier: str,
        rejected_by: str,
        reason_category: RejectionReason,
        reason_detail: str,
        workspace_id: str,
        session_id: Optional[str] = None
    ) -> RejectionArtifact:
        """
        Record a new rejection artifact.
        """
        import uuid
        
        rejection_id = f"rej-{uuid.uuid4().hex[:12]}"
        
        artifact = RejectionArtifact(
            rejection_id=rejection_id,
            proposal_id=proposal_id,
            proposal_title=proposal_title,
            rejected_by=rejected_by,
            rejected_at=TimeAuthority.now(),
            reason_category=reason_category,
            reason_detail=reason_detail,
            proposal_tier=proposal_tier,
            workspace_id=workspace_id,
            session_id=session_id
        )
        
        # Store
        self._rejections[rejection_id] = artifact
        
        # Extract lessons (async pattern detection)
        await self._extract_lessons(artifact)
        
        # Find similar rejections
        await self._find_similar(artifact)
        
        logger.audit(
            action="REJECTION_RECORDED",
            actor=rejected_by,
            target=proposal_id,
            justification=reason_detail,
            metadata={
                "rejection_id": rejection_id,
                "reason_category": reason_category.value,
                "tier": proposal_tier
            }
        )
        
        return artifact
    
    async def _extract_lessons(self, artifact: RejectionArtifact) -> None:
        """
        Extract lessons learned from rejection.
        Uses pattern matching and AI (future: LangGraph).
        """
        # Simple rule-based extraction for Phase 3
        lessons = []
        
        if artifact.reason_category == RejectionReason.INSUFFICIENT_EVIDENCE:
            lessons.append(LessonLearned(
                category="evidence",
                insight=f"Proposals for {artifact.proposal_tier} require stronger evidence base",
                applies_to=[artifact.workspace_id],
                confidence=0.7
            ))
        
        elif artifact.reason_category == RejectionReason.VIOLATES_INVARIANT:
            lessons.append(LessonLearned(
                category="invariants",
                insight="Review invariant documentation before proposing changes",
                applies_to=["all"],
                confidence=0.9
            ))
        
        elif artifact.reason_category == RejectionReason.SCOPE_CREEP:
            lessons.append(LessonLearned(
                category="scope",
                insight="Break large proposals into smaller, focused changes",
                applies_to=[artifact.workspace_id],
                confidence=0.8
            ))
        
        artifact.lessons_learned = lessons
    
    async def _find_similar(self, artifact: RejectionArtifact) -> None:
        """
        Find similar past rejections for pattern detection.
        """
        similar = []
        
        for existing in self._rejections.values():
            if existing.rejection_id == artifact.rejection_id:
                continue
            
            # Simple similarity: same reason category + same tier
            if (existing.reason_category == artifact.reason_category and
                existing.proposal_tier == artifact.proposal_tier):
                similar.append(existing.rejection_id)
        
        artifact.similar_proposals = similar[:5]  # Top 5
    
    async def get_rejection(self, rejection_id: str) -> Optional[RejectionArtifact]:
        """Get a specific rejection by ID."""
        return self._rejections.get(rejection_id)
    
    async def query_rejections(self, query: RejectionQuery) -> List[RejectionArtifact]:
        """Query rejections with filters."""
        results = list(self._rejections.values())
        
        if query.reason_category:
            results = [r for r in results if r.reason_category == query.reason_category]
        
        if query.workspace_id:
            results = [r for r in results if r.workspace_id == query.workspace_id]
        
        if query.rejected_by:
            results = [r for r in results if r.rejected_by == query.rejected_by]
        
        # Sort by date (newest first) and limit
        results.sort(key=lambda r: r.rejected_at, reverse=True)
        return results[:query.limit]
    
    async def get_stats(self, workspace_id: Optional[str] = None) -> RejectionStats:
        """Get rejection statistics."""
        rejections = list(self._rejections.values())
        
        if workspace_id:
            rejections = [r for r in rejections if r.workspace_id == workspace_id]
        
        # Count by reason
        by_reason = {}
        for r in rejections:
            key = r.reason_category.value
            by_reason[key] = by_reason.get(key, 0) + 1
        
        # Count by tier
        by_tier = {}
        for r in rejections:
            by_tier[r.proposal_tier] = by_tier.get(r.proposal_tier, 0) + 1
        
        # Aggregate lessons
        all_lessons = []
        for r in rejections:
            all_lessons.extend(r.lessons_learned)
        
        # Top lessons by confidence
        all_lessons.sort(key=lambda l: l.confidence, reverse=True)
        
        return RejectionStats(
            total_rejections=len(rejections),
            by_reason=by_reason,
            by_tier=by_tier,
            top_lessons=all_lessons[:10],
            rejection_rate=0.0  # Calculate when we have proposal counts
        )


# Singleton instance
_rejection_service: Optional[RejectionService] = None


def get_rejection_service() -> RejectionService:
    """Get the singleton rejection service instance."""
    global _rejection_service
    if _rejection_service is None:
        _rejection_service = RejectionService()
    return _rejection_service
