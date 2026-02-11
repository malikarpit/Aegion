"""
Aegion CORS Configuration.

Production-ready CORS settings with environment-specific origins.
"""

from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from ..core.config import settings
from ..core.logging import logger


# Default allowed origins by environment
DEFAULT_ORIGINS = {
    "development": [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "vscode-webview://*",
    ],
    "staging": [
        "https://staging.aegion.app",
        "https://staging-api.aegion.app",
    ],
    "production": [
        "https://aegion.app",
        "https://app.aegion.io",
        "https://api.aegion.io",
    ],
}


class CORSConfig:
    """CORS configuration manager."""
    
    def __init__(
        self,
        allowed_origins: Optional[List[str]] = None,
        allow_credentials: bool = True,
        allow_methods: Optional[List[str]] = None,
        allow_headers: Optional[List[str]] = None,
        expose_headers: Optional[List[str]] = None,
        max_age: int = 600,  # 10 minutes
    ):
        self.environment = getattr(settings, 'ENVIRONMENT', 'development')
        
        # Use provided origins or defaults for environment
        if allowed_origins:
            self.allowed_origins = allowed_origins
        else:
            self.allowed_origins = self._get_origins_from_env()
        
        self.allow_credentials = allow_credentials
        
        self.allow_methods = allow_methods or [
            "GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"
        ]
        
        self.allow_headers = allow_headers or [
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Session-ID",
            "X-Workspace-ID",
            "Accept",
            "Origin",
        ]
        
        self.expose_headers = expose_headers or [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-Request-ID",
        ]
        
        self.max_age = max_age
    
    def _get_origins_from_env(self) -> List[str]:
        """Get allowed origins from environment or config."""
        # Check for CORS_ORIGINS env var
        cors_origins_str = getattr(settings, 'CORS_ORIGINS', None)
        if cors_origins_str:
            return [o.strip() for o in cors_origins_str.split(',')]
        
        # Fall back to environment defaults
        return DEFAULT_ORIGINS.get(self.environment, DEFAULT_ORIGINS["development"])
    
    def validate_origin(self, origin: str) -> bool:
        """Check if an origin is allowed."""
        if "*" in self.allowed_origins:
            return True
        
        for allowed in self.allowed_origins:
            if allowed.endswith("*"):
                # Wildcard match (e.g., "vscode-webview://*")
                prefix = allowed[:-1]
                if origin.startswith(prefix):
                    return True
            elif origin == allowed:
                return True
        
        return False


def setup_cors(app: FastAPI, config: Optional[CORSConfig] = None) -> None:
    """
    Add CORS middleware to FastAPI app.
    
    Usage:
        from app.middleware.cors_config import setup_cors
        setup_cors(app)
    """
    if config is None:
        config = CORSConfig()
    
    logger.info(
        f"Setting up CORS for {config.environment} with origins: {config.allowed_origins}"
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=config.allow_credentials,
        allow_methods=config.allow_methods,
        allow_headers=config.allow_headers,
        expose_headers=config.expose_headers,
        max_age=config.max_age,
    )


# Default singleton
_cors_config: Optional[CORSConfig] = None


def get_cors_config() -> CORSConfig:
    """Get CORS configuration singleton."""
    global _cors_config
    if _cors_config is None:
        _cors_config = CORSConfig()
    return _cors_config
