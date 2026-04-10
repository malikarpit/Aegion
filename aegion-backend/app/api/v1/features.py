
from fastapi import APIRouter, Depends
from typing import Dict, List
from ...core.security import AuthorityContext, get_current_user
from ...core.feature_flags import get_feature_flags, FeatureFlag

router = APIRouter(prefix="/features", tags=["features"])

@router.get("/", response_model=Dict[str, bool])
async def get_features():
    """Get enabled status of all features."""
    return get_feature_flags().get_all_flags()

@router.get("/manifest", response_model=List[FeatureFlag])
async def get_feature_manifest(
    user: AuthorityContext = Depends(get_current_user)
):
    """Get full feature flag details (Admin only)."""
    # In a real app, check for admin role here
    return get_feature_flags().get_full_manifest()
