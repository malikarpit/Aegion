"""
Aegion Keycloak Adapter Module.

Phase 5: Enterprise SSO via Keycloak.
"""

from .auth_adapter import KeycloakAuthAdapter, KeycloakConfig, KeycloakUser, TokenInfo, create_keycloak_adapter

__all__ = [
    "KeycloakAuthAdapter",
    "KeycloakConfig",
    "KeycloakUser",
    "TokenInfo",
    "create_keycloak_adapter",
]
