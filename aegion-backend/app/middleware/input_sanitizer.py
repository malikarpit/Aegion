"""
Input Sanitizer — Defense-in-depth input validation for all API endpoints.

Defence layers:
    1. Length limits   — reject absurdly long payloads before processing
    2. Unicode control — strip invisible/RTL-override characters (CVE-2021-42574)
    3. Prompt injection — detect known injection attack patterns
    4. Path traversal  — neutralize ../ and null bytes
    5. SQL injection   — detect SQL meta-characters in non-query fields
    6. XSS patterns    — strip script/event handler injections
    7. JSON depth      — reject deeply nested payloads (DoS vector)

Usage:
    from app.middleware.input_sanitizer import sanitize_input, validate_payload_size

    clean = sanitize_input(user_text)     # Strips dangerous patterns
    validate_payload_size(body, 1_000_000) # Raises if > 1MB

References:
    - OWASP Input Validation Cheat Sheet (2024 edition)
    - CVE-2021-42574 (Trojan Source / Bidi attack)
    - Greshake et al. "Prompt Injection Attacks" (2023)
    - NIST SP 800-53 SI-10 (Information Input Validation)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

# Maximum input lengths per field type
MAX_QUERY_LENGTH = 50_000          # 50KB for council queries
MAX_NAME_LENGTH = 256              # Workspace names, rule IDs, etc.
MAX_DESCRIPTION_LENGTH = 5_000    # Descriptions, comments
MAX_API_KEY_LENGTH = 512           # API keys
MAX_PATH_LENGTH = 1_024            # File paths
MAX_JSON_DEPTH = 20                # Maximum nesting depth for JSON payloads
MAX_PAYLOAD_BYTES = 5_000_000      # 5MB absolute maximum

# Unicode control characters to strip (except \n, \r, \t)
# Includes zero-width joiners, Bidi overrides (Trojan Source CVE-2021-42574)
_DANGEROUS_UNICODE = re.compile(
    r'[\u200b-\u200f'    # Zero-width space, LTR/RTL mark
    r'\u202a-\u202e'     # LTR/RTL embedding/override (Trojan Source)
    r'\u2066-\u2069'     # Isolate controls
    r'\u00ad'            # Soft hyphen
    r'\ufeff'            # BOM
    r'\ufff9-\ufffc'     # Annotation chars
    r'\x00-\x08'         # Control chars (except \t=0x09)
    r'\x0b\x0c'          # VT, FF
    r'\x0e-\x1f]',       # Remaining control chars
    re.UNICODE,
)

# Prompt injection patterns (Greshake et al. 2023)
_PROMPT_INJECTION_PATTERNS = [
    # Direct instruction override
    r'(?:ignore|forget|disregard)\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|prompts?|rules?)',
    # System prompt extraction
    r'(?:reveal|show|print|output|display)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions?)',
    # Role-play as unrestricted AI
    r'(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+(?:an?\s+)?(?:unrestricted|unfiltered|evil|jailbroken)',
    # DAN-type jailbreaks
    r'(?:do\s+anything\s+now|DAN\s+mode|developer\s+mode\s+enabled)',
]
_PROMPT_INJECTION_RE = re.compile(
    '|'.join(_PROMPT_INJECTION_PATTERNS),
    re.IGNORECASE | re.DOTALL,
)

# Path traversal patterns
_PATH_TRAVERSAL_RE = re.compile(
    r'(?:\.\.[\\/])'          # ../  or ..\
    r'|(?:%2e%2e[\\/])'      # URL-encoded ../
    r'|(?:\x00)',             # Null byte injection
    re.IGNORECASE,
)

# SQL injection meta-characters (for non-query fields like names, IDs)
_SQL_INJECTION_RE = re.compile(
    r"(?:'\s*(?:OR|AND)\s+\d+\s*=\s*\d+)"              # ' OR 1=1
    r"|(?:;\s*(?:DROP|ALTER|DELETE|UPDATE|INSERT)\s+)"   # ; DROP TABLE
    r"|(?:UNION\s+(?:ALL\s+)?SELECT\s+)",               # UNION SELECT
    re.IGNORECASE,
)

# XSS patterns
_XSS_RE = re.compile(
    r'<\s*script[^>]*>'                 # <script>
    r'|javascript\s*:'                  # javascript:
    r'|on(?:error|load|click|mouseover)\s*=',  # event handlers
    re.IGNORECASE,
)


# ──────────────────────────────────────────────────────────────────────────────
# Input Sanitization
# ──────────────────────────────────────────────────────────────────────────────

class SanitizationResult:
    """Result of input sanitization with details about what was cleaned."""

    __slots__ = ("clean_text", "warnings", "was_modified")

    def __init__(self, clean_text: str, warnings: List[str], was_modified: bool):
        self.clean_text = clean_text
        self.warnings = warnings
        self.was_modified = was_modified


def sanitize_input(
    text: str,
    max_length: int = MAX_QUERY_LENGTH,
    allow_html: bool = False,
    field_name: str = "input",
) -> SanitizationResult:
    """
    Apply all sanitization layers to user input.

    Args:
        text: Raw user input
        max_length: Maximum allowed length
        allow_html: If False, strip XSS patterns
        field_name: For diagnostic messages

    Returns:
        SanitizationResult with cleaned text and warnings
    """
    warnings: List[str] = []
    modified = False
    clean = text

    # Layer 1: Length limit
    if len(clean) > max_length:
        clean = clean[:max_length]
        warnings.append(f"{field_name}: truncated from {len(text)} to {max_length} chars")
        modified = True

    # Layer 2: Dangerous unicode removal
    cleaned_unicode = _DANGEROUS_UNICODE.sub('', clean)
    if cleaned_unicode != clean:
        warnings.append(f"{field_name}: stripped dangerous unicode control characters")
        clean = cleaned_unicode
        modified = True

    # Layer 3: XSS stripping (if HTML not allowed)
    if not allow_html:
        cleaned_xss = _XSS_RE.sub('[REMOVED]', clean)
        if cleaned_xss != clean:
            warnings.append(f"{field_name}: stripped XSS patterns")
            clean = cleaned_xss
            modified = True

    return SanitizationResult(
        clean_text=clean,
        warnings=warnings,
        was_modified=modified,
    )


def detect_prompt_injection(text: str) -> Optional[str]:
    """
    Detect prompt injection attempts.

    Returns the matched pattern string if injection detected, None otherwise.
    This does NOT block — it's up to the caller to decide the response.
    """
    match = _PROMPT_INJECTION_RE.search(text)
    if match:
        return match.group(0)
    return None


def detect_path_traversal(path: str) -> bool:
    """Check if a path contains traversal attacks."""
    return bool(_PATH_TRAVERSAL_RE.search(path))


def detect_sql_injection(value: str) -> bool:
    """
    Check if a non-query field contains SQL injection patterns.

    Note: This is NOT for user queries (which are just text sent to LLMs).
    This is for structured fields like workspace names, rule IDs, etc.
    """
    return bool(_SQL_INJECTION_RE.search(value))


def validate_payload_size(body: bytes, max_bytes: int = MAX_PAYLOAD_BYTES) -> None:
    """
    Validate that a request payload doesn't exceed size limits.

    Raises:
        ValueError: if payload exceeds max_bytes
    """
    if len(body) > max_bytes:
        raise ValueError(
            f"Payload size {len(body)} bytes exceeds maximum {max_bytes} bytes"
        )


def validate_json_depth(obj: Any, max_depth: int = MAX_JSON_DEPTH, _current: int = 0) -> bool:
    """
    Check that a parsed JSON object doesn't exceed maximum nesting depth.

    Deeply nested JSON is a DoS vector — exponential parsing time.

    Returns True if valid, False if too deep.
    """
    if _current > max_depth:
        return False

    if isinstance(obj, dict):
        return all(
            validate_json_depth(v, max_depth, _current + 1)
            for v in obj.values()
        )
    elif isinstance(obj, list):
        return all(
            validate_json_depth(item, max_depth, _current + 1)
            for item in obj
        )

    return True


def sanitize_workspace_name(name: str) -> str:
    """
    Sanitize a workspace name — allow only alphanumeric, hyphens, underscores.
    """
    # Strip dangerous chars, limit length
    clean = re.sub(r'[^a-zA-Z0-9_\-\s]', '', name)
    return clean[:MAX_NAME_LENGTH].strip()
