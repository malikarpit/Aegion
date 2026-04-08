"""
Zero-Trust Network Tests.

Validates:
- mTLS config defaults
- SPIFFE service identity validation
- Network policy (allow-list only)
- Egress deny-by-default
"""

import pytest
from app.services.zero_trust_network import (
    ZeroTrustNetworkPolicy,
    ServiceID,
    TLSConfig,
)


class TestMTLSConfig:
    def test_redis_tls_enabled(self):
        policy = ZeroTrustNetworkPolicy()
        cfg = policy.get_tls_config("redis")
        assert cfg is not None
        assert cfg.enabled is True
        assert cfg.min_version == "TLSv1.3"
        assert cfg.require_client_cert is True

    def test_neo4j_tls_enabled(self):
        policy = ZeroTrustNetworkPolicy()
        cfg = policy.get_tls_config("neo4j")
        assert cfg is not None
        assert cfg.verify_hostname is True

    def test_unknown_service_returns_none(self):
        policy = ZeroTrustNetworkPolicy()
        assert policy.get_tls_config("unknown") is None


class TestServiceIdentity:
    def test_valid_spiffe_ids(self):
        policy = ZeroTrustNetworkPolicy()
        assert policy.validate_service_identity(ServiceID.BACKEND.value) is True
        assert policy.validate_service_identity(ServiceID.SANDBOX_AGENT.value) is True

    def test_invalid_spiffe_id(self):
        policy = ZeroTrustNetworkPolicy()
        assert policy.validate_service_identity("spiffe://evil.io/attacker") is False


class TestNetworkPolicy:
    def setup_method(self):
        self.policy = ZeroTrustNetworkPolicy()

    def test_nginx_to_backend_allowed(self):
        assert self.policy.is_connection_allowed("nginx", "backend", 8000) is True

    def test_backend_to_redis_allowed(self):
        assert self.policy.is_connection_allowed("backend", "redis", 6380) is True

    def test_backend_to_neo4j_allowed(self):
        assert self.policy.is_connection_allowed("backend", "neo4j", 7687) is True

    def test_lateral_movement_denied(self):
        assert self.policy.is_connection_allowed("redis", "neo4j", 7687) is False

    def test_external_to_backend_denied(self):
        assert self.policy.is_connection_allowed("external", "backend", 8000) is False

    def test_wrong_port_denied(self):
        assert self.policy.is_connection_allowed("nginx", "backend", 9999) is False


class TestEgressPolicy:
    def setup_method(self):
        self.policy = ZeroTrustNetworkPolicy()

    def test_ai_api_allowed(self):
        assert self.policy.is_egress_allowed("api.openai.com", 443) is True

    def test_unknown_destination_denied(self):
        assert self.policy.is_egress_allowed("evil.com", 443) is False

    def test_dns_allowed(self):
        assert self.policy.is_egress_allowed("dns", 53) is True

    def test_stats(self):
        stats = self.policy.stats
        assert stats["tls_configs"] >= 2
        assert stats["network_rules"] >= 4
