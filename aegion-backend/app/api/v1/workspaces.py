"""
Aegion Workspace API.

Endpoints for workspace management and collaboration.

Doctrine: "Workspaces are governance boundaries."
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import timezone, datetime, timedelta
import uuid

from pydantic import BaseModel, Field

from ...core.security import get_current_user, AuthorityContext
from ...core.logging import logger
from ...models.workspace import (
    Workspace, WorkspaceWithMembers, WorkspaceMember, 
    WorkspaceRole, WorkspaceInvite, WorkspaceActivity
)
from ...adapters.firestore.workspace_repository import FirestoreWorkspaceRepository
from .stream import broadcast_to_workspace
from ...ports.events import EventMessage


router = APIRouter(prefix="/workspaces", tags=["workspaces"])

# Repository instance
_repo = FirestoreWorkspaceRepository()


# ========== Request/Response Models ==========

class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class InviteMemberRequest(BaseModel):
    email: str = Field(..., description="Email to invite")
    role: WorkspaceRole = Field(default=WorkspaceRole.DEVELOPER)


class UpdateMemberRoleRequest(BaseModel):
    role: WorkspaceRole


class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    description: Optional[str]
    owner_id: str
    member_count: int
    created_at: datetime


# ========== Endpoints ==========

@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: CreateWorkspaceRequest,
    user: AuthorityContext = Depends(get_current_user)
) -> WorkspaceResponse:
    """
    Create a new workspace.
    
    The creating user becomes the owner.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    workspace_id = f"ws-{uuid.uuid4().hex[:12]}"
    
    workspace = Workspace(
        workspace_id=workspace_id,
        name=request.name,
        description=request.description,
        owner_id=user.user_id
    )
    
    owner_member = WorkspaceMember(
        user_id=user.user_id,
        role=WorkspaceRole.OWNER,
        display_name=user.display_name,
        email=user.email
    )
    
    await _repo.create(workspace, owner_member)
    
    logger.info(f"Workspace created: {workspace_id}", user_id=user.user_id)
    
    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        name=workspace.name,
        description=workspace.description,
        owner_id=workspace.owner_id,
        member_count=1,
        created_at=workspace.created_at
    )


@router.get("/{workspace_id}", response_model=WorkspaceWithMembers)
async def get_workspace(
    workspace_id: str,
    user: AuthorityContext = Depends(get_current_user)
) -> WorkspaceWithMembers:
    """
    Get workspace with members.
    
    User must be a member of the workspace.
    """
    workspace = await _repo.get_with_members(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Check membership
    if not workspace.get_member(user.user_id):
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    
    return workspace


@router.get("/", response_model=List[WorkspaceResponse])
async def list_my_workspaces(
    user: AuthorityContext = Depends(get_current_user)
) -> List[WorkspaceResponse]:
    """List all workspaces the user is a member of."""
    workspaces = await _repo.list_user_workspaces(user.user_id)
    
    responses = []
    for ws in workspaces:
        members = await _repo.list_members(ws.workspace_id)
        responses.append(WorkspaceResponse(
            workspace_id=ws.workspace_id,
            name=ws.name,
            description=ws.description,
            owner_id=ws.owner_id,
            member_count=len(members),
            created_at=ws.created_at
        ))
    
    return responses


@router.post("/{workspace_id}/invite")
async def invite_member(
    workspace_id: str,
    request: InviteMemberRequest,
    user: AuthorityContext = Depends(get_current_user)
) -> dict:
    """
    Invite a user to the workspace.
    
    Only owners and admins can invite.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    workspace = await _repo.get_with_members(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Check permission
    member = workspace.get_member(user.user_id)
    if not member or member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only owners and admins can invite")
    
    # Cannot invite as owner
    if request.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot invite as owner")
    
    invite = WorkspaceInvite(
        invite_id=f"inv-{uuid.uuid4().hex[:12]}",
        workspace_id=workspace_id,
        email=request.email,
        role=request.role,
        invited_by=user.user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    
    await _repo.create_invite(invite)
    
    # Log activity
    activity = WorkspaceActivity(
        activity_id=f"act-{uuid.uuid4().hex[:12]}",
        workspace_id=workspace_id,
        event_type="member.invited",
        actor_id=user.user_id,
        target_type="invite",
        target_id=invite.invite_id,
        description=f"Invited {request.email} as {request.role.value}"
    )
    await _repo.log_activity(activity)
    
    # Broadcast event
    await broadcast_to_workspace(workspace_id, EventMessage(
        event_id=activity.activity_id,
        event_type="member.invited",
        payload={"email": request.email, "role": request.role.value},
        metadata={},
        timestamp=datetime.now(timezone.utc)
    ))
    
    return {"invite_id": invite.invite_id, "expires_at": invite.expires_at}


@router.delete("/{workspace_id}/members/{member_user_id}")
async def remove_member(
    workspace_id: str,
    member_user_id: str,
    user: AuthorityContext = Depends(get_current_user)
) -> dict:
    """
    Remove a member from the workspace.
    
    Owners can remove anyone except themselves.
    Admins can remove developers and viewers.
    Users can remove themselves.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    workspace = await _repo.get_with_members(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    actor = workspace.get_member(user.user_id)
    target = workspace.get_member(member_user_id)
    
    if not actor:
        raise HTTPException(status_code=403, detail="Not a member")
    
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    
    # Cannot remove owner
    if target.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot remove workspace owner")
    
    # Self-removal is always allowed (except owner)
    if user.user_id != member_user_id:
        # Check permission
        if actor.role == WorkspaceRole.OWNER:
            pass  # Owner can remove anyone
        elif actor.role == WorkspaceRole.ADMIN:
            if target.role in [WorkspaceRole.ADMIN, WorkspaceRole.OWNER]:
                raise HTTPException(status_code=403, detail="Admins cannot remove admins/owners")
        else:
            raise HTTPException(status_code=403, detail="Insufficient permission")
    
    await _repo.remove_member(workspace_id, member_user_id)
    
    # Broadcast event
    await broadcast_to_workspace(workspace_id, EventMessage(
        event_id=str(uuid.uuid4()),
        event_type="member.removed",
        payload={"user_id": member_user_id},
        metadata={},
        timestamp=datetime.now(timezone.utc)
    ))
    
    return {"status": "removed", "user_id": member_user_id}


@router.patch("/{workspace_id}/members/{member_user_id}/role")
async def update_member_role(
    workspace_id: str,
    member_user_id: str,
    request: UpdateMemberRoleRequest,
    user: AuthorityContext = Depends(get_current_user)
) -> dict:
    """
    Update a member's role.
    
    Only owners can change roles.
    Cannot change owner role.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    workspace = await _repo.get_with_members(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    actor = workspace.get_member(user.user_id)
    
    if not actor or actor.role != WorkspaceRole.OWNER:
        raise HTTPException(status_code=403, detail="Only owner can change roles")
    
    if request.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot assign owner role")
    
    await _repo.update_member_role(workspace_id, member_user_id, request.role)
    
    return {"status": "updated", "user_id": member_user_id, "role": request.role.value}


@router.get("/{workspace_id}/activity", response_model=List[WorkspaceActivity])
async def get_workspace_activity(
    workspace_id: str,
    limit: int = 50,
    user: AuthorityContext = Depends(get_current_user)
) -> List[WorkspaceActivity]:
    """Get recent activity for workspace."""
    workspace = await _repo.get_with_members(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if not workspace.get_member(user.user_id):
        raise HTTPException(status_code=403, detail="Not a member")
    
    return await _repo.get_recent_activity(workspace_id, limit)
