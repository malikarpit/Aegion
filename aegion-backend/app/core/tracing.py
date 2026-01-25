"""
Aegion Request Tracing Middleware.

Adds request ID, timing, and context propagation to all requests.
"""

import uuid
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .cloud_logging import request_id_var, session_id_var, user_id_var, cloud_logger
from .metrics import metrics, AppMetrics


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Request tracing middleware.
    
    Features:
    - Generates unique request ID for each request
    - Propagates context variables for logging
    - Records request duration metrics
    - Adds tracing headers to response
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Extract session and user from headers/auth
        session_id = request.headers.get("X-Session-ID")
        user_id = getattr(request.state, "user_id", None)
        
        # Set context variables
        request_id_token = request_id_var.set(request_id)
        session_id_token = session_id_var.set(session_id)
        user_id_token = user_id_var.set(user_id)
        
        try:
            # Record request received
            AppMetrics.request_received(request.method, request.url.path)
            
            # Time the request
            start_time = time.perf_counter()
            
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Record completion metrics
            AppMetrics.request_completed(
                request.method,
                request.url.path,
                response.status_code,
                duration_ms
            )
            
            # Add tracing headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            
            # Log request completion
            if response.status_code >= 400:
                cloud_logger.warning(
                    f"{request.method} {request.url.path} - {response.status_code}",
                    method=request.method,
                    path=str(request.url.path),
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )
            else:
                cloud_logger.info(
                    f"{request.method} {request.url.path} - {response.status_code}",
                    method=request.method,
                    path=str(request.url.path),
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )
            
            return response
            
        except Exception as e:
            # Record error
            AppMetrics.error_occurred(type(e).__name__)
            cloud_logger.error(
                f"Request failed: {e}",
                method=request.method,
                path=str(request.url.path),
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise
            
        finally:
            # Reset context variables
            request_id_var.reset(request_id_token)
            session_id_var.reset(session_id_token)
            user_id_var.reset(user_id_token)
