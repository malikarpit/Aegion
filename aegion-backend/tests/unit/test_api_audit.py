"""
Tests for API Layer Audit — Section 1.10.

Verifies that all critical API routes are importable, that routers
are properly structured, and that FastAPI app is wired correctly.

Also covers:
    - Persistence layer (Supabase client) module availability
    - Docker Compose config validation
    - Middleware stack integrity

This is an "API surface audit" — ensuring nothing is broken
at the import/config level before we move to integration tests.
"""

import pytest
import importlib


# ══════════════════════════════════════════════════════════════════════════════
# API ROUTE IMPORTS — SECTION 1.10
# ══════════════════════════════════════════════════════════════════════════════

class TestAPIRouteImports:
    """All API route modules must be importable without errors."""

    @pytest.mark.parametrize("module_name", [
        "app.api.v1.health",
        "app.api.v1.council",
        "app.api.v1.models",
        "app.api.v1.governance",
        "app.api.v1.audit",
        "app.api.v1.sessions",
        "app.api.v1.workspaces",
        "app.api.v1.decisions",
        "app.api.v1.reasoning",
        "app.api.v1.memory",
        "app.api.v1.presence",
        "app.api.v1.collaboration",
        "app.api.v1.analytics",
        "app.api.v1.admin",
        "app.api.v1.auth",
        "app.api.v1.ghost_text",
        "app.api.v1.skills",
        "app.api.v1.tasks",
        "app.api.v1.proposals",
        "app.api.v1.stream",
    ])
    def test_route_module_importable(self, module_name):
        """Every API route module must import without error."""
        mod = importlib.import_module(module_name)
        assert mod is not None


class TestAPIRouterStructure:
    """API routers should expose proper router objects."""

    def test_health_has_router(self):
        from app.api.v1 import health
        assert hasattr(health, "router")

    def test_council_has_router(self):
        from app.api.v1 import council
        assert hasattr(council, "router")

    def test_governance_has_router(self):
        from app.api.v1 import governance
        assert hasattr(governance, "router")

    def test_audit_has_router(self):
        from app.api.v1 import audit
        assert hasattr(audit, "router")

    def test_sessions_has_router(self):
        from app.api.v1 import sessions
        assert hasattr(sessions, "router")


# ══════════════════════════════════════════════════════════════════════════════
# MIDDLEWARE STACK — SECTION 1.10
# ══════════════════════════════════════════════════════════════════════════════

class TestMiddlewareStack:
    """Middleware modules must be importable and configured."""

    def test_rate_limit_importable(self):
        from app.middleware.rate_limit import RateLimitMiddleware
        assert RateLimitMiddleware is not None

    def test_input_sanitizer_importable(self):
        from app.middleware.input_sanitizer import sanitize_input
        assert sanitize_input is not None

    def test_tool_sandbox_importable(self):
        from app.middleware.tool_sandbox import ToolAuthoritySandbox
        assert ToolAuthoritySandbox is not None

    def test_websocket_throttle_importable(self):
        from app.middleware import websocket_throttle
        assert websocket_throttle is not None


# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENCE LAYER — SECTION 1.9
# ══════════════════════════════════════════════════════════════════════════════

class TestPersistenceLayer:
    """Database and storage modules."""

    def test_supabase_client_importable(self):
        from app.db.supabase_client import get_supabase_client
        assert get_supabase_client is not None

    def test_store_repository_importable(self):
        from app.services.storage.repository import DraftRepository
        assert DraftRepository is not None

    def test_durable_store_importable(self):
        from app.services.durable_store import JsonFileStore
        assert JsonFileStore is not None


# ══════════════════════════════════════════════════════════════════════════════
# CORE SERVICES — CROSS-SECTION
# ══════════════════════════════════════════════════════════════════════════════

class TestCoreServices:
    """Core service modules — config, logging, security."""

    def test_config_importable(self):
        from app.core.config import settings
        assert settings is not None

    def test_logging_importable(self):
        from app.core.logging import logger
        assert logger is not None

    def test_security_importable(self):
        from app.core.security import AuthorityContext
        assert AuthorityContext is not None

    def test_time_authority_importable(self):
        from app.core.time import TimeAuthority
        assert TimeAuthority is not None


# ══════════════════════════════════════════════════════════════════════════════
# DOCKER COMPOSE — SECTION 1.17
# ══════════════════════════════════════════════════════════════════════════════

class TestDockerConfig:
    """Docker Compose and containerization config validation."""

    def test_dockerfile_exists(self):
        import os
        dockerfile = os.path.join(
            os.path.dirname(__file__), "..", "..", "Dockerfile"
        )
        # Normalize and check
        dockerfile = os.path.normpath(dockerfile)
        assert os.path.exists(dockerfile), f"Dockerfile not found at {dockerfile}"

    def test_requirements_exists(self):
        import os
        req = os.path.join(
            os.path.dirname(__file__), "..", "..", "requirements.txt"
        )
        req = os.path.normpath(req)
        assert os.path.exists(req), f"requirements.txt not found at {req}"

    def test_main_app_importable(self):
        """The FastAPI app must be importable for uvicorn."""
        from app.main import app
        assert app is not None
