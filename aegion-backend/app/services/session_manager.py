"""
Aegion Session Manager.

Central service for managing collaboration sessions, including:
- Lifecycle (Open, Close, Distill)
- Ownership (Claim, Transfer, Release)
- State Synchronization

Doctrine: "Single owner per session."
"""

from typing import Optional, List
from datetime import datetime, timezone
import uuid

from ..models.collaboration import (
    SessionOwnership, OwnershipStatus, OwnershipTransfer, TransferReason
)
from ..models.session import Session, SessionStatus
from ..core.logging import logger
from ..core.errors import AppError, GovernanceError, ResourceNotFoundError

from ..services.durable_store import PostgresModelStore


class SessionManager:
    """
    Manages session lifecycle and ownership.
    Backed by Supabase PostgreSQL via PostgresModelStore (Phase 5).
    """
    
    def __init__(self):
        self._session_store = PostgresModelStore("sessions", Session, "session_id")
        self._ownership_store = PostgresModelStore("ownership", SessionOwnership, "session_id")

    def _validate_keys(self, workspace_id: str, session_id: str) -> None:
        """Preflight assertion: workspace_id must not collide with session_id."""
        if not workspace_id:
            raise ValueError("workspace_id is required for session operations")
        if workspace_id == session_id:
            raise ValueError(
                f"workspace_id ({workspace_id}) must not equal session_id — "
                f"key collision risk. Use the actual workspace ID."
            )

    async def create_session(self, workspace_id: str, owner_id: str) -> Session:
        """Create a new collaboration session."""
        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        
        session = Session(
            session_id=session_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            status=SessionStatus.ACTIVE,
            created_at=now,
            last_activity_at=now
        )
        
        # Initialize ownership
        ownership = SessionOwnership(
            session_id=session_id,
            workspace_id=workspace_id,
            owner_id=owner_id,
            status=OwnershipStatus.CLAIMED,
            updated_at=now
        )
        
        await self._session_store.save(session, session.workspace_id)
        await self._ownership_store.save(ownership, session.workspace_id)
        
        logger.info(f"Session created: {session_id}", owner=owner_id)
        
        from .audit_store import get_audit_store, AuditAction
        get_audit_store().record(
            action=AuditAction.SESSION_CREATED,
            actor=owner_id,
            target=session_id,
            workspace_id=workspace_id,
            metadata={"intent": "new_session"}
        )
        return session

    async def get_session(self, session_id: str, workspace_id: str = "global") -> Optional[Session]:
        return await self._session_store.load(workspace_id, session_id)

    async def get_ownership(self, session_id: str, workspace_id: str = "global") -> Optional[SessionOwnership]:
        return await self._ownership_store.load(workspace_id, session_id)

    async def claim_ownership(self, session_id: str, user_id: str, workspace_id: str = "global", force: bool = False) -> SessionOwnership:
        """
        Claim ownership of a session.
        fails if already owned by someone else (unless force=True).
        """
        self._validate_keys(workspace_id, session_id)
        ownership = await self._ownership_store.load(workspace_id, session_id)
        if not ownership:
             raise ValueError(f"Session {session_id} not found")
             
        now = datetime.now(timezone.utc)
        
        if ownership.status == OwnershipStatus.CLAIMED and ownership.owner_id != user_id:
            if not force:
                raise GovernanceError(f"Session is already owned by {ownership.owner_id}")
            
            # Record forced transfer
            transfer = OwnershipTransfer(
                from_user_id=ownership.owner_id,
                to_user_id=user_id,
                reason=TransferReason.FORCE,
                timestamp=now
            )
            ownership.history.append(transfer)
        
        elif ownership.status == OwnershipStatus.PENDING:
            # If pending transfer to THIS user, complete it
            if ownership.pending_transfer_to == user_id:
                transfer = OwnershipTransfer(
                    from_user_id=ownership.owner_id,
                    to_user_id=user_id,
                    reason=TransferReason.HANDOFF,
                    timestamp=now
                )
                ownership.history.append(transfer)
                ownership.pending_transfer_to = None
            elif not force:
                 raise GovernanceError(f"Session is pending transfer to {ownership.pending_transfer_to}")

        # Update ownership
        ownership.owner_id = user_id
        ownership.status = OwnershipStatus.CLAIMED
        ownership.updated_at = now
        
        await self._ownership_store.save(ownership, ownership.workspace_id)
        logger.info(f"Ownership claimed: {session_id} by {user_id}")
        return ownership

    async def transfer_ownership(self, session_id: str, current_owner_id: str, target_user_id: str, workspace_id: str = "global") -> SessionOwnership:
        """
        Initiate transfer of ownership to another user.
        """
        self._validate_keys(workspace_id, session_id)
        ownership = await self._ownership_store.load(workspace_id, session_id)
        if not ownership:
             raise ValueError(f"Session {session_id} not found")
             
        if ownership.owner_id != current_owner_id:
             raise GovernanceError("Only the current owner can transfer ownership")
             
        ownership.status = OwnershipStatus.PENDING
        ownership.pending_transfer_to = target_user_id
        ownership.updated_at = datetime.now(timezone.utc)
        
        await self._ownership_store.save(ownership, ownership.workspace_id)
        logger.info(f"Ownership transfer initiated: {session_id} from {current_owner_id} to {target_user_id}")
        return ownership

    async def release_ownership(self, session_id: str, user_id: str, workspace_id: str = "global") -> SessionOwnership:
        """
        Release ownership, making the session free to claim.
        """
        self._validate_keys(workspace_id, session_id)
        ownership = await self._ownership_store.load(workspace_id, session_id)
        if not ownership:
             raise ValueError(f"Session {session_id} not found")
        
        if ownership.owner_id != user_id:
             raise GovernanceError("Only the current owner can release ownership")
             
        ownership.status = OwnershipStatus.RELEASED
        ownership.owner_id = None
        ownership.updated_at = datetime.now(timezone.utc)
        
        await self._ownership_store.save(ownership, ownership.workspace_id)
        logger.info(f"Ownership released: {session_id} by {user_id}")
        return ownership

    async def check_write_permission(self, session_id: str, user_id: str, workspace_id: str = "global") -> bool:
        """
        Check if user has write permission (is owner).
        """
        self._validate_keys(workspace_id, session_id)
        ownership = await self._ownership_store.load(workspace_id, session_id)
        if not ownership:
            return False
            
        return ownership.status == OwnershipStatus.CLAIMED and ownership.owner_id == user_id

    # ────────────────────────────────────────────────────────
    # Phase 7: Session Lifecycle Extensions
    # ────────────────────────────────────────────────────────

    async def add_artifact(self, session_id: str, artifact: dict, workspace_id: str = "global") -> dict:
        """Add an artifact to the session's metadata."""
        self._validate_keys(workspace_id, session_id)
        session = await self.get_session(session_id, workspace_id)
        if not session:
            raise ResourceNotFoundError(f"Session {session_id} not found")
        
        artifacts = session.metadata.get("artifacts", [])
        artifact_entry = {**artifact, "added_at": datetime.now(timezone.utc).isoformat()}
        artifacts.append(artifact_entry)
        session.metadata["artifacts"] = artifacts
        
        await self._session_store.save(session, session.workspace_id)
        return artifact_entry

    async def create_checkpoint(self, session_id: str, label: str, state: dict, workspace_id: str = "global", git_ref: Optional[str] = None) -> dict:
        """Create a recoverable state checkpoint."""
        self._validate_keys(workspace_id, session_id)
        session = await self.get_session(session_id, workspace_id)
        if not session:
            raise ResourceNotFoundError(f"Session {session_id} not found")
            
        from ..db.supabase_client import get_supabase_client
        client = get_supabase_client()
        result = client.table("session_checkpoints").insert({
            "workspace_id": session.workspace_id,
            "session_id": session_id,
            "label": label,
            "state_snapshot": state,
            "git_ref": git_ref
        }).execute()
        
        from .audit_store import get_audit_store, AuditAction
        get_audit_store().record(
            action=AuditAction.CHECKPOINT_CREATED,
            actor=session.owner_id,
            target=session_id,
            workspace_id=session.workspace_id,
            metadata={"label": label, "checkpoint_id": result.data[0]["id"]}
        )
        return result.data[0]

    async def close_session(self, session_id: str, workspace_id: str = "global") -> Session:
        """Mark a session as closed and ready for distillation."""
        self._validate_keys(workspace_id, session_id)
        session = await self.get_session(session_id, workspace_id)
        if not session:
            raise ResourceNotFoundError(f"Session {session_id} not found")
            
        session.status = SessionStatus.CLOSED
        session.closed_at = datetime.now(timezone.utc)
        await self._session_store.save(session, session.workspace_id)
        
        logger.info(f"Session closed: {session_id}")
        
        from .audit_store import get_audit_store
        artifacts_count = len(session.metadata.get("artifacts", []))
        get_audit_store().record(
            action="session_closed",
            actor="system",
            target=session_id,
            workspace_id=session.workspace_id,
            metadata={"artifacts_count": artifacts_count}
        )
        return session

    async def recover_session(self, session_id: str, workspace_id: str = "global", checkpoint_id: Optional[str] = None) -> Session:
        """Recover an active session, optionally from a specific checkpoint."""
        self._validate_keys(workspace_id, session_id)
        session = await self.get_session(session_id, workspace_id)
        if not session:
            raise ResourceNotFoundError(f"Session {session_id} not found")
            
        state = {}
        if checkpoint_id:
            from ..db.supabase_client import get_supabase_client
            client = get_supabase_client()
            checkpoint = client.table("session_checkpoints").select("*").eq("id", checkpoint_id).single().execute()
            if checkpoint.data:
                state = checkpoint.data["state_snapshot"]
        
        session.status = SessionStatus.ACTIVE
        session.metadata["recovered_state"] = state
        await self._session_store.save(session, session.workspace_id)
        
        from .audit_store import get_audit_store, AuditAction
        get_audit_store().record(
            action=AuditAction.SESSION_RECOVERED,
            actor=session.owner_id,
            target=session_id,
            workspace_id=session.workspace_id,
            metadata={"checkpoint_id": checkpoint_id} if checkpoint_id else {}
        )
        return session

# Singleton instance
_session_manager = SessionManager()

def get_session_manager() -> SessionManager:
    return _session_manager
