"""
Aegion SessionGuard Middleware.

Doctrine: "Missing Session Boundary Enforcement is a hard failure."
This middleware ensures that every request to the Aegion Backend:
1. Carries a valid Session Token.
2. Carries a declared Intent.
3. Is logged with strict provenance (Actor, Session, Intent).

Requests failing these checks are rejected immediately (401/403).
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from .logging import logger
from .time import TimeAuthority
from ..middleware.session_security import (
    check_session_fingerprint,
    check_concurrent_sessions,
    check_token_binding,
)

class SessionGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 0. Strict Exempt List (Public/Safe Endpoints)
        EXEMPT_ROUTES = {
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/health",
            "/api/v1/health/live",
            "/api/v1/health/ready",
        }
        
        if request.url.path in EXEMPT_ROUTES:
            return await call_next(request)

        # 1. Enforce Session ID (Except for creation endpoints)
        session_id = request.headers.get("X-Aegion-Session")
        # Special exemption for session creation - they don't have an ID yet
        is_session_start = request.url.path.endswith("/sessions/start")

        if not session_id and not is_session_start:
            logger.warning("Blocked request missing Session ID", path=request.url.path)
            return await self._reject(401, "Missing X-Aegion-Session header")

        # 2. Enforce Intent Declaration (Provenance) - NO FALLBACKS
        intent = request.headers.get("X-Aegion-Intent")
        if not intent:
            logger.warning("Blocked request missing Intent", path=request.url.path)
            return await self._reject(400, "Missing X-Aegion-Intent header")

        # 2.5 Anti-impersonation checks (when session is present)
        if session_id:
            # Fingerprint check
            fp_ok, fp_warn = check_session_fingerprint(session_id, request)
            if not fp_ok:
                return await self._reject(403, f"Session fingerprint mismatch: {fp_warn}")

            # Concurrent session check
            user_id = request.headers.get("X-Aegion-User", "unknown")
            check_concurrent_sessions(user_id, session_id)

            # Token binding check
            jwt_id = request.headers.get("X-Aegion-JTI")
            check_token_binding(session_id, jwt_id)

        # 3. Time Authority Stamping
        # We don't trust client time, we generate our own AuditTime
        start_time = TimeAuthority.monotonic()
        
        # Process Request
        response = await call_next(request)
        
        # 4. Audit Log
        duration = TimeAuthority.duration(start_time)
        logger.info(
            "Request processed",
            session_id=session_id,
            path=request.url.path,
            status=response.status_code,
            duration=duration,
            intent=intent
        )

        return response

    async def _reject(self, status: int, detail: str):
        from starlette.responses import JSONResponse
        return JSONResponse(status_code=status, content={"detail": detail})
