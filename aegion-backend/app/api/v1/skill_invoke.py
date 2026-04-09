"""
Aegion API v1 - Skill Invocation Endpoints.

URL-based skill invocation with HMAC-signed tokens:
- Generate time-limited invocation links
- Redeem tokens to render skill prompt templates
- Direct invoke with parameter substitution

Feature: Lightweight "send instruction link to agent" onboarding.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import json
import secrets
import base64

from ...core.logging import logger
from ...core.time import TimeAuthority
from ...core.security import get_current_user, AuthorityContext


router = APIRouter(prefix="/skills", tags=["skill-invoke"])


# ========== Configuration ==========

_HMAC_SECRET = secrets.token_bytes(32)   # Rotated on restart; production should use vault
_DEFAULT_TTL_SECONDS = 3600              # 1 hour


# ========== In-Memory Stores ==========

# We reference the skills store from the skills module
def _get_skills_store() -> dict:
    from .skills import _skills_store
    return _skills_store


# Track redeemed tokens (one-time use)
_redeemed_tokens: set[str] = set()

# Invocation audit log
_invocation_log: list[dict] = []


# ========== Request/Response Models ==========

class InvokeRequest(BaseModel):
    """Direct skill invocation with parameters."""
    parameters: Dict[str, str] = Field(default_factory=dict, description="Template parameter values")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional execution context")


class InvokeResponse(BaseModel):
    skill_id: str
    skill_name: str
    rendered_prompt: str
    invoked_at: str
    invoked_by: str


class GenerateLinkRequest(BaseModel):
    """Request to generate an invocation link."""
    parameters: Dict[str, str] = Field(default_factory=dict, description="Pre-filled parameters")
    ttl_seconds: int = Field(default=3600, ge=60, le=86400, description="Link TTL (60s to 24h)")
    max_uses: int = Field(default=1, ge=1, le=100, description="Maximum redemptions")
    label: Optional[str] = Field(None, description="Human-readable label for tracking")


class InvocationLink(BaseModel):
    invoke_url: str
    token: str
    skill_id: str
    skill_name: str
    expires_at: str
    max_uses: int
    created_by: str


class RedeemResponse(BaseModel):
    skill_id: str
    skill_name: str
    rendered_prompt: str
    parameters: Dict[str, str]
    redeemed_at: str


# ========== Helpers ==========

def _render_template(template: str, params: Dict[str, str]) -> str:
    """Substitute {{param}} placeholders in a prompt template."""
    rendered = template
    for key, value in params.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _sign_token(payload: dict) -> str:
    """Create an HMAC-signed token from a payload dict."""
    payload_json = json.dumps(payload, sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()
    sig = hmac.new(_HMAC_SECRET, payload_b64.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload_b64}.{sig}"


def _verify_token(token: str) -> Optional[dict]:
    """Verify and decode an HMAC-signed token. Returns payload or None."""
    try:
        payload_b64, sig = token.rsplit(".", 1)
        expected_sig = hmac.new(_HMAC_SECRET, payload_b64.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload_json = base64.urlsafe_b64decode(payload_b64).decode()
        return json.loads(payload_json)
    except Exception:
        return None


# ========== Endpoints ==========


@router.post("/{skill_id}/invoke", response_model=InvokeResponse)
async def invoke_skill(
    skill_id: str,
    request: InvokeRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Directly invoke a skill's prompt template with parameter substitution.
    Returns the fully rendered prompt ready to send to an agent.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    store = _get_skills_store()
    skill = store.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    rendered = _render_template(skill.prompt_template, request.parameters)
    now = TimeAuthority.now()

    # Audit log entry
    _invocation_log.append({
        "skill_id": skill_id,
        "invoked_by": user.user_id,
        "parameters": request.parameters,
        "timestamp": now,
        "method": "direct",
    })

    logger.info(f"Skill invoked directly: {skill.name} by {user.user_id}")

    return InvokeResponse(
        skill_id=skill_id,
        skill_name=skill.name,
        rendered_prompt=rendered,
        invoked_at=now,
        invoked_by=user.user_id,
    )


@router.post("/{skill_id}/invoke-link", response_model=InvocationLink)
async def generate_invoke_link(
    skill_id: str,
    request: GenerateLinkRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Generate a signed, time-limited invocation link for a skill.
    The link can be sent to any agent; redeeming it renders the prompt template.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    store = _get_skills_store()
    skill = store.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=request.ttl_seconds)
    ).isoformat() + "Z"

    payload = {
        "sid": skill_id,
        "params": request.parameters,
        "exp": expires_at,
        "max": request.max_uses,
        "by": user.user_id,
        "nonce": secrets.token_hex(8),
    }

    token = _sign_token(payload)

    # Build the URL (relative — the consuming system prefixes with base URL)
    invoke_url = f"/v1/skills/invoke/{token}"

    logger.info(f"Invocation link generated for skill {skill.name} by {user.user_id}")

    return InvocationLink(
        invoke_url=invoke_url,
        token=token,
        skill_id=skill_id,
        skill_name=skill.name,
        expires_at=expires_at,
        max_uses=request.max_uses,
        created_by=user.user_id,
    )


@router.get("/invoke/{token}", response_model=RedeemResponse)
async def redeem_invoke_link(token: str):
    """
    Redeem an invocation token to get the rendered prompt.
    No authentication required — the HMAC token IS the credential.
    """
    # Verify signature
    payload = _verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or tampered invocation token")

    # Check expiry
    try:
        expires = datetime.fromisoformat(payload["exp"].rstrip("Z")).replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            raise HTTPException(status_code=410, detail="Invocation link has expired")
    except (KeyError, ValueError):
        raise HTTPException(status_code=400, detail="Malformed token payload")

    # Check one-time use
    token_id = payload.get("nonce", token[:16])
    use_count = sum(1 for entry in _invocation_log if entry.get("nonce") == token_id)
    max_uses = payload.get("max", 1)
    if use_count >= max_uses:
        raise HTTPException(status_code=409, detail="Invocation link has been fully consumed")

    # Look up skill
    store = _get_skills_store()
    skill_id = payload["sid"]
    skill = store.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill no longer exists")

    params = payload.get("params", {})
    rendered = _render_template(skill.prompt_template, params)
    now = TimeAuthority.now()

    # Audit
    _invocation_log.append({
        "skill_id": skill_id,
        "invoked_by": payload.get("by", "link"),
        "parameters": params,
        "timestamp": now,
        "method": "link",
        "nonce": token_id,
    })

    logger.info(f"Invocation link redeemed for skill {skill.name}")

    return RedeemResponse(
        skill_id=skill_id,
        skill_name=skill.name,
        rendered_prompt=rendered,
        parameters=params,
        redeemed_at=now,
    )


@router.get("/{skill_id}/invocations")
async def list_invocations(
    skill_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """List invocation history for a skill."""
    return [
        entry for entry in _invocation_log
        if entry["skill_id"] == skill_id
    ]
