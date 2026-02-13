"""
Aegion Security Headers Middleware — Enterprise Hardening.

Applies OWASP-recommended HTTP security headers to every response.

Headers applied:
- Strict-Transport-Security (HSTS with 2-year max-age, preload)
- X-Content-Type-Options (nosniff)
- X-Frame-Options (DENY)
- X-XSS-Protection (disabled — CSP is the correct control)
- Content-Security-Policy (default-src 'self', frame-ancestors 'none')
- Referrer-Policy (strict-origin-when-cross-origin)
- Permissions-Policy (disables geolocation, camera, microphone)
- Cache-Control (no-store for API responses)

Environment-aware:
- HSTS only in production/staging (preload only in production)
- Reporting URIs configurable per environment
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Dict, Optional

from ..core.config import settings
from ..core.logging import logger


# ========== Header Profiles ==========

_COMMON_HEADERS: Dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",  # Disabled — CSP replaces this
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(), payment=()",
    "X-Permitted-Cross-Domain-Policies": "none",
}

_PRODUCTION_HEADERS: Dict[str, str] = {
    **_COMMON_HEADERS,
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    ),
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
}

_STAGING_HEADERS: Dict[str, str] = {
    **_COMMON_HEADERS,
    "Strict-Transport-Security": "max-age=86400; includeSubDomains",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self';"
    ),
    "Cache-Control": "no-store",
}

_DEVELOPMENT_HEADERS: Dict[str, str] = {
    **_COMMON_HEADERS,
    # No HSTS in development (would break localhost HTTP)
    "Content-Security-Policy": (
        "default-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "img-src 'self' data:; "
        "frame-ancestors 'none';"
    ),
    "Cache-Control": "no-store",
}

# Map environments to header profiles
_HEADER_PROFILES = {
    "production": _PRODUCTION_HEADERS,
    "staging": _STAGING_HEADERS,
    "development": _DEVELOPMENT_HEADERS,
}

# Paths exempt from CSP (e.g., OpenAPI docs need inline scripts)
_CSP_EXEMPT_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies security headers to all HTTP responses.

    Environment-aware: headers are tuned per environment.
    CSP is relaxed for API documentation endpoints.
    """

    def __init__(self, app, environment: Optional[str] = None):
        super().__init__(app)
        self._environment = environment or getattr(settings, "environment", "development")
        self._headers = _HEADER_PROFILES.get(self._environment, _DEVELOPMENT_HEADERS)
        logger.info(
            f"Security headers middleware initialized",
            extra={"environment": self._environment, "header_count": len(self._headers)},
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Apply all configured headers
        for header, value in self._headers.items():
            # Skip CSP for doc endpoints (they need inline scripts for Swagger UI)
            if header == "Content-Security-Policy" and request.url.path in _CSP_EXEMPT_PATHS:
                continue
            response.headers[header] = value

        return response


# ========== Request Body Size Enforcement ==========

# Maximum request body sizes by content type
_MAX_BODY_SIZES = {
    "default": 1 * 1024 * 1024,      # 1 MB
    "upload": 10 * 1024 * 1024,       # 10 MB
}

# Paths that allow larger uploads
_UPLOAD_PATHS = frozenset({
    "/api/v1/evidence/upload",
    "/api/v1/artifacts/upload",
})


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces request body size limits.

    Returns 413 Payload Too Large if body exceeds limit.
    Upload endpoints have a higher limit.
    """

    def __init__(self, app, default_limit: int = _MAX_BODY_SIZES["default"],
                 upload_limit: int = _MAX_BODY_SIZES["upload"]):
        super().__init__(app)
        self._default_limit = default_limit
        self._upload_limit = upload_limit

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")

        if content_length is not None:
            try:
                body_size = int(content_length)
            except (ValueError, TypeError):
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )

            limit = (
                self._upload_limit
                if request.url.path in _UPLOAD_PATHS
                else self._default_limit
            )

            if body_size > limit:
                logger.warning(
                    "Request body too large",
                    extra={
                        "path": request.url.path,
                        "content_length": body_size,
                        "limit": limit,
                    },
                )
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Payload too large. Maximum: {limit // (1024*1024)}MB",
                    },
                )

        return await call_next(request)


def get_security_headers(environment: Optional[str] = None) -> Dict[str, str]:
    """Get the security headers for the given environment (utility for tests)."""
    env = environment or getattr(settings, "environment", "development")
    return dict(_HEADER_PROFILES.get(env, _DEVELOPMENT_HEADERS))
