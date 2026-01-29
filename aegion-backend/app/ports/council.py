from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.council import CouncilSession

class CouncilRepository(ABC):
    @abstractmethod
    async def save_session(self, session: CouncilSession) -> None:
        """Save a council session."""
        pass
        
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[CouncilSession]:
        """Get a council session by ID."""
        pass
        
    @abstractmethod
    async def find_sessions_by_proposal(self, proposal_id: str) -> List[CouncilSession]:
        """Find all sessions associated with a proposal."""
        pass

    @abstractmethod
    async def get_all_sessions(self) -> List[CouncilSession]:
        """Retrieve all sessions (for debugging/admin)."""
        pass
