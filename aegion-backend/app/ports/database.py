"""
Aegion Database Port (Abstract Interface).

This is the hexagonal architecture PORT for all database operations.
Implementations (adapters) include:
- FirestoreAdapter (Phase 1-2)
- PostgresAdapter (Phase 3+)
- Neo4jAdapter (Phase 4+ for graph queries)

Doctrine: Application layer NEVER imports concrete adapters directly.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


class RepositoryPort(ABC, Generic[T]):
    """
    Generic repository interface for CRUD operations.
    All database adapters must implement this interface.
    """
    
    @abstractmethod
    async def create(self, entity: T) -> T:
        """Create a new entity. Returns the created entity with ID."""
        pass
    
    @abstractmethod
    async def get_by_id(self, entity_id: str) -> Optional[T]:
        """Retrieve entity by ID. Returns None if not found."""
        pass
    
    @abstractmethod
    async def update(self, entity_id: str, data: Dict[str, Any]) -> T:
        """Partial update. Returns updated entity."""
        pass
    
    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """Delete entity. Returns success status."""
        pass
    
    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """List entities with pagination."""
        pass


class SessionRepositoryPort(RepositoryPort["Session"]):
    """Session-specific repository operations."""
    
    @abstractmethod
    async def get_active_by_user(self, user_id: str) -> Optional["Session"]:
        """Get the active session for a user (only one allowed)."""
        pass
    
    @abstractmethod
    async def close_session(self, session_id: str) -> "Session":
        """Mark session as closed. Irreversible."""
        pass
    
    @abstractmethod
    async def distill_session(self, session_id: str) -> "Session":
        """Mark session as distilled (artifact created). Irreversible."""
        pass


class DecisionRepositoryPort(RepositoryPort["Decision"]):
    """Decision-specific repository operations."""
    
    @abstractmethod
    async def get_by_proposal_id(self, proposal_id: str) -> Optional["Decision"]:
        """Get decision linked to a proposal."""
        pass
    
    @abstractmethod
    async def get_by_tier(self, tier: str, status: str = None) -> List["Decision"]:
        """Get decisions by tier, optionally filtered by status."""
        pass
    
    @abstractmethod
    async def get_superseded_chain(self, decision_id: str) -> List["Decision"]:
        """Get the full supersession chain for a decision."""
        pass
    
    @abstractmethod
    async def get_state_at_time(self, timestamp: datetime) -> List["Decision"]:
        """Time-travel query: get decisions active at a point in time."""
        pass


class UserRepositoryPort(RepositoryPort["User"]):
    """User-specific repository operations."""
    
    @abstractmethod
    async def get_by_email(self, email: str) -> Optional["User"]:
        """Get user by email address."""
        pass
    
    @abstractmethod
    async def get_by_workspace(self, workspace_id: str) -> List["User"]:
        """Get all users in a workspace."""
        pass


class WorkspaceRepositoryPort(ABC):
    """Workspace-specific repository operations."""
    
    @abstractmethod
    async def create(self, workspace: "Workspace", owner: "WorkspaceMember") -> "Workspace":
        """Create workspace with owner."""
        pass
    
    @abstractmethod
    async def get(self, workspace_id: str) -> Optional["Workspace"]:
        """Get workspace by ID."""
        pass
    
    @abstractmethod
    async def get_with_members(self, workspace_id: str) -> Optional["WorkspaceWithMembers"]:
        """Get workspace with all members."""
        pass
    
    @abstractmethod
    async def add_member(self, workspace_id: str, member: "WorkspaceMember") -> "WorkspaceMember":
        """Add member to workspace."""
        pass
    
    @abstractmethod
    async def remove_member(self, workspace_id: str, user_id: str) -> None:
        """Remove member from workspace."""
        pass
    
    @abstractmethod
    async def list_user_workspaces(self, user_id: str) -> List["Workspace"]:
        """List all workspaces user is a member of."""
        pass


class EvidenceRepositoryPort(RepositoryPort["Evidence"]):
    """Evidence-specific repository operations."""
    
    @abstractmethod
    async def get_by_proposal(self, proposal_id: str) -> List["Evidence"]:
        """Get all evidence linked to a proposal."""
        pass
    
    @abstractmethod
    async def get_supporting(self, proposal_id: str) -> List["Evidence"]:
        """Get only supporting evidence for a proposal."""
        pass


class AuditLogRepositoryPort(ABC):
    """Append-only audit log. No update or delete."""
    
    @abstractmethod
    async def append(self, event: "AuditEvent") -> "AuditEvent":
        """Append an audit event. Immutable."""
        pass
    
    @abstractmethod
    async def query_by_actor(self, actor_id: str, limit: int = 100) -> List["AuditEvent"]:
        """Query audit events by actor."""
        pass
    
    @abstractmethod
    async def query_by_target(self, target_id: str, limit: int = 100) -> List["AuditEvent"]:
        """Query audit events by target."""
        pass
    
    @abstractmethod
    async def query_by_timerange(
        self, start: datetime, end: datetime, limit: int = 1000
    ) -> List["AuditEvent"]:
        """Query audit events within a time range."""
        pass


# Type hints for forward references (actual models in contracts/)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..contracts.session import Session
    from ..models.decision import Decision
    from ..contracts.user import User
    from ..contracts.evidence import Evidence
    from ..contracts.audit_event import AuditEvent
