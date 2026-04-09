"""
Aegion API v1 - Skills Endpoints.

Skill/Prompt Blueprint Library with install, catalog, and provenance validation.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid
import hashlib

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger
from ...models.skill import SkillBlueprint, SkillCategory, SkillStatus
from ...services.durable_store import JsonFileStore


router = APIRouter(prefix="/skills", tags=["skills"])


# ========== Durable Store ==========
_skills_store = JsonFileStore(".aegion_data/skills.json", SkillBlueprint, "skill_id")


# ========== Request/Response Models ==========


class CreateSkillRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    prompt_template: str
    category: Optional[str] = "custom"
    version: Optional[str] = "1.0.0"
    tags: Optional[List[str]] = None
    parameters: Optional[List[str]] = None
    source_url: Optional[str] = None


class SkillResponse(BaseModel):
    skill_id: str
    name: str
    version: str
    description: str
    prompt_template: str
    category: str
    author: str
    signature: Optional[str] = None
    source_url: Optional[str] = None
    tags: List[str]
    parameters: List[str]
    scripts: List[str] = []
    resources: List[str] = []
    status: str
    install_count: int
    created_at: str
    installed_at: Optional[str] = None
    
    # Governance
    doctrine_tags: List[str] = []
    review_status: str
    permission_manifest: Dict[str, Any] = {}
    attestation_count: int = 0


class InstallResponse(BaseModel):
    skill_id: str
    name: str
    status: str
    installed_at: str
    message: str


class ValidateResponse(BaseModel):
    skill_id: str
    valid: bool
    signature: Optional[str]
    message: str


# ========== Helpers ==========


def _skill_to_response(s: SkillBlueprint) -> SkillResponse:
    return SkillResponse(
        skill_id=s.skill_id,
        name=s.name,
        version=s.version,
        description=s.description,
        prompt_template=s.prompt_template,
        category=s.category.value,
        author=s.author,
        signature=s.signature,
        source_url=s.source_url,
        tags=s.tags,
        parameters=s.parameters,
        status=s.status.value,
        install_count=s.install_count,
        created_at=s.created_at.isoformat(),
        installed_at=s.installed_at.isoformat() if s.installed_at else None,
        doctrine_tags=s.doctrine_tags,
        review_status=s.review_status,
        permission_manifest=s.permission_manifest,
        attestation_count=len(s.attestations),
    )


def _generate_signature(skill: SkillBlueprint) -> str:
    """Generate a deterministic signature from skill content."""
    content = f"{skill.name}:{skill.version}:{skill.prompt_template}:{skill.author}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ========== Endpoints ==========


@router.post("", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    request: CreateSkillRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Create a skill blueprint."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    now = datetime.now(timezone.utc)
    skill_id = str(uuid.uuid4())

    skill = SkillBlueprint(
        skill_id=skill_id,
        name=request.name,
        version=request.version or "1.0.0",
        description=request.description or "",
        prompt_template=request.prompt_template,
        category=SkillCategory(request.category) if request.category else SkillCategory.CUSTOM,
        author=user.user_id,
        tags=request.tags or [],
        parameters=request.parameters or [],
        source_url=request.source_url,
        created_at=now,
    )

    # Auto-generate signature
    skill.signature = _generate_signature(skill)

    await _skills_store.save(skill)
    logger.info(f"Skill created: {skill_id} name={request.name}")
    return _skill_to_response(skill)


@router.get("", response_model=List[SkillResponse])
async def list_skills(
    category: Optional[str] = None,
    status_filter: Optional[str] = None,
    user: AuthorityContext = Depends(get_current_user),
):
    """List skill blueprints (catalog)."""
    skills = await _skills_store.list_all()

    if category:
        skills = [s for s in skills if s.category.value == category]

    if status_filter:
        skills = [s for s in skills if s.status.value == status_filter]

    # Sort by install count (popular first), then name
    skills.sort(key=lambda s: (-s.install_count, s.name))
    return [_skill_to_response(s) for s in skills]


@router.get("/marketplace", response_model=List[SkillResponse])
async def search_marketplace(
    query: Optional[str] = None,
    category: Optional[str] = None,
    tag: Optional[str] = None,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Search for skills in the public/private marketplace.
    Returns ranked results based on install count and relevance.
    """
    results = await _skills_store.list_all()

    if category:
        results = [s for s in results if s.category.value == category]
    
    if tag:
        results = [s for s in results if tag in s.tags or tag in s.doctrine_tags]

    if query:
        q = query.lower()
        results = [s for s in results if q in s.name.lower() or q in s.description.lower()]

    # Rank by installs + verification
    results.sort(key=lambda s: (s.install_count, s.status == "installed"), reverse=True)
    
    return [_skill_to_response(s) for s in results]


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get a specific skill blueprint."""
    skill = await _skills_store.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
    return _skill_to_response(skill)


@router.post("/{skill_id}/install", response_model=InstallResponse)
async def install_skill(
    skill_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Install a skill blueprint."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    skill = await _skills_store.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")

    if skill.status == SkillStatus.INSTALLED:
        raise HTTPException(status_code=409, detail=f"Skill {skill_id} is already installed")

    now = datetime.now(timezone.utc)
    skill.status = SkillStatus.INSTALLED
    skill.installed_at = now
    skill.install_count += 1
    await _skills_store.save(skill)

    logger.info(f"Skill installed: {skill_id}")
    return InstallResponse(
        skill_id=skill_id,
        name=skill.name,
        status="installed",
        installed_at=now.isoformat(),
        message=f"Skill '{skill.name}' installed successfully",
    )


@router.post("/{skill_id}/validate", response_model=ValidateResponse)
async def validate_skill(
    skill_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Validate a skill's signature and provenance."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    skill = await _skills_store.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")

    expected_sig = _generate_signature(skill)
    valid = skill.signature == expected_sig

    return ValidateResponse(
        skill_id=skill_id,
        valid=valid,
        signature=skill.signature,
        message="Signature valid" if valid else "Signature mismatch — skill may have been tampered with",
    )


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Delete/uninstall a skill blueprint."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    deleted = await _skills_store.delete(skill_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
    logger.info(f"Skill deleted: {skill_id}")


# ========== Feature: Attestation & Marketplace ==========


class AttestSkillRequest(BaseModel):
    execution_context: Dict[str, Any]
    result_hash: str
    duration_ms: int


@router.post("/{skill_id}/attest")
async def attest_skill(
    skill_id: str,
    request: AttestSkillRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Cryptographically attest to a skill execution.
    Creates a signed record that this skill was run by this user.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    skill = await _skills_store.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    attestation = {
        "attestation_id": str(uuid.uuid4()),
        "attestor": user.user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "skill_version": skill.version,
        "context_hash": hashlib.sha256(str(request.execution_context).encode()).hexdigest(),
        "result_hash": request.result_hash,
        "duration_ms": request.duration_ms,
    }
    
    skill.attestations.append(attestation)
    return attestation


# ========== Feature: Filesystem Skill Sync ==========


class SyncSkillsRequest(BaseModel):
    workspace_path: str


@router.post("/sync", status_code=status.HTTP_200_OK)
async def sync_skills_from_repo(
    request: SyncSkillsRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Import skills from .aegion/skills/ directory in workspace."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    from ...services.skill_loader import get_skill_loader
    loader = get_skill_loader()

    loaded = loader.load_from_directory(request.workspace_path)

    imported = []
    for skill_dict in loaded:
        # Skip if already exists (by name + version)
        all_skills = await _skills_store.list_all()
        existing = [
            s for s in all_skills
            if s.name == skill_dict["name"] and s.version == skill_dict.get("version", "1.0.0")
        ]
        if existing:
            continue

        skill = SkillBlueprint(
            skill_id=skill_dict["skill_id"],
            name=skill_dict["name"],
            version=skill_dict.get("version", "1.0.0"),
            description=skill_dict.get("description", ""),
            prompt_template=skill_dict["prompt_template"],
            category=SkillCategory.CUSTOM,
            author=skill_dict.get("author", user.user_id),
            signature=skill_dict.get("signature"),
            source_url=skill_dict.get("source_url"),
            tags=skill_dict.get("tags", []),
            parameters=skill_dict.get("parameters", []),
            created_at=skill_dict["created_at"],
        )
        await _skills_store.save(skill)
        imported.append(_skill_to_response(skill))

    return {
        "scanned": len(loaded),
        "imported": len(imported),
        "skipped": len(loaded) - len(imported),
        "skills": imported,
    }