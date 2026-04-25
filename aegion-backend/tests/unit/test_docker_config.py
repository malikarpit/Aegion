"""
Tests for Docker Compose validation — Phase R6.

Validates the docker-compose.yml structure by parsing YAML and
checking that all services meet production requirements:
    - Valid YAML parsing
    - All services have healthchecks
    - Backend exposes port 8000
    - Backend depends on Redis
    - Named volumes defined
    - Restart policy set
"""

import pytest
import yaml
import os

COMPOSE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "docker-compose.yml"
)


@pytest.fixture
def compose_config():
    """Load and parse docker-compose.yml."""
    with open(COMPOSE_PATH, "r") as f:
        return yaml.safe_load(f)


class TestDockerComposeValidation:
    """Docker Compose structure validation."""

    def test_yaml_parses_without_error(self, compose_config):
        assert compose_config is not None
        assert "services" in compose_config

    def test_all_services_have_healthcheck(self, compose_config):
        services = compose_config["services"]
        # Services that MUST have healthchecks
        required_healthy = ["backend", "redis", "neo4j"]
        for name in required_healthy:
            if name in services:
                assert "healthcheck" in services[name], (
                    f"Service '{name}' missing healthcheck"
                )

    def test_backend_service_exposes_port_8000(self, compose_config):
        backend = compose_config["services"]["backend"]
        ports = backend.get("ports", [])
        port_strs = [str(p) for p in ports]
        assert any("8000" in p for p in port_strs), (
            f"Backend should expose port 8000, got: {ports}"
        )

    def test_backend_depends_on_redis(self, compose_config):
        backend = compose_config["services"]["backend"]
        deps = backend.get("depends_on", {})
        # deps can be a list or dict
        if isinstance(deps, dict):
            assert "redis" in deps
        elif isinstance(deps, list):
            assert "redis" in deps

    def test_volumes_defined(self, compose_config):
        assert "volumes" in compose_config
        volumes = compose_config["volumes"]
        assert len(volumes) >= 2, "Should have at least 2 named volumes"

    def test_restart_policy_set(self, compose_config):
        backend = compose_config["services"]["backend"]
        assert "restart" in backend, "Backend should have restart policy"
        assert backend["restart"] in ["always", "unless-stopped", "on-failure"]

    def test_redis_maxmemory_configured(self, compose_config):
        redis = compose_config["services"]["redis"]
        cmd = redis.get("command", "")
        assert "maxmemory" in str(cmd), "Redis should have maxmemory configured"

    def test_override_file_exists(self):
        override_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "docker-compose.override.yml"
        )
        assert os.path.isfile(override_path), "docker-compose.override.yml should exist"
