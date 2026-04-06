"""
Aegion API v1 - Model Routing Endpoints.

List, select, and configure model routing profiles.

Feature: Multi-model routing profiles.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from pydantic import BaseModel

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger


router = APIRouter(prefix="/models", tags=["model-routing"])


# ========== Models ==========


class ModelProfileResponse(BaseModel):
    profile_id: str
    name: str
    provider: str
    model_id: str
    display_name: str
    context_window: int
    cost_tier: str
    capabilities: List[str]
    max_output_tokens: int
    description: str


class SetActiveRequest(BaseModel):
    workspace_id: str
    profile_name: str


class RegisterProfileRequest(BaseModel):
    name: str
    provider: str
    model_id: str
    display_name: str
    context_window: int = 128_000
    cost_tier: str = "medium"
    capabilities: List[str] = ["code", "chat"]
    max_output_tokens: int = 8192
    description: str = ""


# ========== Endpoints ==========


@router.get("", response_model=List[ModelProfileResponse])
async def list_models(
    user: AuthorityContext = Depends(get_current_user),
):
    """List all available model profiles."""
    from ...services.model_registry import get_model_registry
    registry = get_model_registry()

    return [
        ModelProfileResponse(
            profile_id=p.profile_id,
            name=p.name,
            provider=p.provider,
            model_id=p.model_id,
            display_name=p.display_name,
            context_window=p.context_window,
            cost_tier=p.cost_tier.value,
            capabilities=p.capabilities,
            max_output_tokens=p.max_output_tokens,
            description=p.description,
        )
        for p in registry.list_profiles()
    ]


@router.get("/active", response_model=ModelProfileResponse)
async def get_active_model(
    workspace_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get the active model profile for a workspace."""
    from ...services.model_registry import get_model_registry
    registry = get_model_registry()
    p = registry.get_active(workspace_id)

    return ModelProfileResponse(
        profile_id=p.profile_id,
        name=p.name,
        provider=p.provider,
        model_id=p.model_id,
        display_name=p.display_name,
        context_window=p.context_window,
        cost_tier=p.cost_tier.value,
        capabilities=p.capabilities,
        max_output_tokens=p.max_output_tokens,
        description=p.description,
    )


@router.put("/active")
async def set_active_model(
    request: SetActiveRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Set the active model profile for a workspace."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    from ...services.model_registry import get_model_registry
    registry = get_model_registry()

    success = registry.set_active(request.workspace_id, request.profile_name)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Profile '{request.profile_name}' not found",
        )

    logger.info(f"Active model set: {request.profile_name} for workspace {request.workspace_id}")
    return {"workspace_id": request.workspace_id, "active_profile": request.profile_name}


@router.post("/register", response_model=ModelProfileResponse)
async def register_custom_model(
    request: RegisterProfileRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Register a custom model profile."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    from ...services.model_registry import get_model_registry, ModelProfile, CostTier
    registry = get_model_registry()

    profile = ModelProfile(
        profile_id=request.name,
        name=request.name,
        provider=request.provider,
        model_id=request.model_id,
        display_name=request.display_name,
        context_window=request.context_window,
        cost_tier=CostTier(request.cost_tier),
        capabilities=request.capabilities,
        max_output_tokens=request.max_output_tokens,
        description=request.description,
    )

    registered = registry.register_custom(profile)

    return ModelProfileResponse(
        profile_id=registered.profile_id,
        name=registered.name,
        provider=registered.provider,
        model_id=registered.model_id,
        display_name=registered.display_name,
        context_window=registered.context_window,
        cost_tier=registered.cost_tier.value,
        capabilities=registered.capabilities,
        max_output_tokens=registered.max_output_tokens,
        description=registered.description,
    )


# ── ACK Model Catalog (Phase 9 Enhanced) ──

@router.get("/catalog", summary="Full ACK model catalog with pricing")
async def model_catalog(
    provider: Optional[str] = None,
    capability: Optional[str] = None,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    List all 50+ models from the ACK model catalog with pricing and capabilities.

    Optionally filter by provider name or required capability.
    """
    from ...services.council_kernel.model_router import MODEL_CATALOG, ModelCapability

    results = []
    for model_id, spec in MODEL_CATALOG.items():
        if provider and spec.provider != provider:
            continue
        if capability:
            try:
                cap = ModelCapability(capability)
                if cap not in spec.capabilities:
                    continue
            except ValueError:
                pass

        results.append({
            "model_id": spec.model_id,
            "provider": spec.provider,
            "display_name": spec.display_name,
            "context_window": spec.context_window,
            "max_output_tokens": spec.max_output_tokens,
            "input_price_per_m": spec.input_price_per_m,
            "output_price_per_m": spec.output_price_per_m,
            "capabilities": [c.value for c in spec.capabilities],
            "tier": spec.tier,
            "supports_streaming": spec.supports_streaming,
            "deprecated": spec.deprecated,
        })

    # Sort by tier then price
    results.sort(key=lambda m: (m["tier"], m["input_price_per_m"]))
    return {"models": results, "total": len(results)}


@router.get("/catalog/providers", summary="List available ACK providers")
async def list_providers(
    user: AuthorityContext = Depends(get_current_user),
):
    """List all supported LLM providers with their model counts."""
    from ...services.council_kernel.model_router import MODEL_CATALOG

    providers: dict = {}
    for spec in MODEL_CATALOG.values():
        if spec.provider not in providers:
            providers[spec.provider] = {"model_count": 0, "cheapest_input": float("inf")}
        providers[spec.provider]["model_count"] += 1
        providers[spec.provider]["cheapest_input"] = min(
            providers[spec.provider]["cheapest_input"], spec.input_price_per_m
        )

    return {
        "providers": [
            {"name": name, "model_count": info["model_count"],
             "cheapest_input_per_m": info["cheapest_input"]}
            for name, info in sorted(providers.items())
        ]
    }
