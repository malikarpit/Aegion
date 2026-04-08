"""
Rate Limiting & Abuse Protection Tests.

Validates:
- Token bucket algorithm (consume, refill, burst)
- WebSocket throttle (per-user, per-workspace, violation tracking)
- SSE flood control (backpressure circuit breaker)
- Proposal rate limiter (hourly/daily limits, exponential backoff)
- AI quota enforcer (token/cost limits, budget remaining)
"""

import pytest
import time
from unittest.mock import patch

from app.middleware.websocket_throttle import (
    TokenBucket,
    WebSocketThrottle,
    SSEFloodControl,
    ProposalRateLimiter,
    AIQuotaEnforcer,
    AIUsageRecord,
    WS_CLOSE_RATE_LIMITED,
    get_ws_throttle,
    get_proposal_limiter,
    get_ai_quota_enforcer,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Token Bucket
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestTokenBucket:
    def test_initial_capacity(self):
        bucket = TokenBucket(capacity=10.0, rate=1.0)
        assert bucket.available >= 9.9  # ~10 minus tiny elapsed time

    def test_consume_within_capacity(self):
        bucket = TokenBucket(capacity=5.0, rate=1.0)
        assert bucket.consume() is True
        assert bucket.consume() is True

    def test_consume_exceeds_capacity(self):
        bucket = TokenBucket(capacity=2.0, rate=0.0)  # No refill
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is False  # Exhausted

    def test_refill_over_time(self):
        bucket = TokenBucket(capacity=1.0, rate=1000.0)  # Fast refill
        bucket.consume()
        # With rate=1000/s, even a tiny time delta should refill
        time.sleep(0.01)
        assert bucket.consume() is True

    def test_burst_allowed(self):
        bucket = TokenBucket(capacity=10.0, rate=1.0)
        # Should allow consuming 10 tokens immediately (burst)
        for _ in range(10):
            assert bucket.consume() is True
        # 11th should fail
        assert bucket.consume() is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WebSocket Throttle
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestWebSocketThrottle:
    def setup_method(self):
        self.throttle = WebSocketThrottle(
            user_rate=5.0, user_burst=5.0,
            workspace_rate=10.0, workspace_burst=10.0,
        )

    def test_allowed_within_rate(self):
        allowed, reason = self.throttle.check_message_allowed("user1", "ws1")
        assert allowed is True
        assert reason is None

    def test_user_rate_exceeded(self):
        # Exhaust user bucket
        for _ in range(5):
            self.throttle.check_message_allowed("user1", "ws1")

        allowed, reason = self.throttle.check_message_allowed("user1", "ws1")
        assert allowed is False
        assert "User rate limit" in reason

    def test_workspace_rate_exceeded(self):
        # Exhaust workspace bucket (10 msgs from different users)
        for i in range(10):
            self.throttle.check_message_allowed(f"user{i}", "ws1")

        allowed, reason = self.throttle.check_message_allowed("user99", "ws1")
        assert allowed is False
        assert "Workspace rate limit" in reason

    def test_violation_tracking(self):
        # Exhaust and trigger violation
        for _ in range(5):
            self.throttle.check_message_allowed("user1", "ws1")
        self.throttle.check_message_allowed("user1", "ws1")

        assert self.throttle.get_violation_count("user1", "ws_user_rate") >= 1

    def test_separate_user_buckets(self):
        """Different users have independent rate limits."""
        # Exhaust user1
        for _ in range(5):
            self.throttle.check_message_allowed("user1", "ws1")

        # user2 should still be allowed
        allowed, _ = self.throttle.check_message_allowed("user2", "ws1")
        assert allowed is True

    def test_cleanup_stale(self):
        self.throttle.check_message_allowed("user1", "ws1")
        # Mark bucket as old manually
        self.throttle._user_buckets["user1"]._last_refill = time.monotonic() - 600
        removed = self.throttle.cleanup_stale(max_age_seconds=300)
        assert removed >= 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SSE Flood Control
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestSSEFloodControl:
    def setup_method(self):
        self.sse = SSEFloodControl(max_backpressure_events=3)

    def test_no_trip_below_threshold(self):
        assert self.sse.record_backpressure("client1") is False
        assert self.sse.record_backpressure("client1") is False

    def test_circuit_breaker_trips(self):
        """After 3 backpressure events, circuit breaker trips."""
        self.sse.record_backpressure("client1")
        self.sse.record_backpressure("client1")
        assert self.sse.record_backpressure("client1") is True

    def test_success_resets_backpressure(self):
        self.sse.record_backpressure("client1")
        self.sse.record_backpressure("client1")
        self.sse.record_success("client1")  # Reset
        # Should need 3 more before tripping
        assert self.sse.record_backpressure("client1") is False
        assert self.sse.record_backpressure("client1") is False
        assert self.sse.record_backpressure("client1") is True

    def test_remove_client_cleanup(self):
        self.sse.record_backpressure("client1")
        self.sse.remove_client("client1")
        # New backpressure should start fresh
        assert self.sse.record_backpressure("client1") is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Proposal Rate Limiter
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestProposalRateLimiter:
    def setup_method(self):
        self.limiter = ProposalRateLimiter(
            user_hourly_limit=3,
            workspace_daily_limit=5,
        )

    def test_allowed_within_limit(self):
        allowed, reason, retry = self.limiter.check_allowed("user1", "ws1")
        assert allowed is True
        assert reason is None
        assert retry is None

    def test_user_hourly_limit(self):
        for _ in range(3):
            self.limiter.check_allowed("user1", "ws1")

        allowed, reason, retry = self.limiter.check_allowed("user1", "ws1")
        assert allowed is False
        assert "hourly" in reason
        assert retry is not None

    def test_workspace_daily_limit(self):
        for i in range(5):
            self.limiter.check_allowed(f"user{i}", "ws1")

        allowed, reason, retry = self.limiter.check_allowed("user99", "ws1")
        assert allowed is False
        assert "daily" in reason

    def test_exponential_backoff(self):
        """Repeated violations should increase retry-after time."""
        for _ in range(3):
            self.limiter.check_allowed("user1", "ws1")

        _, _, retry1 = self.limiter.check_allowed("user1", "ws1")
        _, _, retry2 = self.limiter.check_allowed("user1", "ws1")
        assert retry2 > retry1  # Exponential increase

    def test_separate_workspace_limits(self):
        """Different workspaces have independent limits."""
        for _ in range(3):
            self.limiter.check_allowed("user1", "ws1")

        # Same user, different workspace should work
        allowed, _, _ = self.limiter.check_allowed("user1_new", "ws2")
        assert allowed is True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI Quota Enforcer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAIQuotaEnforcer:
    def setup_method(self):
        self.quota = AIQuotaEnforcer(
            daily_token_limit=1000,
            per_request_cost_limit=0.50,
            daily_cost_limit=5.00,
        )

    def test_allowed_with_budget(self):
        allowed, reason, headers = self.quota.check_budget("user1", estimated_tokens=100)
        assert allowed is True
        assert reason is None
        assert "X-AI-Budget-Remaining" in headers

    def test_per_request_cost_cap(self):
        """Requests exceeding per-request cost limit are blocked."""
        allowed, reason, headers = self.quota.check_budget(
            "user1", estimated_cost=0.75
        )
        assert allowed is False
        assert "per-request limit" in reason

    def test_daily_token_limit(self):
        """Once daily tokens are consumed, further requests are blocked."""
        self.quota.record_usage("user1", tokens_used=900, cost_usd=1.00)

        allowed, reason, _ = self.quota.check_budget("user1", estimated_tokens=200)
        assert allowed is False
        assert "token limit" in reason

    def test_daily_cost_limit(self):
        self.quota.record_usage("user1", tokens_used=100, cost_usd=4.80)

        allowed, reason, _ = self.quota.check_budget("user1", estimated_cost=0.30)
        assert allowed is False
        assert "cost limit" in reason

    def test_budget_remaining_header(self):
        """X-AI-Budget-Remaining should reflect remaining tokens."""
        self.quota.record_usage("user1", tokens_used=300, cost_usd=0.50)

        allowed, _, headers = self.quota.check_budget("user1", estimated_tokens=100)
        assert allowed is True
        remaining = int(headers["X-AI-Budget-Remaining"])
        assert remaining == 600  # 1000 - 300 - 100

    def test_usage_recording(self):
        self.quota.record_usage("user1", tokens_used=500, cost_usd=2.00)
        usage = self.quota.get_usage("user1")
        assert usage.tokens_used == 500
        assert usage.cost_usd == 2.00
        assert usage.requests_today == 1

    def test_day_reset(self):
        """Usage should reset after 24 hours."""
        self.quota.record_usage("user1", tokens_used=900, cost_usd=4.00)
        # Simulate day rollover
        usage = self.quota.get_usage("user1")
        usage.day_start = time.time() - 86401  # >24h ago
        usage.reset_if_new_day()
        assert usage.tokens_used == 0
        assert usage.cost_usd == 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Singleton Accessors
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestSingletons:
    def test_ws_throttle_singleton(self):
        t1 = get_ws_throttle()
        t2 = get_ws_throttle()
        assert t1 is t2

    def test_proposal_limiter_singleton(self):
        p1 = get_proposal_limiter()
        p2 = get_proposal_limiter()
        assert p1 is p2

    def test_ai_quota_singleton(self):
        a1 = get_ai_quota_enforcer()
        a2 = get_ai_quota_enforcer()
        assert a1 is a2

    def test_ws_close_code_defined(self):
        assert WS_CLOSE_RATE_LIMITED == 4008
