"""
Aegion Data Protection: Operational Resilience.

Provides:
- Core dump prevention (sandbox + backend process)
- Log secret redaction at logger level
- Stack trace sanitizer (strips sensitive locals)
- Backup encryption key separation
"""

import os
import re
import resource
import traceback
from typing import Any, Dict, List, Optional, Pattern, Set


# ========== Core Dump Prevention ==========

def disable_core_dumps() -> bool:
    """
    Disable core dumps for the current process.

    Core dumps can contain sensitive data (keys, tokens, PII).
    Call at process startup.

    Returns True if successfully disabled.
    """
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        return True
    except (ValueError, resource.error):
        return False


def get_core_dump_status() -> Dict[str, Any]:
    """Check current core dump limits."""
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_CORE)
        return {
            "core_dumps_disabled": soft == 0 and hard == 0,
            "soft_limit": soft,
            "hard_limit": hard,
        }
    except (ValueError, resource.error):
        return {"core_dumps_disabled": False, "error": "Cannot read RLIMIT_CORE"}


# ========== Log Secret Redaction ==========

# Patterns that match secrets in log output
_SECRET_PATTERNS: List[tuple] = [
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)),
    ("api_key_value", re.compile(
        r"(?:api[_-]?key|apikey|secret|token|password|passwd|authorization)"
        r"\s*[=:]\s*['\"]?[A-Za-z0-9\-._~+/]{8,}",
        re.IGNORECASE,
    )),
    ("connection_string", re.compile(
        r"(?:redis|postgres|mysql|mongodb|neo4j)://[^\s]+",
        re.IGNORECASE,
    )),
    ("private_key_block", re.compile(
        r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----.*?-----END (?:RSA |EC |DSA )?PRIVATE KEY-----",
        re.DOTALL | re.IGNORECASE,
    )),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("hex_secret", re.compile(r"(?:secret|key|token)\s*[=:]\s*[0-9a-f]{32,}", re.IGNORECASE)),
]

# Sensitive local variable names to redact in stack traces
_SENSITIVE_LOCALS: Set[str] = {
    "password", "passwd", "secret", "token", "api_key",
    "private_key", "signing_key", "master_key", "encryption_key",
    "session_key", "auth_header", "cookie", "credentials",
}


def redact_log_secrets(text: str) -> str:
    """
    Redact secrets from log output.

    Scans for patterns matching API keys, tokens, connection strings,
    and other sensitive data, replacing them with [REDACTED].
    """
    result = text
    for name, pattern in _SECRET_PATTERNS:
        result = pattern.sub(f"[REDACTED:{name}]", result)
    return result


def sanitize_stack_trace(tb_text: str) -> str:
    """
    Sanitize a stack trace by redacting sensitive local variables.

    Strips values of variables named password, secret, token, etc.
    """
    lines = tb_text.split("\n")
    sanitized = []

    for line in lines:
        stripped = line.strip()
        # Check if line assigns a sensitive variable
        redacted = False
        for var_name in _SENSITIVE_LOCALS:
            if stripped.startswith(f"{var_name} =") or stripped.startswith(f"{var_name}="):
                sanitized.append(f"    {var_name} = [REDACTED]")
                redacted = True
                break
        if not redacted:
            sanitized.append(line)

    return "\n".join(sanitized)


def get_safe_locals(frame_locals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter sensitive variables from frame locals for safe logging.

    Returns a copy with sensitive values replaced.
    """
    safe = {}
    for key, value in frame_locals.items():
        if key.lower() in _SENSITIVE_LOCALS:
            safe[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 100:
            safe[key] = f"{value[:50]}...[truncated]"
        else:
            safe[key] = repr(value)
    return safe


# ========== Backup Key Separation ==========

class BackupKeyManager:
    """
    Manages backup encryption keys separately from application keys.

    Backup keys MUST NOT be the same as or derived from:
    - Application signing keys
    - Session keys
    - Per-workspace encryption keys

    This ensures a compromised app key doesn't expose backups.
    """

    def __init__(self, backup_key: Optional[bytes] = None):
        self._backup_key = backup_key or os.urandom(32)
        self._restore_log: List[Dict[str, str]] = []

    @property
    def key_fingerprint(self) -> str:
        """Short fingerprint of backup key (for audit, not the key itself)."""
        import hashlib
        return hashlib.sha256(self._backup_key).hexdigest()[:12]

    def log_restore(self, actor_id: str, backup_id: str, workspace_id: str) -> None:
        """Record a backup restoration event."""
        self._restore_log.append({
            "actor_id": actor_id,
            "backup_id": backup_id,
            "workspace_id": workspace_id,
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        })

    def get_restore_log(self) -> List[Dict[str, str]]:
        return list(self._restore_log)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "key_fingerprint": self.key_fingerprint,
            "total_restores": len(self._restore_log),
        }
