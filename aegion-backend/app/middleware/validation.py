"""
Aegion Input Validation Utilities.

Centralized validation for common input patterns.
Prevents injection attacks and ensures data integrity.
"""

import re
from typing import Optional, List, Any
from pydantic import BaseModel, field_validator, ConfigDict
from fastapi import HTTPException, status


# ========== Validation Patterns ==========

# Safe ID pattern: alphanumeric with hyphens and underscores
SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,128}$')

# UUID pattern
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)

# Email pattern (simplified but effective)
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

# Path traversal prevention
PATH_TRAVERSAL_PATTERN = re.compile(r'\.\.[\\/]')

# SQL injection patterns
SQL_INJECTION_PATTERNS = [
    re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b)", re.IGNORECASE),
    re.compile(r"(--|;|/\*|\*/)", re.IGNORECASE),
]

# XSS patterns
XSS_PATTERNS = [
    re.compile(r'<script', re.IGNORECASE),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),
]


# ========== Validation Functions ==========

def validate_id(value: str, field_name: str = "id") -> str:
    """Validate a safe ID string."""
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} cannot be empty"
        )
    
    if not SAFE_ID_PATTERN.match(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} contains invalid characters. Use alphanumeric, hyphens, underscores only."
        )
    
    return value


def validate_uuid(value: str, field_name: str = "id") -> str:
    """Validate UUID format."""
    if not UUID_PATTERN.match(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be a valid UUID"
        )
    return value


def validate_email(value: str) -> str:
    """Validate email format."""
    if not EMAIL_PATTERN.match(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    return value.lower()


def sanitize_string(
    value: str, 
    max_length: int = 10000,
    allow_html: bool = False,
    field_name: str = "input"
) -> str:
    """
    Sanitize a string input.
    
    - Trims whitespace
    - Enforces max length
    - Detects path traversal
    - Optionally blocks HTML/XSS
    """
    if not isinstance(value, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be a string"
        )
    
    value = value.strip()
    
    if len(value) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} exceeds maximum length of {max_length}"
        )
    
    # Check for path traversal
    if PATH_TRAVERSAL_PATTERN.search(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} contains invalid path characters"
        )
    
    # Check for XSS if HTML not allowed
    if not allow_html:
        for pattern in XSS_PATTERNS:
            if pattern.search(value):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field_name} contains potentially unsafe content"
                )
    
    return value


def validate_list_size(
    items: List[Any], 
    max_size: int = 100,
    field_name: str = "list"
) -> List[Any]:
    """Validate list doesn't exceed maximum size."""
    if len(items) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} exceeds maximum size of {max_size}"
        )
    return items


def validate_pagination(
    offset: int = 0, 
    limit: int = 20,
    max_limit: int = 100
) -> tuple[int, int]:
    """Validate and normalize pagination parameters."""
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 20
    if limit > max_limit:
        limit = max_limit
    return offset, limit


# ========== Pydantic Mixins ==========

class SafeIdMixin(BaseModel):
    """Mixin for models with ID validation."""
    
    @field_validator('*', mode='before')
    @classmethod
    def validate_id_fields(cls, v, info):
        if info.field_name.endswith('_id') and isinstance(v, str):
            if not SAFE_ID_PATTERN.match(v):
                raise ValueError(f'{info.field_name} contains invalid characters')
        return v


class SanitizedInputMixin(BaseModel):
    """Mixin for models with string sanitization."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    @field_validator('*', mode='before')
    @classmethod
    def sanitize_strings(cls, v, info):
        if isinstance(v, str):
            # Basic sanitization
            v = v.strip()
            # Check for path traversal
            if PATH_TRAVERSAL_PATTERN.search(v):
                raise ValueError(f'{info.field_name} contains invalid path characters')
        return v


# ========== Request Validation Decorator ==========

def validate_request_ids(*id_params: str):
    """
    Decorator to validate ID parameters in route handlers.
    
    Usage:
        @app.get("/items/{item_id}")
        @validate_request_ids("item_id")
        async def get_item(item_id: str): ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for param in id_params:
                if param in kwargs:
                    validate_id(kwargs[param], param)
            return await func(*args, **kwargs)
        return wrapper
    return decorator
