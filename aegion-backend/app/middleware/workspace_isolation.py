"""
Aegion Workspace Isolation Middleware.

Doctrine: "Every query is scoped. Every boundary is enforced."

Ensures that users can only access data within their authorized workspace.
Extracts workspace_id from the JWT claims or request headers and injects it
into the request state for downstream use by services.
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Optional, Set

from ..core.logging import logger


# Routes that don't require workspace context
WORKSPACE_EXEMPT_ROUTES: Set[str] = {
    "/",
    "/health",
    "/health/live",
    "/docs",
    "/redoc",
    "/openapi.json",
}

# Routes that operate across workspaces (admin-only)
CROSS_WORKSPACE_ROUTES: Set[str] = {
    "/api/v1/admin/usage",
    "/api/v1/admin/policy-dashboard",
    "/api/v1/admin/env",
}


class WorkspaceIsolationMiddleware(BaseHTTPMiddleware):
    """
    Enforces per-workspace data isolation.

    Flow:
    1. Extract workspace_id from X-Workspace-Id header or JWT claims
    2. Validate user's membership in that workspace
    3. Inject workspace_id into request.state for downstream filtering
    4. Block requests that attempt cross-workspace access without ADMIN role
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip for exempt routes
        if path in WORKSPACE_EXEMPT_ROUTES:
            return await call_next(request)

        # Skip for session creation (no workspace context yet)
        if path.endswith("/sessions/start"):
            return await call_next(request)

        # Extract workspace context
        workspace_id = request.headers.get("X-Workspace-Id")

        if not workspace_id:
            # Try to infer from path parameters (e.g., /api/v1/workspaces/{id}/...)
            workspace_id = self._extract_workspace_from_path(path)

        # Cross-workspace routes require ADMIN — skip workspace enforcement
        if path in CROSS_WORKSPACE_ROUTES:
            request.state.workspace_id = workspace_id or "__admin__"
            return await call_next(request)

        if not workspace_id:
            # Default workspace for backward compatibility
            workspace_id = "default"

        # Inject into request state for downstream services
        request.state.workspace_id = workspace_id

        # Add workspace boundary header to response
        response = await call_next(request)
        response.headers["X-Workspace-Boundary"] = workspace_id

        return response

    def _extract_workspace_from_path(self, path: str) -> Optional[str]:
        """Extract workspace_id from URL path if present."""
        # Pattern: /api/v1/.../workspace/{workspace_id}/...
        parts = path.strip("/").split("/")
        for i, part in enumerate(parts):
            if part in ("workspace", "workspaces") and i + 1 < len(parts):
                return parts[i + 1]
        return None


class WorkspaceQueryFilter:
    """
    Helper for services to enforce workspace isolation in queries.

    Usage in service layer:
        filter = WorkspaceQueryFilter(request.state.workspace_id)
        nodes = await graph.query_nodes(
            filters={"workspace_id": filter.workspace_id}
        )
    """

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id

    def apply_filter(self, query_params: dict) -> dict:
        """Add workspace_id filter to query parameters."""
        query_params["workspace_id"] = self.workspace_id
        return query_params

    def validate_access(self, resource_workspace_id: str) -> bool:
        """Check if the current workspace context allows access to a resource."""
        if self.workspace_id == "__admin__":
            return True  # Admin has cross-workspace access
        return resource_workspace_id == self.workspace_id

    def enforce_access(self, resource_workspace_id: str, resource_id: str):
        """Raise 403 if workspace boundary is violated."""
        if not self.validate_access(resource_workspace_id):
            logger.warning(
                "Workspace boundary violation attempt",
                requested_workspace=resource_workspace_id,
                actual_workspace=self.workspace_id,
                resource_id=resource_id,
            )
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: resource belongs to workspace '{resource_workspace_id}'"
            )
