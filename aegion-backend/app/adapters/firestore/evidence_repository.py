"""
Aegion Adapters - Firestore Evidence Repository.

Handles storage of Evidence.
Evidence is immutable.
"""

from typing import Optional, List, Any
from google.cloud import firestore
from ...contracts.evidence import Evidence, EvidenceClassification
from ...ports.database import EvidenceRepositoryPort

class FirestoreEvidenceRepository(EvidenceRepositoryPort):
    """
    Firestore implementation for Evidence storage.
    Collection: `evidence`
    """
    COLLECTION = "evidence"

    def __init__(self, db: firestore.AsyncClient = None):
        self._db = db

    @property
    def db(self) -> firestore.AsyncClient:
        if self._db is None:
            self._db = firestore.AsyncClient()
        return self._db

    async def create(self, entity: Evidence) -> Evidence:
        """Create a new evidence."""
        # Use json mode for serialization safety
        data = entity.model_dump(mode='json')
        doc_ref = self.db.collection(self.COLLECTION).document(entity.evidence_id)
        await doc_ref.set(data)
        return entity

    async def get_by_id(self, entity_id: str) -> Optional[Evidence]:
        """Get evidence by ID."""
        doc_ref = self.db.collection(self.COLLECTION).document(entity_id)
        doc = await doc_ref.get()
        if doc.exists:
            return Evidence(**doc.to_dict())
        return None
        
    async def update(self, entity_id: str, data: dict[str, Any]) -> Evidence:
        """
        Update evidence. 
        Note: Evidence is doctrinally immutable, but tech layer supports it if needed (e.g. adding metadata).
        """
        doc_ref = self.db.collection(self.COLLECTION).document(entity_id)
        await doc_ref.update(data)
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: str) -> bool:
        """Delete evidence."""
        doc_ref = self.db.collection(self.COLLECTION).document(entity_id)
        await doc_ref.delete()
        return True

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Evidence]:
        """List evidence."""
        query = (
            self.db.collection(self.COLLECTION)
            .order_by("collected_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .offset(offset)
        )
        docs = await query.get()
        return [Evidence(**doc.to_dict()) for doc in docs]

    async def get_by_proposal(self, proposal_id: str) -> List[Evidence]:
        """List evidence linked to a proposal."""
        query = (
            self.db.collection(self.COLLECTION)
            .where("proposal_id", "==", proposal_id)
            .order_by("collected_at", direction=firestore.Query.DESCENDING)
        )
        docs = await query.get()
        return [Evidence(**doc.to_dict()) for doc in docs]

    async def get_supporting(self, proposal_id: str) -> List[Evidence]:
        """Get only supporting evidence for a proposal."""
        query = (
            self.db.collection(self.COLLECTION)
            .where("proposal_id", "==", proposal_id)
            .where("classification", "==", EvidenceClassification.SUPPORTING.value)
            # Firestore requires composite index for multiple fields + sort. 
            # If sort removed, easier.
        )
        docs = await query.get()
        return [Evidence(**doc.to_dict()) for doc in docs]
