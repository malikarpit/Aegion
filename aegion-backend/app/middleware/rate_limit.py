"""
Aegion Rate Limiting Middleware.

Production-grade rate limiting using sliding window algorithm.
Supports both in-memory (dev) and Redis (production) backends.
"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
import time

from ..core.config import settings
from ..core.logging import logger


class RateLimitBackend:
    """Abstract rate limit storage backend."""
    
    async def is_rate_limited(
        self, 
        key: str, 
        limit: int, 
        window_seconds: int
    ) -> Tuple[bool, int, int]:
        """
        Check if key is rate limited.
        
        Returns:
            (is_limited, remaining, reset_after_seconds)
        """
        raise NotImplementedError


class InMemoryRateLimitBackend(RateLimitBackend):
    """In-memory rate limiter for development."""
    
    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def is_rate_limited(
        self, 
        key: str, 
        limit: int, 
        window_seconds: int
    ) -> Tuple[bool, int, int]:
        now = time.time()
        window_start = now - window_seconds
        
        async with self._lock:
            # Clean old requests
            self._requests[key] = [
                ts for ts in self._requests[key] 
                if ts > window_start
            ]
            
            current_count = len(self._requests[key])
            
            if current_count >= limit:
                # Calculate reset time
                oldest = min(self._requests[key]) if self._requests[key] else now
                reset_after = int(oldest + window_seconds - now)
                return True, 0, max(reset_after, 1)
            
            # Record this request
            self._requests[key].append(now)
            remaining = limit - current_count - 1
            
            return False, remaining, window_seconds


class RedisRateLimitBackend(RateLimitBackend):
    """Redis-based rate limiter for production."""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis = None
    
    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self.redis_url)
            except ImportError:
                logger.warning("redis package not installed, falling back to in-memory")
                return None
        return self._redis
    
    async def is_rate_limited(
        self, 
        key: str, 
        limit: int, 
        window_seconds: int
    ) -> Tuple[bool, int, int]:
        redis = await self._get_redis()
        if redis is None:
            # Fallback - always allow
            return False, limit, window_seconds
        
        now = time.time()
        window_start = now - window_seconds
        
        pipe = redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        # Count current entries
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Set expiry
        pipe.expire(key, window_seconds)
        
        results = await pipe.execute()
        current_count = results[1]
        
        if current_count >= limit:
            # Get oldest entry to calculate reset
            oldest = await redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                reset_after = int(oldest[0][1] + window_seconds - now)
            else:
                reset_after = window_seconds
            return True, 0, max(reset_after, 1)
        
        remaining = limit - current_count - 1
        return False, remaining, window_seconds


class RateLimitConfig:
    """Rate limit configuration per endpoint category."""
    
    # Requests per minute
    DEFAULT = 60
    AUTH = 10  # Strict for auth endpoints
    AI = 20    # AI endpoints are expensive
    READ = 120 # Read-heavy endpoints
    ADMIN = 30 # Admin operations
    
    @classmethod
    def get_limit_for_path(cls, path: str) -> int:
        """Get rate limit based on endpoint path."""
        if "/auth/" in path or "/login" in path:
            return cls.AUTH
        if "/council/" in path or "/ghost-text" in path:
            return cls.AI
        if path.startswith("/v1/health"):
            return cls.READ * 10  # Health checks should be fast
        if "/admin/" in path:
            return cls.ADMIN
        if any(m in path for m in ["/get", "/list", "/query"]):
            return cls.READ
        return cls.DEFAULT


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware with configurable limits per endpoint.
    
    Headers returned:
    - X-RateLimit-Limit: Maximum requests allowed
    - X-RateLimit-Remaining: Requests remaining in window
    - X-RateLimit-Reset: Seconds until window resets
    - Retry-After: (on 429) Seconds to wait before retry
    """
    
    def __init__(self, app, redis_url: Optional[str] = None):
        super().__init__(app)
        
        if redis_url:
            self.backend = RedisRateLimitBackend(redis_url)
        else:
            self.backend = InMemoryRateLimitBackend()
        
        self.window_seconds = 60  # 1 minute window
        self.enabled = getattr(settings, 'RATE_LIMIT_ENABLED', True)
    
    def _get_client_key(self, request: Request) -> str:
        """Get unique client identifier."""
        # Try to get user ID from auth context
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"rate_limit:user:{user_id}"
        
        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        
        return f"rate_limit:ip:{ip}"
    
    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled:
            return await call_next(request)
        
        # Skip rate limiting for internal health checks
        if request.url.path in ["/health", "/health/live"]:
            return await call_next(request)
        
        client_key = self._get_client_key(request)
        limit = RateLimitConfig.get_limit_for_path(request.url.path)
        
        is_limited, remaining, reset_after = await self.backend.is_rate_limited(
            client_key, limit, self.window_seconds
        )
        
        if is_limited:
            logger.warning(
                f"Rate limit exceeded for {client_key} on {request.url.path}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down.",
                headers={
                    "Retry-After": str(reset_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_after),
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_after)
        
        return response


# Singleton for easy access
_rate_limiter: Optional[RateLimitMiddleware] = None


def get_rate_limit_middleware(redis_url: Optional[str] = None) -> RateLimitMiddleware:
    """Get rate limit middleware instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimitMiddleware
    return _rate_limiter
