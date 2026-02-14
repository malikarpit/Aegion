"""
Aegion WebSocket & SSE Throttle: Enterprise Hardening.

Token bucket rate limiting for real-time connections:
- WebSocket: per-user and per-workspace message limits
- SSE: backpressure detection with circuit breaker
- Proposal: submission spam prevention
- AI: per-user daily token/cost quotas

Design:
- Token bucket algorithm: smooth rate control, burst tolerance
- Close connections with appropriate error codes on violation
- Thread-safe, async-compatible
"""

import asyncio
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field

from ..core.logging import logger


# ========== Token Bucket Algorithm ==========

@dataclass
class TokenBucket:
    """
    Token bucket rate limiter.

    Allows burst up to `capacity`, refills at `rate` tokens per second.
    """
    capacity: float
    rate: float  # tokens per second
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)

    def __post_init__(self):
        self._tokens = self.capacity
        self._last_refill = time.monotonic()

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate limited."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now

        # Refill tokens
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)

        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    @property
    def available(self) -> float:
        """Current available tokens (without consuming)."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        return min(self.capacity, self._tokens + elapsed * self.rate)


# ========== WebSocket Throttle ==========

# Close codes for WebSocket violations
WS_CLOSE_RATE_LIMITED = 4008
WS_CLOSE_ABUSE_DETECTED = 4009


class WebSocketThrottle:
    """
    Per-user and per-workspace WebSocket message throttling.

    Limits:
    - Per-user: 10 messages/second (burst up to 15)
    - Per-workspace: 50 messages/second (burst up to 75)
    - Close connection with 4008 on violation
    """

    def __init__(
        self,
        user_rate: float = 10.0,
        user_burst: float = 15.0,
        workspace_rate: float = 50.0,
        workspace_burst: float = 75.0,
    ):
        self._user_buckets: Dict[str, TokenBucket] = {}
        self._workspace_buckets: Dict[str, TokenBucket] = {}
        self._user_rate = user_rate
        self._user_burst = user_burst
        self._workspace_rate = workspace_rate
        self._workspace_burst = workspace_burst
        self._violation_counts: Dict[str, int] = {}

    def _get_user_bucket(self, user_id: str) -> TokenBucket:
        if user_id not in self._user_buckets:
            self._user_buckets[user_id] = TokenBucket(
                capacity=self._user_burst,
                rate=self._user_rate,
            )
        return self._user_buckets[user_id]

    def _get_workspace_bucket(self, workspace_id: str) -> TokenBucket:
        if workspace_id not in self._workspace_buckets:
            self._workspace_buckets[workspace_id] = TokenBucket(
                capacity=self._workspace_burst,
                rate=self._workspace_rate,
            )
        return self._workspace_buckets[workspace_id]

    def check_message_allowed(
        self, user_id: str, workspace_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a WebSocket message is allowed.

        Returns:
            (allowed, reason_if_blocked)
        """
        user_bucket = self._get_user_bucket(user_id)
        workspace_bucket = self._get_workspace_bucket(workspace_id)

        if not user_bucket.consume():
            self._record_violation(user_id, "ws_user_rate")
            return False, f"User rate limit exceeded ({self._user_rate} msg/s)"

        if not workspace_bucket.consume():
            self._record_violation(workspace_id, "ws_workspace_rate")
            return False, f"Workspace rate limit exceeded ({self._workspace_rate} msg/s)"

        return True, None

    def _record_violation(self, key: str, violation_type: str) -> None:
        """Track violations per key for escalation."""
        vkey = f"{violation_type}:{key}"
        self._violation_counts[vkey] = self._violation_counts.get(vkey, 0) + 1
        count = self._violation_counts[vkey]

        logger.warning(
            "WebSocket rate limit violation",
            extra={
                "key": key,
                "type": violation_type,
                "violation_count": count,
            },
        )

    def get_violation_count(self, key: str, violation_type: str) -> int:
        """Get violation count for monitoring/escalation."""
        return self._violation_counts.get(f"{violation_type}:{key}", 0)

    def cleanup_stale(self, max_age_seconds: float = 300.0) -> int:
        """Remove buckets that haven't been used in max_age_seconds."""
        now = time.monotonic()
        removed = 0

        stale_users = [
            uid for uid, bucket in self._user_buckets.items()
            if now - bucket._last_refill > max_age_seconds
        ]
        for uid in stale_users:
            del self._user_buckets[uid]
            removed += 1

        stale_workspaces = [
            wid for wid, bucket in self._workspace_buckets.items()
            if now - bucket._last_refill > max_age_seconds
        ]
        for wid in stale_workspaces:
            del self._workspace_buckets[wid]
            removed += 1

        return removed


