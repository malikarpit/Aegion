"""
Aegion Workspace Repository - Firestore Implementation.

Doctrine: "Workspaces are governance boundaries."
"""

from typing import Optional, List
from datetime import datetime, timezone
import uuid

from google.cloud import firestore

from ...ports.database import WorkspaceRepositoryPort
from ...models.workspace import (
    Workspace, WorkspaceWithMembers, WorkspaceMember, 
    WorkspaceRole, WorkspaceInvite, WorkspaceActivity
)
from ...core.logging import logger


class FirestoreWorkspaceRepository(WorkspaceRepositoryPort):
    """Firestore implementation of workspace repository."""
    
    def __init__(self, db: firestore.Client = None):
        self._db = db
    
    @property
    def db(self) -> firestore.Client:
        if self._db is None:
            self._db = firestore.Client()
        return self._db
    
    def _workspaces_ref(self):
        return self.db.collection("workspaces")
    
    def _members_ref(self, workspace_id: str):
        return self._workspaces_ref().document(workspace_id).collection("members")
    
    def _invites_ref(self, workspace_id: str):
        return self._workspaces_ref().document(workspace_id).collection("invites")
    
    def _activity_ref(self, workspace_id: str):
        return self._workspaces_ref().document(workspace_id).collection("activity")
    
    # ========== Workspace CRUD ==========
    
    async def create(self, workspace: Workspace, owner_member: WorkspaceMember) -> Workspace:
        """Create workspace with owner."""
        # Save workspace
        self._workspaces_ref().document(workspace.workspace_id).set(
            workspace.model_dump(mode="json")
        )
        
        # Add owner as member
        self._members_ref(workspace.workspace_id).document(owner_member.user_id).set(
            owner_member.model_dump(mode="json")
        )
        
        logger.audit(
            action="WORKSPACE_CREATED",
            actor=owner_member.user_id,
            target=workspace.workspace_id
        )
        
        return workspace
    
    async def get(self, workspace_id: str) -> Optional[Workspace]:
        """Get workspace by ID."""
        doc = self._workspaces_ref().document(workspace_id).get()
        if not doc.exists:
            return None
        return Workspace(**doc.to_dict())
    
    async def get_with_members(self, workspace_id: str) -> Optional[WorkspaceWithMembers]:
        """Get workspace with all members."""
        workspace = await self.get(workspace_id)
        if not workspace:
            return None
        
        members = []
        for doc in self._members_ref(workspace_id).stream():
            members.append(WorkspaceMember(**doc.to_dict()))
        
        return WorkspaceWithMembers(
            **workspace.model_dump(),
            members=members
        )
    
    async def update(self, workspace: Workspace) -> Workspace:
        """Update workspace."""
        workspace.updated_at = datetime.now(timezone.utc)
        self._workspaces_ref().document(workspace.workspace_id).update(
            workspace.model_dump(mode="json")
        )
        return workspace
    
    async def delete(self, workspace_id: str) -> None:
        """Delete workspace and all subcollections."""
        # Delete members
        for doc in self._members_ref(workspace_id).stream():
            doc.reference.delete()
        
        # Delete invites
        for doc in self._invites_ref(workspace_id).stream():
            doc.reference.delete()
        
        # Delete activity
        for doc in self._activity_ref(workspace_id).stream():
            doc.reference.delete()
        
        # Delete workspace
        self._workspaces_ref().document(workspace_id).delete()
    
    # ========== Member Management ==========
    
    async def add_member(
        self, workspace_id: str, member: WorkspaceMember
    ) -> WorkspaceMember:
        """Add member to workspace."""
        self._members_ref(workspace_id).document(member.user_id).set(
            member.model_dump(mode="json")
        )
        
        logger.audit(
            action="MEMBER_ADDED",
            actor=member.invited_by or "system",
            target=f"{workspace_id}/{member.user_id}"
        )
        
        return member
    
    async def get_member(
        self, workspace_id: str, user_id: str
    ) -> Optional[WorkspaceMember]:
        """Get member of workspace."""
        doc = self._members_ref(workspace_id).document(user_id).get()
        if not doc.exists:
            return None
        return WorkspaceMember(**doc.to_dict())
    
    async def update_member_role(
        self, workspace_id: str, user_id: str, new_role: WorkspaceRole
    ) -> None:
        """Update member role."""
        self._members_ref(workspace_id).document(user_id).update({
            "role": new_role.value
        })
    
    async def remove_member(self, workspace_id: str, user_id: str) -> None:
        """Remove member from workspace."""
        self._members_ref(workspace_id).document(user_id).delete()
        
        logger.audit(
            action="MEMBER_REMOVED",
            actor="system",
            target=f"{workspace_id}/{user_id}"
        )
    
    async def list_members(self, workspace_id: str) -> List[WorkspaceMember]:
        """List all members of workspace."""
        members = []
        for doc in self._members_ref(workspace_id).stream():
            members.append(WorkspaceMember(**doc.to_dict()))
        return members
    
    # ========== Invites ==========
    
    async def create_invite(self, invite: WorkspaceInvite) -> WorkspaceInvite:
        """Create workspace invite."""
        self._invites_ref(invite.workspace_id).document(invite.invite_id).set(
            invite.model_dump(mode="json")
        )
        return invite
    
    async def get_invite(
        self, workspace_id: str, invite_id: str
    ) -> Optional[WorkspaceInvite]:
        """Get invite by ID."""
        doc = self._invites_ref(workspace_id).document(invite_id).get()
        if not doc.exists:
            return None
        return WorkspaceInvite(**doc.to_dict())
    
    async def accept_invite(self, workspace_id: str, invite_id: str) -> None:
        """Mark invite as accepted."""
        self._invites_ref(workspace_id).document(invite_id).update({
            "accepted": True,
            "accepted_at": datetime.now(timezone.utc).isoformat()
        })
    
    # ========== Activity ==========
    
    async def log_activity(self, activity: WorkspaceActivity) -> None:
        """Log workspace activity."""
        self._activity_ref(activity.workspace_id).document(activity.activity_id).set(
            activity.model_dump(mode="json")
        )
    
    async def get_recent_activity(
        self, workspace_id: str, limit: int = 50
    ) -> List[WorkspaceActivity]:
        """Get recent activity for workspace."""
        activities = []
        query = (
            self._activity_ref(workspace_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        for doc in query.stream():
            activities.append(WorkspaceActivity(**doc.to_dict()))
        return activities
    
    # ========== User's Workspaces ==========
    
    async def list_user_workspaces(self, user_id: str) -> List[Workspace]:
        """List all workspaces user is a member of."""
        # This requires a collection group query
        workspaces = []
        
        # Query all members collections for this user
        query = self.db.collection_group("members").where("user_id", "==", user_id)
        for doc in query.stream():
            # Get workspace from parent
            workspace_ref = doc.reference.parent.parent
            ws_doc = workspace_ref.get()
            if ws_doc.exists:
                workspaces.append(Workspace(**ws_doc.to_dict()))
        
        return workspaces
