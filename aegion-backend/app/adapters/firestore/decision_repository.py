"""
Aegion Adapters - Firestore Decision Repository.

Handles storage of Decision objects.
Decisions are immutable once approved.
"""

from typing import Optional, List, Any
from datetime import datetime
from google.cloud import firestore
from ...models.decision import Decision, DecisionStatus
from ...ports.database import DecisionRepositoryPort

class FirestoreDecisionRepository(DecisionRepositoryPort):
    """
    Firestore implementation for Decision storage.
    Collection: `decisions`
    """
    COLLECTION = "decisions"

    def __init__(self, db: firestore.AsyncClient = None):
        self._db = db

    @property
    def db(self) -> firestore.AsyncClient:
        if self._db is None:
            self._db = firestore.AsyncClient()
        return self._db

    async def create(self, entity: Decision) -> Decision:
        """Create a new decision."""
        # Use mode='json' to ensure compatibility
        data = entity.model_dump(mode='json')
        doc_ref = self.db.collection(self.COLLECTION).document(entity.decision_id)
        await doc_ref.set(data)
        return entity

    async def get_by_id(self, entity_id: str) -> Optional[Decision]:
        """Get decision by ID."""
        doc_ref = self.db.collection(self.COLLECTION).document(entity_id)
        doc = await doc_ref.get()
        if doc.exists:
            return Decision(**doc.to_dict())
        return None
    
    # Generic update method required by RepositoryPort
    async def update(self, entity_id: str, data: dict[str, Any]) -> Decision:
        """Update decision."""
        doc_ref = self.db.collection(self.COLLECTION).document(entity_id)
        # We need to fetch, update, and return
        # But for Firestore we can just update
        await doc_ref.update(data)
        # Return updated
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: str) -> bool:
        """Delete decision."""
        doc_ref = self.db.collection(self.COLLECTION).document(entity_id)
        await doc_ref.delete()
        return True

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Decision]:
        """List decisions."""
        query = (
            self.db.collection(self.COLLECTION)
            .order_by("proposed_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .offset(offset)
        )
        docs = await query.get()
        return [Decision(**doc.to_dict()) for doc in docs]

    async def get_by_proposal_id(self, proposal_id: str) -> Optional[Decision]:
        """Get decision linked to a proposal."""
        query = (
            self.db.collection(self.COLLECTION)
            .where("proposal_id", "==", proposal_id)
            .limit(1)
        )
        docs = await query.get()
        if docs:
            return Decision(**docs[0].to_dict())
        return None

    async def get_by_tier(self, tier: str, status: str = None) -> List[Decision]:
        """Get decisions by tier."""
        query = (
            self.db.collection(self.COLLECTION)
            .where("tier", "==", tier)
        )
        if status:
            query = query.where("status", "==", status)
            
        docs = await query.get()
        return [Decision(**doc.to_dict()) for doc in docs]

    async def get_superseded_chain(self, decision_id: str) -> List[Decision]:
        """Get the full supersession chain for a decision."""
        # This requires traversing up and down.
        # For MVP, let's just find the decision and traverse up (ancestors)
        # TODO: Implement full traversal efficiently.
        # Here we do naive recursive or iterative fetching.
        
        chain = []
        current = await self.get_by_id(decision_id)
        if not current:
            return []
            
        # Find root (traverse supersedes_id)
        # Actually standard usage: A supersedes B. B supersedes C.
        # Query: supersedes_id == current.decision_id -> finds what supersedes THIS
        # Query: current.supersedes_id -> find what THIS supersedes
        
        # We want the full chain.
        # 1. Traverse "superseded_by_id" (forward) to find newest
        # 2. Traverse "supersedes_id" (backward) to find oldest
        
        # Assuming simple linear chain for now.
        
        # Go backwards to start
        start = current
        while start.supersedes_id:
            super_id = start.supersedes_id
            prev = await self.get_by_id(super_id)
            if not prev:
                break
            start = prev
        
        # Now start is the root (oldest). Traverse forward using superseded_by_id
        current_node = start
        while current_node:
            chain.append(current_node)
            if not current_node.superseded_by_id:
                break
            next_node = await self.get_by_id(current_node.superseded_by_id)
            if not next_node:
                break
            current_node = next_node
            
        return chain

    async def get_state_at_time(self, timestamp: datetime) -> List[Decision]:
        """
        Get decisions active at a point in time.
        Active = approved_at <= T AND (superseded_by_id is None OR next_decision.approved_at > T)
        """
        # This is expensive in NoSQL without specific indexing/schema.
        # We fetch all approved decisions up to T.
        # Then filter out those superseded before T.
        
        # 1. Fetch all approved decisions created before T
        # (Using proposed_at as proxy for query optimization, filter by approved_at)
        
        # Actually, "decision_date" ie approved_at is what matters.
        # Let's assume we fetch all established decisions.
        # For MVP: fetch all, filter. Be careful with scale.
        
        query = (
            self.db.collection(self.COLLECTION)
            .where("status", "in", [DecisionStatus.APPROVED, DecisionStatus.SUPERSEDED])
            # .where("approved_at", "<=", timestamp.isoformat()) # Firestore needs datetime or string match
        )
        docs = await query.get()
        candidates = [Decision(**doc.to_dict()) for doc in docs]
        
        active = []
        for d in candidates:
            # Check if existed at T
            if not d.approved_at or d.approved_at > timestamp:
                continue
            
            # Check if superseded before T
            is_active = True
            if d.superseded_by_id:
                # Need to check when it was superseded.
                # Simplest: The superseding decision's approved_at
                superseder = await self.get_by_id(d.superseded_by_id)
                if superseder and superseder.approved_at and superseder.approved_at <= timestamp:
                    is_active = False
            
            if is_active:
                active.append(d)
                
        return active
