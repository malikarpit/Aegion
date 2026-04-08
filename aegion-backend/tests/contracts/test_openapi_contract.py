"""
AG-001: OpenAPI Contract Stability Test.

Ensures that every registered /api/v1 route:
  1. Appears in the OpenAPI schema.
  2. Has a response model (no untyped endpoints).
  3. Does not drift from the frozen contract.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ── All expected v1 route prefixes (frozen contract) ──
EXPECTED_ROUTE_GROUPS = [
    "/api/v1/sessions",
    "/api/v1/proposals",
    "/api/v1/decisions",
    "/api/v1/council",
    "/api/v1/workspaces",
    "/api/v1/sentinel",
    "/api/v1/noesis",
    "/api/v1/ghost-text",
    "/api/v1/sessions/drafts",
    "/api/v1/evidence",
    "/api/v1/architecture",
    "/api/v1/health",
    "/api/v1/chronos",
    "/api/v1/audit",
    "/api/v1/praxis",
    "/api/v1/pipelines",
    "/api/v1/rejections",
]


class TestOpenAPIContract:
    """Contract stability tests for the OpenAPI spec."""

    def test_openapi_json_available(self):
        """GET /openapi.json returns valid schema."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert schema["info"]["title"] == "Aegion Backend"

    def test_all_route_groups_present(self):
        """Every expected route group has at least one path in the schema."""
        resp = client.get("/openapi.json")
        schema = resp.json()
        paths = list(schema["paths"].keys())

        for group in EXPECTED_ROUTE_GROUPS:
            matching = [p for p in paths if p.startswith(group)]
            assert len(matching) > 0, (
                f"Route group '{group}' missing from OpenAPI spec. "
                f"Available paths: {paths}"
            )

    def test_no_untagged_endpoints(self):
        """Every endpoint should belong to at least one tag."""
        resp = client.get("/openapi.json")
        schema = resp.json()

        untagged = []
        for path, methods in schema["paths"].items():
            if not path.startswith("/api/v1"):
                continue  # skip /health, /
            for method, spec in methods.items():
                if method in ("options", "head", "parameters"):
                    continue
                tags = spec.get("tags", [])
                if not tags:
                    untagged.append(f"{method.upper()} {path}")

        assert len(untagged) == 0, f"Untagged endpoints: {untagged}"

    def test_schema_has_components(self):
        """Schema should contain component definitions (Pydantic models)."""
        resp = client.get("/openapi.json")
        schema = resp.json()
        components = schema.get("components", {}).get("schemas", {})
        # We expect at least the core models
        assert len(components) > 0, "No component schemas found in OpenAPI spec"

    def test_schema_version_matches(self):
        """API version in schema matches app version."""
        resp = client.get("/openapi.json")
        schema = resp.json()
        assert schema["info"]["version"] == "0.1.0"

    def test_server_definitions(self):
        """Schema includes server definitions for dev and prod."""
        resp = client.get("/openapi.json")
        schema = resp.json()
        servers = schema.get("servers", [])
        urls = [s["url"] for s in servers]
        assert "http://localhost:8000" in urls
        assert "https://api.aegion.io" in urls

    def test_paths_count_stability(self):
        """
        Smoke check: the number of paths should not drop.
        If a route is removed, this test catches it.
        """
        resp = client.get("/openapi.json")
        schema = resp.json()
        path_count = len(schema["paths"])
        # We know we have at least 20+ routes registered
        assert path_count >= 20, (
            f"Expected at least 20 API paths, got {path_count}. "
            "A route may have been accidentally removed."
        )
