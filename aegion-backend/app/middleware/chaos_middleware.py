"""
Chaos Engineering Middleware.

Intercepts requests to inject latency or failures based on ChaosMonkey configuration.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from ..services.praxis.chaos import ChaosMonkey, _config
from ..core.logging import logger


class ChaosMiddleware(BaseHTTPMiddleware):
    """
    Middleware that invokes Chaos Monkey on every request.
    Only active if Chaos Configuration is enabled.
    """
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if _config.enabled:
            # We can inspect request path to exclude health checks or critical endpoints if needed
            if "/health" in request.url.path or "/metrics" in request.url.path:
                pass 
            else:
                try:
                    await ChaosMonkey.maybe_inject_chaos()
                except Exception as e:
                    # If chaos monkey raises an error (simulated failure), we catch it here 
                    # to log it properly as a chaos event, then re-raise or return 500.
                    # Standard exception handling will catch re-raised exceptions.
                    logger.warning(f"💥 Chaos Monkey intercepted request to {request.url.path}: {e}")
                    raise e

        response = await call_next(request)
        return response
