
import json
import os
from typing import List, Optional
from pathlib import Path
from datetime import datetime

from app.ports.council import CouncilRepository
from app.domain.council import CouncilSession
from app.core.logging import logger

class FileCouncilRepository(CouncilRepository):
    """
    File-system based repository for Council Sessions.
    Stores each session as a separate JSON file for easy inspection.
    """
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self._ensure_dir()
        
    def _ensure_dir(self):
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
    def _get_file_path(self, session_id: str) -> Path:
        # Sanitize ID to prevent path traversal (though UUIDs are safe)
        safe_id = "".join([c for c in session_id if c.isalnum() or c in ('-', '_')])
        return self.data_dir / f"{safe_id}.json"

    async def save_session(self, session: CouncilSession) -> None:
        """Save session to JSON file."""
        file_path = self._get_file_path(session.session_id)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(session.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Failed to persist council session {session.session_id}: {e}")
            raise

    async def get_session(self, session_id: str) -> Optional[CouncilSession]:
        """Load session from JSON file."""
        file_path = self._get_file_path(session_id)
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read()
                return CouncilSession.model_validate_json(data)
        except Exception as e:
            logger.error(f"Failed to load council session {session_id}: {e}")
            return None

    async def find_sessions_by_proposal(self, proposal_id: str) -> List[CouncilSession]:
        """Scan directory for sessions matching proposal_id. Inefficient but simple for v1."""
        sessions = []
        # optimization: could maintain an index file, but directory scan is fine for < 1000 files
        try:
            for file_path in self.data_dir.glob("*.json"):
                try:
                    # Quick check: read file and parse
                    # Optimization: Could read first few lines if we enforce structure, 
                    # but JSON parse is safest.
                    with open(file_path, "r", encoding="utf-8") as f:
                        # We might utilize a lighter parsing or just load it
                        session = CouncilSession.model_validate_json(f.read())
                        if session.proposal_id == proposal_id:
                            sessions.append(session)
                except Exception:
                    continue # Skip corrupted files
        except Exception as e:
             logger.error(f"Error searching sessions: {e}")
             
        # Sort by start time descending
        sessions.sort(key=lambda s: s.started_at, reverse=True)
        return sessions

    async def get_all_sessions(self) -> List[CouncilSession]:
        """Retrieve all sessions."""
        sessions = []
        try:
            for file_path in self.data_dir.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        session = CouncilSession.model_validate_json(f.read())
                        sessions.append(session)
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            
        sessions.sort(key=lambda s: s.started_at, reverse=True)
        return sessions
