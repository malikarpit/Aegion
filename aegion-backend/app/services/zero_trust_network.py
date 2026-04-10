"""
Aegion Zero-Trust Network Model: Operational Resilience.

Provides:
- mTLS configuration for Redis and Neo4j connections
- Network policy definitions (Kubernetes)
- SPIFFE service identity management
- Host-level egress control policy
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone


class ServiceID(str, Enum):
    """SPIFFE-style service identifiers."""
    BACKEND = "spiffe://aegion.io/backend"
    SANDBOX_AGENT = "spiffe://aegion.io/sandbox-agent"
    REDIS = "spiffe://aegion.io/redis"
    NEO4J = "spiffe://aegion.io/neo4j"
    NGINX = "spiffe://aegion.io/nginx"


@dataclass
class TLSConfig:
    """mTLS configuration for a service connection."""
    service: str
    enabled: bool = True
    min_version: str = "TLSv1.3"
    cert_path: Optional[str] = None
    key_path: Optional[str] = None
    ca_path: Optional[str] = None
    verify_hostname: bool = True
    require_client_cert: bool = True  # mTLS


@dataclass
class NetworkRule:
    """Network policy rule (Kubernetes-style)."""
    name: str
    source: str
    destination: str
    port: int
    protocol: str = "TCP"
    action: str = "ALLOW"


@dataclass
class EgressRule:
    """Host-level egress control rule."""
    destination: str
    port: int
    purpose: str
    allowed: bool = True


class ZeroTrustNetworkPolicy:
    """
    Zero-trust network configuration and policy enforcement.

    Principles:
    - No default trust between services
    - All inter-service communication requires mTLS
    - Explicit allow-list for network paths
    - No default internet egress
    """

    def __init__(self):
        self._tls_configs: Dict[str, TLSConfig] = {}
        self._network_rules: List[NetworkRule] = []
        self._egress_rules: List[EgressRule] = []
        self._initialize_defaults()

    def _initialize_defaults(self):
        """Set up default zero-trust policies."""
        # mTLS configs for all service connections
        self._tls_configs["redis"] = TLSConfig(
            service="redis",
            cert_path="/certs/backend.crt",
            key_path="/certs/backend.key",
            ca_path="/certs/ca.crt",
        )
        self._tls_configs["neo4j"] = TLSConfig(
            service="neo4j",
            cert_path="/certs/backend.crt",
            key_path="/certs/backend.key",
            ca_path="/certs/ca.crt",
        )

        # Network rules (allow-list only)
        self._network_rules = [
            NetworkRule("nginx-to-backend", "nginx", "backend", 8000),
            NetworkRule("backend-to-redis", "backend", "redis", 6380),
            NetworkRule("backend-to-neo4j", "backend", "neo4j", 7687),
            NetworkRule("backend-to-sandbox", "backend", "sandbox-agent", 50051, "TCP"),
        ]

        # Egress rules (deny-by-default, explicit allow)
        self._egress_rules = [
            EgressRule("api.openai.com", 443, "AI model API"),
            EgressRule("api.anthropic.com", 443, "AI model API"),
            EgressRule("pypi.org", 443, "Package registry"),
            EgressRule("dns", 53, "DNS resolution", allowed=True),
        ]

    def get_tls_config(self, service: str) -> Optional[TLSConfig]:
        return self._tls_configs.get(service)

    def is_connection_allowed(self, source: str, destination: str, port: int) -> bool:
        """Check if a network connection is allowed by policy."""
        for rule in self._network_rules:
            if (rule.source == source and
                rule.destination == destination and
                rule.port == port and
                rule.action == "ALLOW"):
                return True
        return False

    def is_egress_allowed(self, destination: str, port: int) -> bool:
        """Check if outbound traffic is allowed."""
        for rule in self._egress_rules:
            if rule.destination == destination and rule.port == port:
                return rule.allowed
        return False  # Deny by default

    def get_network_rules(self) -> List[NetworkRule]:
        return list(self._network_rules)

    def get_egress_rules(self) -> List[EgressRule]:
        return list(self._egress_rules)

    def validate_service_identity(self, claimed_id: str) -> bool:
        """Validate a SPIFFE service identity."""
        valid_ids = {s.value for s in ServiceID}
        return claimed_id in valid_ids

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "tls_configs": len(self._tls_configs),
            "network_rules": len(self._network_rules),
            "egress_rules": len(self._egress_rules),
        }
