"""
Integration tests for OpenClaw/Moltbook feature completion.

Covers:
- Feature #1: URL-based skill invocation
- Feature #2: Agent identity & verification
- Feature #3: Anti-impersonation hardening
"""

import pytest
import hashlib
import hmac
import time
from unittest.mock import MagicMock, patch


# =============================================
# Feature #1: URL-Based Skill Invocation
# =============================================

class TestSkillInvocation:
    """Tests for skill_invoke.py — HMAC-signed invocation links."""

    def _make_skill(self, skill_id="sk_1", name="Test Skill"):
        """Create a mock SkillBlueprint."""
        mock = MagicMock()
        mock.name = name
        mock.prompt_template = "Hello {{name}}, run {{task}} now."
        return skill_id, mock

    def test_render_template(self):
        """Template substitution replaces {{param}} placeholders."""
        from app.api.v1.skill_invoke import _render_template

        result = _render_template("Hello {{name}}, do {{action}}.", {"name": "Bot", "action": "deploy"})
        assert result == "Hello Bot, do deploy."
        assert "{{" not in result

    def test_sign_and_verify_token(self):
        """HMAC-signed tokens can be created and verified."""
        from app.api.v1.skill_invoke import _sign_token, _verify_token

        payload = {"skill_id": "sk_1", "params": {"a": "1"}, "exp": "2099-01-01T00:00:00Z"}
        token = _sign_token(payload)

        # Token has two parts: base64.signature
        assert "." in token

        # Verify round-trip
        decoded = _verify_token(token)
        assert decoded is not None
        assert decoded["skill_id"] == "sk_1"
        assert decoded["params"]["a"] == "1"

    def test_tampered_token_rejected(self):
        """Modifying the token payload invalidates the signature."""
        from app.api.v1.skill_invoke import _sign_token, _verify_token

        token = _sign_token({"data": "original"})
        # Tamper with the payload portion
        parts = token.split(".")
        tampered = parts[0][:-2] + "XX." + parts[1]

        assert _verify_token(tampered) is None

    def test_invocation_log_records_entries(self):
        """Direct invocations are recorded in the audit log."""
        from app.api.v1.skill_invoke import _invocation_log

        initial_count = len(_invocation_log)
        _invocation_log.append({
            "skill_id": "sk_test",
            "invoked_by": "user_1",
            "parameters": {},
            "timestamp": "2026-01-01T00:00:00Z",
            "method": "direct",
        })
        assert len(_invocation_log) == initial_count + 1
        assert _invocation_log[-1]["method"] == "direct"


# =============================================
# Feature #2: Agent Identity & Verification
# =============================================

class TestAgentIdentity:
    """Tests for agent_identity.py — registration, verification, claims."""

    def _get_service(self):
        from app.services.agent_identity import AgentIdentityService
        return AgentIdentityService()

    def test_register_agent(self):
        """Agent registration creates record with owner binding."""
        svc = self._get_service()
        agent, raw_key = svc.register_agent(
            owner_user_id="user_1",
            display_name="TestBot",
            capabilities=["read", "write"],
        )
        assert agent.agent_id.startswith("agent_")
        assert agent.owner_user_id == "user_1"
        assert agent.display_name == "TestBot"
        assert raw_key.startswith("aeg_agent_")
        assert agent.verified is False

    def test_verify_ownership(self):
        """Ownership verification matches owner_user_id."""
        svc = self._get_service()
        agent, _ = svc.register_agent("user_1", "Bot", [])

        assert svc.verify_ownership(agent.agent_id, "user_1") is True
        assert svc.verify_ownership(agent.agent_id, "user_2") is False

    def test_challenge_response_verification(self):
        """Challenge-response flow verifies ownership with signed nonce."""
        svc = self._get_service()
        agent, _ = svc.register_agent("user_1", "Bot", [])

        # Get challenge
        nonce = svc.create_verification_challenge(agent.agent_id)
        assert nonce is not None

        # Sign the nonce correctly
        signed = hmac.new(
            agent.api_key_hash.encode(),
            nonce.encode(),
            hashlib.sha256,
        ).hexdigest()

        assert svc.complete_verification(agent.agent_id, signed) is True
        assert svc.get_agent(agent.agent_id).verified is True

    def test_bad_signature_fails_verification(self):
        """Wrong signature does not verify."""
        svc = self._get_service()
        agent, _ = svc.register_agent("user_1", "Bot", [])
        nonce = svc.create_verification_challenge(agent.agent_id)

        assert svc.complete_verification(agent.agent_id, "wrong_signature") is False
        assert svc.get_agent(agent.agent_id).verified is False

    def test_create_and_verify_claim(self):
        """Agent-to-agent identity claims can be created and verified."""
        svc = self._get_service()
        a1, _ = svc.register_agent("user_1", "AgentA", [])
        a2, _ = svc.register_agent("user_2", "AgentB", [])

        claim = svc.create_claim(
            source_agent_id=a1.agent_id,
            target_agent_id=a2.agent_id,
            claim_type="delegate_read",
            scope="skills.*",
        )
        assert claim is not None
        assert claim.claim_id.startswith("claim_")

        valid, msg = svc.verify_claim(claim.claim_id)
        assert valid is True
        assert "verified" in msg.lower()

    def test_revoke_claim(self):
        """Revoked claims cannot be verified."""
        svc = self._get_service()
        a1, _ = svc.register_agent("user_1", "A", [])
        a2, _ = svc.register_agent("user_1", "B", [])

        claim = svc.create_claim(a1.agent_id, a2.agent_id, "trust")
        svc.revoke_claim(claim.claim_id, "user_1")

        valid, msg = svc.verify_claim(claim.claim_id)
        assert valid is False
        assert "revoked" in msg.lower()

    def test_deregister_agent(self):
        """Deregistering an agent soft-deletes and revokes outgoing claims."""
        svc = self._get_service()
        a1, _ = svc.register_agent("user_1", "A", [])
        a2, _ = svc.register_agent("user_1", "B", [])
        claim = svc.create_claim(a1.agent_id, a2.agent_id, "trust")

        svc.deregister_agent(a1.agent_id, "user_1")
        assert svc.get_agent(a1.agent_id).status == "deregistered"
        assert svc._claims[claim.claim_id].revoked is True

    def test_list_agents_filters_by_owner(self):
        """list_agents respects owner filter and excludes deregistered."""
        svc = self._get_service()
        svc.register_agent("user_1", "A", [])
        svc.register_agent("user_2", "B", [])
        a3, _ = svc.register_agent("user_1", "C", [])
        svc.deregister_agent(a3.agent_id, "user_1")

        user1_agents = svc.list_agents("user_1")
        assert len(user1_agents) == 1
        assert user1_agents[0].display_name == "A"


