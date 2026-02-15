import json
import os
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime

from ...ports.database import SessionRepositoryPort
from ...domain.session import Session
from ...core.logging import logger
from ...core.time import TimeAuthority

class FileSessionRepository(SessionRepositoryPort):
    """
    File-system based repository for User Sessions.
    Stores each session as a separate JSON file in .aegion/sessions/
    """
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self._ensure_dir()
        
    def _ensure_dir(self):
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
    def _get_file_path(self, session_id: str) -> Path:
        safe_id = "".join([c for c in session_id if c.isalnum() or c in ('-', '_')])
        return self.data_dir / f"{safe_id}.json"

    async def create(self, entity: Session) -> Session:
        """Create a new session."""
        file_path = self._get_file_path(entity.session_id)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(entity.model_dump_json(indent=2))
            logger.info(f"Session created: {entity.session_id}")
            return entity
        except Exception as e:
            logger.error(f"Failed to persist session {entity.session_id}: {e}")
            raise

    async def get_by_id(self, entity_id: str) -> Optional[Session]:
        """Get session by ID."""
        file_path = self._get_file_path(entity_id)
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return Session.model_validate_json(f.read())
        except Exception as e:
            logger.error(f"Failed to load session {entity_id}: {e}")
            return None

    async def update(self, entity_id: str, data: Dict[str, Any]) -> Session:
        """Partial update."""
        session = await self.get_by_id(entity_id)
        if not session:
            raise ValueError(f"Session {entity_id} not found")
        
        # Update fields
        current_data = session.model_dump()
        current_data.update(data)
        updated_session = Session.model_validate(current_data)
        
        await self.create(updated_session) # Overwrite file
        return updated_session

    async def delete(self, entity_id: str) -> bool:
        """Delete session."""
        file_path = self._get_file_path(entity_id)
        if file_path.exists():
            os.remove(file_path)
            return True
        return False

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Session]:
        """List sessions."""
        sessions = []
        try:
            files = sorted(self.data_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
            # Pagination
            files = files[offset:offset+limit]
            
            for file_path in files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        sessions.append(Session.model_validate_json(f.read()))
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            
        return sessions

    async def get_active_by_user(self, user_id: str) -> Optional[Session]:
        """Get active session for user."""
        # Inefficient for file system, but acceptable for Local Mode v1
        all_sessions = await self.list_all(limit=1000) # Scan recent 1000
        for s in all_sessions:
            if s.owner_id == user_id and s.status == "active":
                return s
        return None

    async def close_session(self, session_id: str) -> Session:
        """Close session."""
        closed_at = TimeAuthority.now()
        await self.update(session_id, {
            "status": "closed",
            "closed_at": closed_at
        })
        return await self.get_by_id(session_id)

    async def distill_session(self, session_id: str) -> Session:
        """Distill session."""
        distilled_at = TimeAuthority.now()
        await self.update(session_id, {
            "status": "distilled",
            "distilled_at": distilled_at
        })
        return await self.get_by_id(session_id)
