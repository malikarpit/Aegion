"""
Aegion Session Security Middleware.

Anti-impersonation hardening:
- Session fingerprinting (User-Agent + Accept-Language + IP subnet)
- Concurrent session detection (per-user limit)
- Token binding (JWT ID → session binding)

Feature: Anti-impersonation beyond token validation.
"""

import hashlib
from typing import Optional, Dict, List, Set
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import Request
from starlette.responses import JSONResponse

from ..core.logging import logger
from ..core.time import TimeAuthority


# ========== Configuration ==========

# When True, fingerprint drift causes 403; when False, only warns
STRICT_FINGERPRINT = False
MAX_CONCURRENT_SESSIONS = 3
MAX_DRIFT_COMPONENTS = 1  # Allow 1 component to change (e.g. IP roaming)


# ========== In-Memory Stores ==========

# session_id -> fingerprint hash
_session_fingerprints: Dict[str, str] = {}

# session_id -> component dict (for drift analysis)
_session_components: Dict[str, Dict[str, str]] = {}

# user_id -> set of active session_ids
_user_sessions: Dict[str, Set[str]] = defaultdict(set)

# session_id -> bound JWT ID (jti)
_session_token_bindings: Dict[str, str] = {}

# Security event log
_security_events: List[dict] = []


# ========== Fingerprinting ==========

def _extract_fingerprint_components(request: Request) -> Dict[str, str]:
    """Extract fingerprint components from the request."""
    # User-Agent
    ua = request.headers.get("User-Agent", "unknown")

    # Accept-Language
    lang = request.headers.get("Accept-Language", "unknown")

    # IP subnet (/24 for IPv4)
    ip = "unknown"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    elif request.client:
        ip = request.client.host

    # Mask to /24 subnet
    parts = ip.split(".")
    if len(parts) == 4:
        ip_subnet = ".".join(parts[:3]) + ".0/24"
    else:
        ip_subnet = ip  # IPv6 or unknown — use as-is

    return {
        "user_agent": ua,
        "accept_language": lang,
        "ip_subnet": ip_subnet,
    }


def _hash_components(components: Dict[str, str]) -> str:
    """Hash fingerprint components into a single string."""
    canonical = "|".join(f"{k}={v}" for k, v in sorted(components.items()))
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


def _count_drift(old: Dict[str, str], new: Dict[str, str]) -> int:
    """Count how many fingerprint components changed."""
    return sum(1 for k in old if old.get(k) != new.get(k))


def _log_event(event_type: str, **kwargs):
    """Record a security event."""
    entry = {
        "type": event_type,
        "timestamp": TimeAuthority.now(),
        **kwargs,
    }
    _security_events.append(entry)
    # Trim to last 1000 events
    if len(_security_events) > 1000:
        _security_events[:] = _security_events[-1000:]


# ========== Core Checks ==========

def check_session_fingerprint(
    session_id: str,
    request: Request,
) -> tuple[bool, Optional[str]]:
    """
    Check session fingerprint for drift.

    Returns:
        (is_ok, warning_message)
        - is_ok is False only when STRICT_FINGERPRINT is True and drift exceeds threshold.
    """
    components = _extract_fingerprint_components(request)
    fp_hash = _hash_components(components)

    if session_id not in _session_fingerprints:
        # First request — record baseline
        _session_fingerprints[session_id] = fp_hash
        _session_components[session_id] = components
        return True, None

    # Compare
    if _session_fingerprints[session_id] == fp_hash:
        return True, None

    # Drift detected — analyze which components changed
    old_components = _session_components[session_id]
    drift_count = _count_drift(old_components, components)
    changed = [k for k in old_components if old_components.get(k) != components.get(k)]

    warning = (
        f"Session fingerprint drift: {drift_count} component(s) changed "
        f"({', '.join(changed)}) for session {session_id}"
    )

    logger.warning(warning)
    _log_event(
        "fingerprint_drift",
        session_id=session_id,
        drift_count=drift_count,
        changed_components=changed,
    )

    if drift_count > MAX_DRIFT_COMPONENTS and STRICT_FINGERPRINT:
        return False, warning

    return True, warning


def check_concurrent_sessions(
    user_id: str,
    session_id: str,
) -> tuple[bool, Optional[str]]:
    """
    Enforce concurrent session limit.

    Returns:
        (is_ok, warning_message)
    """
    sessions = _user_sessions[user_id]
    sessions.add(session_id)

    if len(sessions) <= MAX_CONCURRENT_SESSIONS:
        return True, None

    # Too many sessions — log and optionally reject
    warning = (
        f"User {user_id} has {len(sessions)} concurrent sessions "
        f"(limit: {MAX_CONCURRENT_SESSIONS})"
    )
    logger.warning(warning)
    _log_event(
        "concurrent_session_limit",
        user_id=user_id,
        session_count=len(sessions),
        sessions=list(sessions),
    )

    # Evict the oldest (first added) — we keep the newest MAX sessions
    excess = list(sessions)[:-MAX_CONCURRENT_SESSIONS]
    for old_sid in excess:
        sessions.discard(old_sid)
        _session_fingerprints.pop(old_sid, None)
        _session_components.pop(old_sid, None)
        _session_token_bindings.pop(old_sid, None)

    return True, warning


def check_token_binding(
    session_id: str,
    jwt_id: Optional[str],
) -> tuple[bool, Optional[str]]:
    """
    Bind JWT ID to session. Flag if a different JWT appears on the same session.

    Returns:
        (is_ok, warning_message)
    """
    if not jwt_id:
        return True, None

    if session_id not in _session_token_bindings:
        _session_token_bindings[session_id] = jwt_id
        return True, None

    if _session_token_bindings[session_id] == jwt_id:
        return True, None

    # Different JWT on same session — suspicious
    warning = (
        f"Token binding mismatch: session {session_id} was bound to "
        f"JWT {_session_token_bindings[session_id]}, now sees {jwt_id}"
    )
    logger.warning(warning)
    _log_event(
        "token_binding_mismatch",
        session_id=session_id,
        expected_jti=_session_token_bindings[session_id],
        actual_jti=jwt_id,
    )

    # Update binding (token refresh is legitimate)
    _session_token_bindings[session_id] = jwt_id

    return True, warning


def release_session(session_id: str, user_id: Optional[str] = None):
    """Clean up session tracking when a session ends."""
    _session_fingerprints.pop(session_id, None)
    _session_components.pop(session_id, None)
    _session_token_bindings.pop(session_id, None)
    if user_id and user_id in _user_sessions:
        _user_sessions[user_id].discard(session_id)


def get_security_events(limit: int = 50) -> List[dict]:
    """Get recent security events."""
    return _security_events[-limit:]