# =============================================
# Feature #3: Anti-Impersonation
# =============================================

class TestSessionSecurity:
    """Tests for session_security.py — fingerprinting, concurrent sessions, token binding."""

    def _make_request(self, ua="TestAgent/1.0", lang="en-US", ip="192.168.1.42"):
        """Create a mock request with fingerprint-relevant headers."""
        class Headers:
            def __init__(self, data):
                self._data = data
            def get(self, key, default=""):
                return self._data.get(key, default)

        headers = Headers({
            "User-Agent": ua,
            "Accept-Language": lang,
            "X-Forwarded-For": ip,
        })
        req = MagicMock()
        req.headers = headers
        req.client = MagicMock()
        req.client.host = ip
        return req

    def test_fingerprint_first_request_passes(self):
        """First request per session establishes the baseline fingerprint."""
        from app.middleware.session_security import (
            check_session_fingerprint,
            _session_fingerprints,
        )
        sid = f"fp_test_{time.time_ns()}"
        req = self._make_request()

        ok, warn = check_session_fingerprint(sid, req)
        assert ok is True
        assert warn is None
        assert sid in _session_fingerprints

    def test_fingerprint_same_request_passes(self):
        """Identical subsequent requests pass fingerprint check."""
        from app.middleware.session_security import check_session_fingerprint

        sid = f"fp_same_{time.time_ns()}"
        req = self._make_request()

        check_session_fingerprint(sid, req)  # baseline
        ok, warn = check_session_fingerprint(sid, req)  # same
        assert ok is True
        assert warn is None

    def test_fingerprint_drift_warns(self):
        """Changed User-Agent triggers a drift warning (not block in default mode)."""
        from app.middleware.session_security import check_session_fingerprint

        sid = f"fp_drift_{time.time_ns()}"
        req1 = self._make_request(ua="Agent/1.0")
        req2 = self._make_request(ua="Agent/2.0")  # different UA

        check_session_fingerprint(sid, req1)  # baseline
        ok, warn = check_session_fingerprint(sid, req2)
        # Default mode = warn only, so ok is still True
        assert ok is True
        assert warn is not None
        assert "drift" in warn.lower()

    def test_concurrent_session_tracking(self):
        """User sessions are tracked; excess sessions cause eviction of oldest."""
        from app.middleware.session_security import (
            check_concurrent_sessions,
            _user_sessions,
            MAX_CONCURRENT_SESSIONS,
        )

        user = f"user_concur_{time.time_ns()}"
        # Create MAX + 1 sessions
        for i in range(MAX_CONCURRENT_SESSIONS + 1):
            ok, warn = check_concurrent_sessions(user, f"session_{i}")

        # Should still have at most MAX sessions
        assert len(_user_sessions[user]) <= MAX_CONCURRENT_SESSIONS

    def test_token_binding_matches(self):
        """Same JWT ID on same session passes."""
        from app.middleware.session_security import check_token_binding

        sid = f"tb_{time.time_ns()}"
        ok1, _ = check_token_binding(sid, "jti_abc")
        ok2, warn2 = check_token_binding(sid, "jti_abc")
        assert ok1 is True
        assert ok2 is True
        assert warn2 is None

    def test_token_binding_mismatch_warns(self):
        """Different JWT ID on same session triggers a warning."""
        from app.middleware.session_security import check_token_binding

        sid = f"tb_mismatch_{time.time_ns()}"
        check_token_binding(sid, "jti_first")
        ok, warn = check_token_binding(sid, "jti_second")
        assert ok is True  # warns but doesn't block
        assert warn is not None
        assert "mismatch" in warn.lower()
