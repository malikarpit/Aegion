"""
Data Protection Tests.

Validates:
- Core dump prevention
- Log secret redaction (bearer, API key, connection string, private key, AWS)
- Stack trace sanitization
- Safe locals filtering
- Backup key separation and restore logging
"""

import pytest
from app.services.data_protection import (
    disable_core_dumps,
    get_core_dump_status,
    redact_log_secrets,
    sanitize_stack_trace,
    get_safe_locals,
    BackupKeyManager,
)


class TestCoreDumps:
    def test_disable_core_dumps(self):
        result = disable_core_dumps()
        assert result is True

    def test_status_after_disable(self):
        disable_core_dumps()
        status = get_core_dump_status()
        assert status["core_dumps_disabled"] is True
        assert status["soft_limit"] == 0


class TestLogRedaction:
    def test_redact_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig"
        result = redact_log_secrets(text)
        assert "eyJ" not in result
        assert "[REDACTED:" in result

    def test_redact_api_key(self):
        text = "api_key=sk-abcdef1234567890"
        result = redact_log_secrets(text)
        assert "sk-abcdef" not in result

    def test_redact_connection_string(self):
        text = "Connecting to redis://user:pass@localhost:6379/0"
        result = redact_log_secrets(text)
        assert "user:pass" not in result

    def test_redact_aws_key(self):
        text = "Using key AKIAIOSFODNN7EXAMPLE"
        result = redact_log_secrets(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_safe_text_unchanged(self):
        text = "Processing 42 graph nodes successfully"
        result = redact_log_secrets(text)
        assert result == text

    def test_multiple_secrets_redacted(self):
        text = "token=abc123secret Bearer eyXYZ apikey:hunter2long"
        result = redact_log_secrets(text)
        assert "abc123" not in result
        assert "eyXYZ" not in result


class TestStackTraceSanitization:
    def test_password_redacted(self):
        tb = "    password = 's3cret!'\n    username = 'admin'"
        result = sanitize_stack_trace(tb)
        assert "s3cret" not in result
        assert "REDACTED" in result
        assert "admin" in result

    def test_secret_redacted(self):
        tb = "    secret = b'my-signing-key'"
        result = sanitize_stack_trace(tb)
        assert "my-signing-key" not in result

    def test_non_sensitive_preserved(self):
        tb = "    count = 42\n    name = 'test'"
        result = sanitize_stack_trace(tb)
        assert "42" in result
        assert "test" in result


class TestSafeLocals:
    def test_sensitive_var_redacted(self):
        frame = {"password": "hunter2", "count": 5}
        safe = get_safe_locals(frame)
        assert safe["password"] == "[REDACTED]"
        assert "5" in safe["count"]

    def test_long_string_truncated(self):
        frame = {"data": "x" * 200}
        safe = get_safe_locals(frame)
        assert "truncated" in safe["data"]

    def test_token_redacted(self):
        frame = {"token": "eyJhbGciOiJ...", "status": "ok"}
        safe = get_safe_locals(frame)
        assert safe["token"] == "[REDACTED]"
        assert "ok" in safe["status"]


class TestBackupKeyManager:
    def test_unique_fingerprint(self):
        mgr1 = BackupKeyManager()
        mgr2 = BackupKeyManager()
        assert mgr1.key_fingerprint != mgr2.key_fingerprint

    def test_restore_logging(self):
        mgr = BackupKeyManager()
        mgr.log_restore("admin-1", "backup-20240101", "ws-1")
        log = mgr.get_restore_log()
        assert len(log) == 1
        assert log[0]["actor_id"] == "admin-1"
        assert log[0]["workspace_id"] == "ws-1"

    def test_stats(self):
        mgr = BackupKeyManager()
        mgr.log_restore("u1", "b1", "ws-1")
        mgr.log_restore("u2", "b2", "ws-2")
        assert mgr.stats["total_restores"] == 2