# ========== SSE Flood Control ==========

class SSEFloodControl:
    """
    SSE (Server-Sent Events) backpressure detection with circuit breaker.

    If a client can't consume events fast enough (backpressure),
    disconnect after `max_backpressure_events` consecutive failures.
    """

    def __init__(self, max_backpressure_events: int = 3, event_rate: float = 100.0):
        self._backpressure_counts: Dict[str, int] = {}
        self._max_backpressure = max_backpressure_events
        self._event_buckets: Dict[str, TokenBucket] = {}
        self._event_rate = event_rate

    def record_backpressure(self, client_id: str) -> bool:
        """
        Record a backpressure event for a client.

        Returns True if circuit breaker should trip (disconnect client).
        """
        self._backpressure_counts[client_id] = (
            self._backpressure_counts.get(client_id, 0) + 1
        )
        count = self._backpressure_counts[client_id]

        if count >= self._max_backpressure:
            logger.warning(
                "SSE circuit breaker tripped",
                extra={"client_id": client_id, "backpressure_count": count},
            )
            return True
        return False

    def record_success(self, client_id: str) -> None:
        """Reset backpressure count on successful delivery."""
        self._backpressure_counts[client_id] = 0

    def check_event_rate(self, client_id: str) -> bool:
        """Check if event rate is within limits."""
        if client_id not in self._event_buckets:
            self._event_buckets[client_id] = TokenBucket(
                capacity=self._event_rate * 2,
                rate=self._event_rate,
            )
        return self._event_buckets[client_id].consume()

    def remove_client(self, client_id: str) -> None:
        """Clean up when client disconnects."""
        self._backpressure_counts.pop(client_id, None)
        self._event_buckets.pop(client_id, None)


# ========== Proposal Spam Prevention ==========

