"""
Aegion Adapters - Firestore Draft Repository.

Handles storage of mutable session drafts.
"""

from typing import Optional, List
from datetime import datetime, timezone
from google.cloud import firestore
from ...models.draft import SessionDraft

class FirestoreDraftRepository:
    """
    Firestore implementation of draft storage.
    Collection: `session_drafts`
    """
    COLLECTION = "session_drafts"

    def __init__(self, db: firestore.AsyncClient = None):
        self._db = db

    @property
    def db(self) -> firestore.AsyncClient:
        if self._db is None:
            self._db = firestore.AsyncClient()
        return self._db

    async def save(self, draft: SessionDraft) -> SessionDraft:
        """Save or update a draft."""
        draft.updated_at = datetime.now(timezone.utc)
        data = draft.model_dump()
        # Convert datetime objects to string/timestamp if needed, 
        # but Firestore client handles datetime usually.
        # Pydantic model_dump might produce datetimes.
        
        doc_ref = self.db.collection(self.COLLECTION).document(draft.draft_id)
        await doc_ref.set(data)
        return draft

    async def get(self, draft_id: str) -> Optional[SessionDraft]:
        """Retrieve a draft by ID."""
        doc_ref = self.db.collection(self.COLLECTION).document(draft_id)
        doc = await doc_ref.get()
        
        if doc.exists:
            return SessionDraft(**doc.to_dict())
        return None

    async def list_for_user(self, user_id: str) -> List[SessionDraft]:
        """List all drafts for a specific user."""
        query = (
            self.db.collection(self.COLLECTION)
            .where("user_id", "==", user_id)
            .order_by("updated_at", direction=firestore.Query.DESCENDING)
        )
        
        docs = await query.get()
        return [SessionDraft(**doc.to_dict()) for doc in docs]

    async def delete(self, draft_id: str) -> bool:
        """Permanently delete a draft."""
        doc_ref = self.db.collection(self.COLLECTION).document(draft_id)
        await doc_ref.delete()
        return True
