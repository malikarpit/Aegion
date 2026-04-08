"""
Forensic Readiness Tests.

Validates:
- Correlation ID generation and propagation
- UTC timestamp authority (ISO 8601, monotonic, NTP drift check)
- PII log redaction (email, IP, JWT, API key, credit card, SSN)
- Sensitive field redaction in dicts
- AuditEvent structured builder
"""

import pytest
import time
from datetime import timezone

from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.middleware.forensic_readiness import (
    CorrelationIDMiddleware,
    UTCTimestampAuthority,
    AuditEvent,
    correlation_id_var,
    get_correlation_id,
    redact_pii,
    redact_dict,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _echo(request: Request):
    return JSONResponse({"ok": True})


def _make_app():
    app = Starlette(routes=[Route("/", _echo)])
    app.add_middleware(CorrelationIDMiddleware)
    return app


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Correlation ID Middleware
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCorrelationID:
    def setup_method(self):
        self.client = TestClient(_make_app())

    def test_generates_correlation_id(self):
        """Response should include X-Correlation-ID when none provided."""
        resp = self.client.get("/")
        assert "X-Correlation-ID" in resp.headers
        cid = resp.headers["X-Correlation-ID"]
        assert len(cid) == 36  # UUIDv4 format

    def test_preserves_client_correlation_id(self):
        """Client-provided X-Correlation-ID should be preserved."""
        resp = self.client.get("/", headers={"X-Correlation-ID": "client-trace-123"})
        assert resp.headers["X-Correlation-ID"] == "client-trace-123"

    def test_unique_ids_per_request(self):
        """Each request should get a unique correlation ID."""
        resp1 = self.client.get("/")
        resp2 = self.client.get("/")
        assert resp1.headers["X-Correlation-ID"] != resp2.headers["X-Correlation-ID"]

    def test_get_correlation_id_generates_new(self):
        """get_correlation_id should return a UUID when no context."""
        # Reset context
        token = correlation_id_var.set(None)
        try:
            cid = get_correlation_id()
            assert len(cid) == 36
        finally:
            correlation_id_var.reset(token)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UTC Timestamp Authority
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestUTCTimestampAuthority:
    def test_now_is_utc(self):
        dt = UTCTimestampAuthority.now()
        assert dt.tzinfo == timezone.utc

    def test_now_iso_format(self):
        iso = UTCTimestampAuthority.now_iso()
        assert "T" in iso
        assert "+" in iso or "Z" in iso or "UTC" in iso

    def test_now_unix_reasonable(self):
        ts = UTCTimestampAuthority.now_unix()
        # Should be a reasonable timestamp (after 2024)
        assert ts > 1700000000

    def test_monotonic_increases(self):
        m1 = UTCTimestampAuthority.monotonic()
        time.sleep(0.001)
        m2 = UTCTimestampAuthority.monotonic()
        assert m2 > m1

    def test_elapsed_calculation(self):
        start = UTCTimestampAuthority.monotonic()
        time.sleep(0.01)
        elapsed = UTCTimestampAuthority.elapsed(start)
        assert elapsed >= 0.005  # At least some time passed

    def test_ntp_drift_check_returns_dict(self):
        result = UTCTimestampAuthority.check_ntp_drift()
        assert "drift_seconds" in result
        assert "drift_ok" in result
        assert "checked_at" in result

    def test_ntp_drift_within_bounds(self):
        """Under normal conditions, drift should be minimal."""
        result = UTCTimestampAuthority.check_ntp_drift()
        assert result["drift_ok"] is True

    def test_ntp_healthy(self):
        assert UTCTimestampAuthority.is_ntp_healthy() is True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PII Redaction
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPIIRedaction:
    def test_redact_email(self):
        result = redact_pii("User email is admin@aegion.io ok?")
        assert "[REDACTED:email]" in result
        assert "admin@aegion.io" not in result

    def test_redact_ip_address(self):
        result = redact_pii("Client IP: 192.168.1.100")
        assert "[REDACTED:ip_address]" in result
        assert "192.168.1.100" not in result

    def test_redact_jwt_token(self):
        fake_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = redact_pii(f"Token: {fake_jwt}")
        assert "[REDACTED:jwt_token]" in result
        assert "eyJhbG" not in result

    def test_redact_credit_card(self):
        result = redact_pii("Card: 4111-1111-1111-1111")
        assert "[REDACTED:credit_card]" in result
        assert "4111" not in result

    def test_redact_ssn(self):
        result = redact_pii("SSN: 123-45-6789")
        assert "[REDACTED:ssn]" in result
        assert "123-45-6789" not in result

    def test_no_false_positives_on_clean_text(self):
        clean = "This is a normal log message about graph nodes."
        result = redact_pii(clean)
        assert result == clean

    def test_multiple_pii_types_in_one_string(self):
        text = "User admin@test.com from 10.0.0.1 with SSN 111-22-3333"
        result = redact_pii(text)
        assert "admin@test.com" not in result
        assert "10.0.0.1" not in result
        assert "111-22-3333" not in result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dict Redaction
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDictRedaction:
    def test_sensitive_field_redacted(self):
        data = {"user": "alice", "password": "hunter2", "action": "login"}
        result = redact_dict(data)
        assert result["password"] == "[REDACTED]"
        assert result["user"] == "alice"

    def test_pii_in_string_values_redacted(self):
        data = {"message": "Authenticated admin@corp.com from 10.0.0.5"}
        result = redact_dict(data)
        assert "admin@corp.com" not in result["message"]
        assert "10.0.0.5" not in result["message"]

    def test_nested_dict_redacted(self):
        data = {"auth": {"token": "secret123", "user": "bob"}}
        result = redact_dict(data)
        assert result["auth"]["token"] == "[REDACTED]"
        assert result["auth"]["user"] == "bob"

    def test_non_string_values_preserved(self):
        data = {"count": 42, "active": True, "tags": ["a", "b"]}
        result = redact_dict(data)
        assert result["count"] == 42
        assert result["active"] is True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Audit Event
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAuditEvent:
    def test_event_has_required_fields(self):
        event = AuditEvent(
            action="PROPOSAL_CREATED",
            actor_id="user-123",
            resource_type="proposal",
            resource_id="prop-456",
        )
        d = event.to_dict()
        assert d["action"] == "PROPOSAL_CREATED"
        assert d["actor_id"] == "user-123"
        assert d["resource_type"] == "proposal"
        assert d["resource_id"] == "prop-456"
        assert d["outcome"] == "success"
        assert "correlation_id" in d
        assert "timestamp" in d

    def test_event_redacts_evidence(self):
        event = AuditEvent(
            action="LOGIN",
            actor_id="user-1",
            resource_type="session",
            resource_id="sess-1",
            evidence={"password": "secret", "ip": "10.0.0.1"},
        )
        d = event.to_dict()
        assert d["evidence"]["password"] == "[REDACTED]"

    def test_event_failure_outcome(self):
        event = AuditEvent(
            action="UNAUTHORIZED_ACCESS",
            actor_id="user-bad",
            resource_type="admin_panel",
            resource_id="panel-1",
            outcome="failure",
        )
        assert event.to_dict()["outcome"] == "failure"

    def test_event_emit_returns_dict(self):
        event = AuditEvent(
            action="TEST",
            actor_id="u1",
            resource_type="test",
            resource_id="t1",
        )
        result = event.emit()
        assert isinstance(result, dict)
        assert result["action"] == "TEST"