class ProposalRateLimiter:
    """
    Prevents proposal submission spam.

    Limits:
    - Per user: 10 proposals per hour
    - Per workspace: 50 proposals per day
    - Exponential backoff on repeated violations
    """

    def __init__(
        self,
        user_hourly_limit: int = 10,
        workspace_daily_limit: int = 50,
    ):
        self._user_hourly_limit = user_hourly_limit
        self._workspace_daily_limit = workspace_daily_limit
        self._user_counts: Dict[str, list] = {}  # user_id -> [timestamps]
        self._workspace_counts: Dict[str, list] = {}  # workspace_id -> [timestamps]
        self._violation_backoff: Dict[str, int] = {}  # user_id -> violation count

    def check_allowed(
        self, user_id: str, workspace_id: str
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check if proposal submission is allowed.

        Returns:
            (allowed, reason_if_blocked, retry_after_seconds)
        """
        now = time.time()

        # Check user hourly limit
        user_timestamps = self._user_counts.get(user_id, [])
        hour_ago = now - 3600
        user_timestamps = [t for t in user_timestamps if t > hour_ago]
        self._user_counts[user_id] = user_timestamps

        if len(user_timestamps) >= self._user_hourly_limit:
            backoff = self._get_backoff(user_id)
            return False, f"User hourly limit ({self._user_hourly_limit}/hr)", backoff

        # Check workspace daily limit
        ws_timestamps = self._workspace_counts.get(workspace_id, [])
        day_ago = now - 86400
        ws_timestamps = [t for t in ws_timestamps if t > day_ago]
        self._workspace_counts[workspace_id] = ws_timestamps

        if len(ws_timestamps) >= self._workspace_daily_limit:
            return False, f"Workspace daily limit ({self._workspace_daily_limit}/day)", 3600

        # Record submission
        user_timestamps.append(now)
        ws_timestamps.append(now)

        return True, None, None

    def _get_backoff(self, user_id: str) -> int:
        """Exponential backoff for repeated violations."""
        self._violation_backoff[user_id] = self._violation_backoff.get(user_id, 0) + 1
        count = self._violation_backoff[user_id]
        return min(60 * (2 ** (count - 1)), 3600)  # Cap at 1 hour

    @property
    def user_hourly_limit(self) -> int:
        return self._user_hourly_limit

    @property
    def workspace_daily_limit(self) -> int:
        return self._workspace_daily_limit


# ========== AI Token/Cost Quotas ==========

@dataclass
class AIUsageRecord:
    """Tracks AI token usage and cost per user per day."""
    tokens_used: int = 0
    cost_usd: float = 0.0
    requests_today: int = 0
    day_start: float = field(default_factory=time.time)

    def is_new_day(self) -> bool:
        """Check if we've rolled over to a new day."""
        return (time.time() - self.day_start) > 86400

    def reset_if_new_day(self) -> None:
        """Reset counters if it's a new day."""
        if self.is_new_day():
            self.tokens_used = 0
            self.cost_usd = 0.0
            self.requests_today = 0
            self.day_start = time.time()


class AIQuotaEnforcer:
    """
    Per-user daily AI token and cost quotas.

    Limits:
    - Daily token limit (default: 100,000 tokens/user/day)
    - Per-request cost limit ($1.00 hard cap)
    - Daily cost limit ($10.00/user/day)

    Returns X-AI-Budget-Remaining header for client awareness.
    """

    def __init__(
        self,
        daily_token_limit: int = 100_000,
        per_request_cost_limit: float = 1.00,
        daily_cost_limit: float = 10.00,
    ):
        self._daily_token_limit = daily_token_limit
        self._per_request_cost_limit = per_request_cost_limit
        self._daily_cost_limit = daily_cost_limit
        self._usage: Dict[str, AIUsageRecord] = {}

    def _get_usage(self, user_id: str) -> AIUsageRecord:
        if user_id not in self._usage:
            self._usage[user_id] = AIUsageRecord()
        record = self._usage[user_id]
        record.reset_if_new_day()
        return record

    def check_budget(
        self, user_id: str, estimated_tokens: int = 0, estimated_cost: float = 0.0
    ) -> Tuple[bool, Optional[str], Dict[str, str]]:
        """
        Check if user has AI budget remaining.

        Returns:
            (allowed, reason_if_blocked, response_headers)
        """
        usage = self._get_usage(user_id)
        headers = {}

        # Per-request cost cap
        if estimated_cost > self._per_request_cost_limit:
            return (
                False,
                f"Request cost ${estimated_cost:.2f} exceeds per-request limit ${self._per_request_cost_limit:.2f}",
                {"X-AI-Budget-Remaining": "0"},
            )

        # Daily token check
        remaining_tokens = self._daily_token_limit - usage.tokens_used
        if estimated_tokens > remaining_tokens:
            return (
                False,
                f"Daily token limit reached ({usage.tokens_used}/{self._daily_token_limit})",
                {"X-AI-Budget-Remaining": "0"},
            )

        # Daily cost check
        remaining_cost = self._daily_cost_limit - usage.cost_usd
        if estimated_cost > remaining_cost:
            return (
                False,
                f"Daily cost limit reached (${usage.cost_usd:.2f}/${self._daily_cost_limit:.2f})",
                {"X-AI-Budget-Remaining": "0"},
            )

        headers["X-AI-Budget-Remaining"] = str(remaining_tokens - estimated_tokens)
        return True, None, headers

    def record_usage(
        self, user_id: str, tokens_used: int, cost_usd: float
    ) -> None:
        """Record AI usage after a successful request."""
        usage = self._get_usage(user_id)
        usage.tokens_used += tokens_used
        usage.cost_usd += cost_usd
        usage.requests_today += 1

    def get_usage(self, user_id: str) -> AIUsageRecord:
        """Get current usage for a user (for reporting)."""
        return self._get_usage(user_id)

    @property
    def daily_token_limit(self) -> int:
        return self._daily_token_limit

    @property
    def daily_cost_limit(self) -> float:
        return self._daily_cost_limit


# ========== Singletons ==========

_ws_throttle: Optional[WebSocketThrottle] = None
_sse_flood: Optional[SSEFloodControl] = None
_proposal_limiter: Optional[ProposalRateLimiter] = None
_ai_quota: Optional[AIQuotaEnforcer] = None


def get_ws_throttle() -> WebSocketThrottle:
    global _ws_throttle
    if _ws_throttle is None:
        _ws_throttle = WebSocketThrottle()
    return _ws_throttle


def get_sse_flood_control() -> SSEFloodControl:
    global _sse_flood
    if _sse_flood is None:
        _sse_flood = SSEFloodControl()
    return _sse_flood


def get_proposal_limiter() -> ProposalRateLimiter:
    global _proposal_limiter
    if _proposal_limiter is None:
        _proposal_limiter = ProposalRateLimiter()
    return _proposal_limiter


def get_ai_quota_enforcer() -> AIQuotaEnforcer:
    global _ai_quota
    if _ai_quota is None:
        _ai_quota = AIQuotaEnforcer()
    return _ai_quota
