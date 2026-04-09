"""
Structured JSON Logging Middleware — Phase 74.

Captures all HTTP requests and responses as structured JSON logs,
including trace/correlation IDs, latency, and response status.
Provides GCP-compatible structured logging formats.
"""

import time
import json
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable, Awaitable

logger = logging.getLogger("aegion.http")


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start_time = time.monotonic()
        
        # Extract correlation ID if set by previous middleware
        correlation_id = request.headers.get("X-Correlation-ID", request.headers.get("X-Request-ID", "unknown"))

        # Build initial log structure
        log_data = {
            "severity": "INFO",
            "message": f"HTTP {request.method} {request.url.path}",
            "httpRequest": {
                "requestMethod": request.method,
                "requestUrl": str(request.url),
                "userAgent": request.headers.get("user-agent", ""),
                "remoteIp": request.client.host if request.client else "",
                "protocol": f"HTTP/{request.scope.get('http_version', '1.1')}",
            },
            "logging.googleapis.com/trace": correlation_id,
            "workspace_id": request.headers.get("X-Workspace-ID", "global"),
        }

        try:
            response = await call_next(request)
            
            latency_ms = (time.monotonic() - start_time) * 1000
            
            # Update log with response data
            log_data["httpRequest"]["status"] = response.status_code
            log_data["httpRequest"]["latency"] = f"{latency_ms / 1000:.4f}s"
            
            if response.status_code >= 500:
                log_data["severity"] = "ERROR"
            elif response.status_code >= 400:
                log_data["severity"] = "WARNING"

            # Print JSON for fluentd / stackdriver to consume
            print(json.dumps(log_data))

            return response
            
        except Exception as exc:
            # Handle unhandled exceptions
            latency_ms = (time.monotonic() - start_time) * 1000
            log_data["httpRequest"]["status"] = 500
            log_data["httpRequest"]["latency"] = f"{latency_ms / 1000:.4f}s"
            log_data["severity"] = "CRITICAL"
            log_data["error_details"] = str(exc)
            
            print(json.dumps(log_data))
            raise
