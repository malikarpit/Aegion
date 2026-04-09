"""
Aegion API v1 - Secrets Management.

Feature: Vault-backed secrets with short-lived access tokens.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from ...core.security import AuthorityContext, Role, get_current_user
from ...core.logging import logger
from ...services.vault import get_vault


router = APIRouter(prefix="/secrets", tags=["secrets"])


class StoreSecretRequest(BaseModel):
    key: str
    value: str


class SecretTokenResponse(BaseModel):
    key: str
    token: str
    expires_in_seconds: int


class RetrieveSecretResponse(BaseModel):
    key: str
    value: str  # The actual secret (only returned via token exchange)


@router.post("", status_code=status.HTTP_201_CREATED)
async def store_secret(
    request: StoreSecretRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Store a secret in the vault (Admin only)."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can manage secrets")
        
    vault = get_vault()
    vault.store_secret(request.key, request.value)
    
    logger.audit(
        action="SECRET_STORED",
        actor=user.user_id,
        target=request.key,
        justification="Secret stored/updated"
    )
    return {"message": "Secret stored successfully"}


@router.get("/{key}/token", response_model=SecretTokenResponse)
async def get_secret_token(
    key: str,
    ttl: int = 300,
    user: AuthorityContext = Depends(get_current_user),
):
    """Generate a short-lived token to access a secret."""
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can access secrets")
        
    vault = get_vault()
    try:
        token = vault.generate_token(key, ttl_seconds=ttl)
    except ValueError:
        raise HTTPException(status_code=404, detail="Secret not found")
        
    return SecretTokenResponse(
        key=key,
        token=token,
        expires_in_seconds=ttl
    )


@router.post("/redeem", response_model=RetrieveSecretResponse)
async def redeem_secret_token(
    token: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Redeem a token to retrieve a secret value."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # Note: Anyone with a valid token can redeem it, assuming they can auth to the API.
    # In strict mode, we might bind token to user_id.
    
    vault = get_vault()
    value = vault.redeem_token(token)
    
    if not value:
        raise HTTPException(status_code=403, detail="Invalid or expired token")
        
    return RetrieveSecretResponse(
        key="<redacted>", # Don't echo key name if not needed, or we'd need to store it in token data
        value=value
    )


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    key: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Delete a secret."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can manage secrets")
        
    vault = get_vault()
    vault.delete_secret(key)
    
    logger.audit(
        action="SECRET_DELETED",
        actor=user.user_id,
        target=key,
        justification="Secret deleted"
    )
