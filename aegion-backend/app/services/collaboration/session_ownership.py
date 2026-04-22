"""
Aegion Session Ownership Service.

Tracks session participants and ownership.

Doctrine: "Sessions have owners, decisions have authors."
"""

from typing import Dict, List, Optional, Set
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
import uuid

from ...core.logging import logger


class ParticipantRole(str, Enum):
    """Roles a participant can have in a session."""
    OWNER = "owner"
    COLLABORATOR = "collaborator"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class Participant(BaseModel):
    """A session participant."""
    user_id: str
    role: ParticipantRole
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    cursor_position: Optional[dict] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


class SessionParticipants(BaseModel):
    """Participants in a session."""
    session_id: str
    owner_id: str
    participants: Dict[str, Participant] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SessionOwnership:
    """
    Manages session participants and ownership.
    
    Invariants:
    - Every session has exactly one owner
    - Owner can transfer ownership
    - Participants can have different roles
    """
    
    def __init__(self):
        self._sessions: Dict[str, SessionParticipants] = {}
    
    def create_session(
        self, 
        session_id: str, 
        owner_id: str,
        owner_metadata: Dict[str, str] = None
    ) -> SessionParticipants:
        """Create a new session with owner."""
        owner = Participant(
            user_id=owner_id,
            role=ParticipantRole.OWNER,
            metadata=owner_metadata or {}
        )
        
        session = SessionParticipants(
            session_id=session_id,
            owner_id=owner_id,
            participants={owner_id: owner}
        )
        
        self._sessions[session_id] = session
        
        logger.info(
            f"Session created",
            session_id=session_id,
            owner_id=owner_id
        )
        
        return session
    
    def join_session(
        self,
        session_id: str,
        user_id: str,
        role: ParticipantRole = ParticipantRole.COLLABORATOR,
        metadata: Dict[str, str] = None
    ) -> Optional[Participant]:
        """Add participant to session."""
        session = self._sessions.get(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return None
        
        # Cannot join as owner
        if role == ParticipantRole.OWNER:
            role = ParticipantRole.COLLABORATOR
        
        participant = Participant(
            user_id=user_id,
            role=role,
            metadata=metadata or {}
        )
        
        session.participants[user_id] = participant
        
        logger.info(
            f"Participant joined session",
            session_id=session_id,
            user_id=user_id,
            role=role
        )
        
        return participant
    
    def leave_session(self, session_id: str, user_id: str) -> bool:
        """Remove participant from session."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        # Owner cannot leave without transferring ownership
        if user_id == session.owner_id:
            logger.warning(
                f"Owner cannot leave session without transferring ownership",
                session_id=session_id,
                owner_id=user_id
            )
            return False
        
        if user_id in session.participants:
            del session.participants[user_id]
            logger.info(
                f"Participant left session",
                session_id=session_id,
                user_id=user_id
            )
            return True
        
        return False
    
    def transfer_ownership(
        self, 
        session_id: str, 
        from_user_id: str, 
        to_user_id: str
    ) -> bool:
        """Transfer session ownership."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        # Only owner can transfer
        if session.owner_id != from_user_id:
            logger.warning(
                f"Only owner can transfer ownership",
                session_id=session_id,
                requester=from_user_id
            )
            return False
        
        # New owner must be participant
        if to_user_id not in session.participants:
            logger.warning(
                f"New owner must be participant",
                session_id=session_id,
                to_user_id=to_user_id
            )
            return False
        
        # Transfer
        old_owner = session.participants[from_user_id]
        old_owner.role = ParticipantRole.COLLABORATOR
        
        new_owner = session.participants[to_user_id]
        new_owner.role = ParticipantRole.OWNER
        
        session.owner_id = to_user_id
        
        logger.audit(
            action="SESSION_OWNERSHIP_TRANSFERRED",
            actor=from_user_id,
            target=to_user_id,
            justification=f"Ownership transferred from {from_user_id} to {to_user_id}",
            session_id=session_id
        )
        
        return True
    
    def get_participants(self, session_id: str) -> List[Participant]:
        """Get all participants in session."""
        session = self._sessions.get(session_id)
        if not session:
            return []
        return list(session.participants.values())
    
    def get_owner(self, session_id: str) -> Optional[str]:
        """Get session owner ID."""
        session = self._sessions.get(session_id)
        return session.owner_id if session else None
    
    def is_owner(self, session_id: str, user_id: str) -> bool:
        """Check if user is session owner."""
        session = self._sessions.get(session_id)
        return session is not None and session.owner_id == user_id
    
    def update_activity(self, session_id: str, user_id: str):
        """Update participant's last activity timestamp."""
        session = self._sessions.get(session_id)
        if session and user_id in session.participants:
            session.participants[user_id].last_activity = datetime.now(timezone.utc)
    
    def update_cursor(
        self, 
        session_id: str, 
        user_id: str, 
        position: dict
    ):
        """Update participant's cursor position."""
        session = self._sessions.get(session_id)
        if session and user_id in session.participants:
            session.participants[user_id].cursor_position = position
            session.participants[user_id].last_activity = datetime.now(timezone.utc)

    async def register_participant(self, session_id: str, user_id: str, role: str) -> None:
        """
        Register a participant (async wrapper for compatibility).
        Handles both creation (owner) and joining.
        """
        if role == "owner":
            # In a real persisting service, check if exists first
            if session_id not in self._sessions:
                self.create_session(session_id, user_id)
        else:
            self.join_session(session_id, user_id, ParticipantRole(role))


# Singleton instance
_session_ownership: Optional[SessionOwnership] = None


def get_session_ownership() -> SessionOwnership:
    """Get session ownership service singleton."""
    global _session_ownership
    if _session_ownership is None:
        _session_ownership = SessionOwnership()
    return _session_ownership
