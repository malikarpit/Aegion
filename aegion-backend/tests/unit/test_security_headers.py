"""
Security Headers & API Hardening Tests.

Validates:
- Security headers applied per environment (production/staging/development)
- HSTS preload only in production
- CSP exemptions for API docs
- Request body size enforcement (1MB default, 10MB uploads)
- Token revocation list (individual + user-wide)
- Token revocation cleanup
"""

import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock

from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.requests import Request

from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
    get_security_headers,
    _PRODUCTION_HEADERS,
    _STAGING_HEADERS,
    _DEVELOPMENT_HEADERS,
)
from app.core.security import (
    TokenRevocationList,
    get_revocation_list,
    MAX_TOKEN_EXPIRY_SECONDS,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def _homepage(request: Request):
    return JSONResponse({"ok": True})


async def _docs(request: Request):
    return JSONResponse({"docs": True})


async def _upload(request: Request):
    return JSONResponse({"uploaded": True})


def _make_app(environment: str = "production"):
    app = Starlette(routes=[
        Route("/", _homepage),
        Route("/docs", _docs),
        Route("/api/v1/evidence/upload", _upload, methods=["POST"]),
    ])
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, environment=environment)
    return app


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Security Headers — Production
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestProductionHeaders:
    def setup_method(self):
        self.client = TestClient(_make_app("production"))

    def test_hsts_preload_in_production(self):
        response = self.client.get("/")
        hsts = response.headers.get("Strict-Transport-Security")
        assert hsts is not None
        assert "max-age=63072000" in hsts
        assert "preload" in hsts
        assert "includeSubDomains" in hsts

    def test_x_frame_options_deny(self):
        response = self.client.get("/")
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_x_content_type_options(self):
        response = self.client.get("/")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_xss_protection_disabled(self):
        """X-XSS-Protection should be '0' (CSP replaces it)."""
        response = self.client.get("/")
        assert response.headers.get("X-XSS-Protection") == "0"

    def test_csp_present_in_production(self):
        response = self.client.get("/")
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_referrer_policy(self):
        response = self.client.get("/")
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self):
        response = self.client.get("/")
        pp = response.headers.get("Permissions-Policy")
        assert "geolocation=()" in pp
        assert "camera=()" in pp

    def test_cache_control_no_store(self):
        response = self.client.get("/")
        assert "no-store" in response.headers.get("Cache-Control", "")

    def test_csp_exempt_for_docs(self):
        """CSP should NOT be applied to /docs endpoint."""
        response = self.client.get("/docs")
        assert response.headers.get("Content-Security-Policy") is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Security Headers — Staging
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestStagingHeaders:
    def setup_method(self):
        self.client = TestClient(_make_app("staging"))

    def test_hsts_short_maxage_in_staging(self):
        response = self.client.get("/")
        hsts = response.headers.get("Strict-Transport-Security")
        assert hsts is not None
        assert "max-age=86400" in hsts
        assert "preload" not in hsts  # No preload in staging


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Security Headers — Development
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDevelopmentHeaders:
    def setup_method(self):
        self.client = TestClient(_make_app("development"))

    def test_no_hsts_in_development(self):
        """HSTS should NOT be present in development (would break localhost HTTP)."""
        response = self.client.get("/")
        assert response.headers.get("Strict-Transport-Security") is None

    def test_relaxed_csp_in_development(self):
        response = self.client.get("/")
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "'unsafe-inline'" in csp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Request Size Limiting
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestRequestSizeLimit:
    def setup_method(self):
        self.client = TestClient(_make_app("production"))

    def test_rejects_oversized_body(self):
        """Default 1MB limit should reject 2MB body."""
        response = self.client.get("/", headers={"Content-Length": str(2 * 1024 * 1024)})
        assert response.status_code == 413

    def test_allows_normal_body(self):
        """Small body should pass."""
        response = self.client.get("/", headers={"Content-Length": "1024"})
        assert response.status_code == 200

    def test_rejects_invalid_content_length(self):
        """Non-numeric Content-Length should return 400."""
        response = self.client.get("/", headers={"Content-Length": "abc"})
        assert response.status_code == 400

    def test_upload_has_higher_limit(self):
        """Upload endpoint should allow up to 10MB."""
        # 5MB should be fine for upload
        response = self.client.post(
            "/api/v1/evidence/upload",
            headers={"Content-Length": str(5 * 1024 * 1024)},
        )
        assert response.status_code == 200

    def test_upload_rejects_over_10mb(self):
        """Upload endpoint should reject > 10MB."""
        response = self.client.post(
            "/api/v1/evidence/upload",
            headers={"Content-Length": str(15 * 1024 * 1024)},
        )
        assert response.status_code == 413


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Token Revocation List
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestTokenRevocationList:
    def setup_method(self):
        self.trl = TokenRevocationList.get_instance()
        self.trl.clear()

    def test_revoke_individual_token(self):
        self.trl.revoke_token("jti-abc-123")
        assert self.trl.is_revoked("jti-abc-123") is True

    def test_non_revoked_token_passes(self):
        assert self.trl.is_revoked("jti-clean-456") is False

    def test_revoke_user_tokens(self):
        """All tokens issued before revocation should be revoked."""
        issued_at = time.time() - 60  # Issued 60s ago
        self.trl.revoke_user_tokens("user-1")
        assert self.trl.is_revoked("jti-any", user_id="user-1", issued_at=issued_at) is True

    def test_user_revocation_allows_new_tokens(self):
        """Tokens issued AFTER user revocation should pass."""
        self.trl.revoke_user_tokens("user-1")
        issued_at = time.time() + 10  # Issued in the future
        assert self.trl.is_revoked("jti-new", user_id="user-1", issued_at=issued_at) is False

    def test_cleanup_removes_expired(self):
        """Tokens older than MAX_TOKEN_EXPIRY should be cleaned up."""
        self.trl._revoked_jtis["old-jti"] = time.time() - MAX_TOKEN_EXPIRY_SECONDS - 100
        self.trl._revoked_jtis["fresh-jti"] = time.time()
        removed = self.trl.cleanup_expired()
        assert removed == 1
        assert "old-jti" not in self.trl._revoked_jtis
        assert "fresh-jti" in self.trl._revoked_jtis

    def test_size_property(self):
        self.trl.revoke_token("jti-1")
        self.trl.revoke_token("jti-2")
        self.trl.revoke_user_tokens("user-1")
        assert self.trl.size == 3

    def test_singleton_pattern(self):
        """get_revocation_list should return the same instance."""
        rl1 = get_revocation_list()
        rl2 = get_revocation_list()
        assert rl1 is rl2

    def test_constructor_returns_singleton(self):
        """Direct constructor should still resolve to singleton instance."""
        rl1 = TokenRevocationList()
        rl2 = TokenRevocationList()
        assert rl1 is rl2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Utility
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGetSecurityHeaders:
    def test_production_headers_complete(self):
        headers = get_security_headers("production")
        assert "Strict-Transport-Security" in headers
        assert "Content-Security-Policy" in headers
        assert "X-Frame-Options" in headers

    def test_development_no_hsts(self):
        headers = get_security_headers("development")
        assert "Strict-Transport-Security" not in headers
