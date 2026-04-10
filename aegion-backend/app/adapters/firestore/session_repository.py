"""
Aegion Firestore Adapter - Session Repository.

Implements SessionRepositoryPort using Google Cloud Firestore.
Phase 1-2 implementation.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from google.cloud import firestore

from ...ports.database import SessionRepositoryPort
from ...domain.session import Session
from ...core.time import TimeAuthority
from ...core.logging import logger


class FirestoreSessionRepository(SessionRepositoryPort):
    """
    Firestore implementation of SessionRepositoryPort.
    """
    
    COLLECTION = "sessions"
    
    def __init__(self, db: firestore.AsyncClient = None):
        self._db = db
    
    @property
    def db(self) -> firestore.AsyncClient:
        if self._db is None:
            self._db = firestore.AsyncClient()
        return self._db
    
    async def create(self, entity: Session) -> Session:
        """Create a new session."""
        doc_ref = self.db.collection(self.COLLECTION).document(entity.session_id)
        # Use helper or model_dump
        await doc_ref.set(entity.model_dump(mode='json'))
        
        logger.info(
            f"Session created: {entity.session_id}",
            session_id=entity.session_id,
            owner_id=entity.owner_id
        )
        return entity
    
    async def get_by_id(self, entity_id: str) -> Optional[Session]:
        """Get session by ID."""
        doc_ref = self.db.collection(self.COLLECTION).document(entity_id)
        doc = await doc_ref.get()
        
        if doc.exists:
            return Session.model_validate(doc.to_dict())
        return None
    
    async def update(self, entity_id: str, data: Dict[str, Any]) -> Session:
        """Partial update of session."""
        doc_ref = self.db.collection(self.COLLECTION).document(entity_id)
        await doc_ref.update(data)
        
        return await self.get_by_id(entity_id)
    
    async def delete(self, entity_id: str) -> bool:
        """Delete session (rarely used - prefer close)."""
        doc_ref = self.db.collection(self.COLLECTION).document(entity_id)
        await doc_ref.delete()
        return True
    
    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Session]:
        """List sessions with pagination."""
        query = (
            self.db.collection(self.COLLECTION)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .offset(offset)
        )
        
        docs = await query.get()
        return [Session.model_validate(doc.to_dict()) for doc in docs]
    
    async def get_active_by_user(self, user_id: str) -> Optional[Session]:
        """Get active session for user (only one allowed)."""
        query = (
            self.db.collection(self.COLLECTION)
            .where("owner_id", "==", user_id)
            .where("status", "==", "active")
            .limit(1)
        )
        
        docs = await query.get()
        if docs:
            return Session.model_validate(docs[0].to_dict())
        return None


    
    async def close_session(self, session_id: str) -> Session:
        """
        Mark session as closed. IRREVERSIBLE.
        Doctrine: Sessions cannot be reopened.
        """
        closed_at = TimeAuthority.now()
        
        # We need to explicitly convert datetime to string if firestore expects it, 
        # or rely on pydantic serialization.
        # But 'update' takes Dict. Pydantic model usually handles serializing fields to compatible types.
        # For Firestore, datetime objects are fine.
        
        await self.update(session_id, {
            "status": "closed",
            "closed_at": closed_at
        })
        
        logger.audit(
            action="SESSION_CLOSED",
            actor="system",
            target=session_id,
            justification="Session closure requested"
        )
        
        return await self.get_by_id(session_id)
    
    async def distill_session(self, session_id: str) -> Session:
        """
        Mark session as distilled. IRREVERSIBLE.
        Called after artifact extraction.
        """
        session = await self.get_by_id(session_id)
        if session.status != "closed":
            raise ValueError("Cannot distill session that is not closed")
        
        distilled_at = TimeAuthority.now()
        
        await self.update(session_id, {
            "status": "distilled",
            "distilled_at": distilled_at
        })
        
        logger.audit(
            action="SESSION_DISTILLED",
            actor="system",
            target=session_id,
            justification="Session artifact created and stored"
        )
        
        return await self.get_by_id(session_id)
