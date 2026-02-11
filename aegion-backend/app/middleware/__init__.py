"""
Aegion Middleware Package.

Security and request processing middleware.
"""

from .rate_limit import RateLimitMiddleware, RateLimitConfig
from .validation import (
    validate_id,
    validate_uuid,
    validate_email,
    sanitize_string,
    validate_list_size,
    validate_pagination,
    SafeIdMixin,
    SanitizedInputMixin,
)
from .cors_config import CORSConfig, setup_cors, get_cors_config
from .api_keys import APIKeyService, APIKeyScope, get_api_key_service


__all__ = [
    # Rate Limiting
    "RateLimitMiddleware",
    "RateLimitConfig",
    
    # Validation
    "validate_id",
    "validate_uuid",
    "validate_email",
    "sanitize_string",
    "validate_list_size",
    "validate_pagination",
    "SafeIdMixin",
    "SanitizedInputMixin",
    
    # CORS
    "CORSConfig",
    "setup_cors",
    "get_cors_config",
    
    # API Keys
    "APIKeyService",
    "APIKeyScope",
    "get_api_key_service",
]
