"""
Tests for Rejection Learner — Phase R5.

Reference: Christiano et al., 2017 — "Deep Reinforcement Learning from Human Preferences"

Covers:
    Recording:
        - Record single rejection
        - Record multiple rejections
        - Rejection stores timestamp

    Penalty Calculation:
        - No rejections → zero penalty
        - Identical query → max penalty
        - Partial overlap → proportional
        - Penalty capped at MAX_PENALTY
        - Unrelated query → near zero
        - Workspace filtering

    Trends:
        - Empty trends
        - Counts recent only
        - Top reasons
        - Filters by workspace
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.services.rejection_learner import (
    RejectionLearner,
    get_rejection_learner,
)


# ══════════════════════════════════════════════════════════════════════════════
# RECORDING
# ══════════════════════════════════════════════════════════════════════════════

class TestRejectionRecording:
    def test_record_rejection(self):
        rl = RejectionLearner()
        entry = rl.record_rejection("fix the auth bug", "Irrelevant", "ws1")
        assert entry["reason"] == "Irrelevant"
        assert entry["workspace_id"] == "ws1"
        assert len(rl.get_log()) == 1

    def test_multiple_rejections(self):
        rl = RejectionLearner()
        rl.record_rejection("query1", "bad", "ws1")
        rl.record_rejection("query2", "wrong", "ws1")
        rl.record_rejection("query3", "bad", "ws2")
        assert len(rl.get_log()) == 3

    def test_rejection_stores_timestamp(self):
        rl = RejectionLearner()
        ts = datetime(2025, 1, 15, tzinfo=timezone.utc)
        entry = rl.record_rejection("test", "reason", "ws1", timestamp=ts)
        assert entry["timestamp"] == ts

    def test_clear_by_workspace(self):
        rl = RejectionLearner()
        rl.record_rejection("a", "r", "ws1")
        rl.record_rejection("b", "r", "ws2")
        removed = rl.clear("ws1")
        assert removed == 1
        assert len(rl.get_log()) == 1

    def test_clear_all(self):
        rl = RejectionLearner()
        rl.record_rejection("a", "r", "ws1")
        rl.record_rejection("b", "r", "ws2")
        removed = rl.clear()
        assert removed == 2
        assert len(rl.get_log()) == 0


# ══════════════════════════════════════════════════════════════════════════════
# PENALTY CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

class TestPenaltyCalculation:
    def test_no_rejections_zero_penalty(self):
        rl = RejectionLearner()
        assert rl.get_penalty("some query") == 0.0

    def test_identical_query_max_penalty(self):
        rl = RejectionLearner()
        rl.record_rejection("fix the authentication bug", "bad", "ws1")
        penalty = rl.get_penalty("fix the authentication bug")
        # Jaccard = 1.0 → penalty = BASE_PENALTY * 1.0 = 0.15
        assert penalty == pytest.approx(0.15, abs=0.01)

    def test_partial_overlap_proportional(self):
        rl = RejectionLearner()
        rl.record_rejection("database migration strategy", "wrong approach", "ws1")
        penalty = rl.get_penalty("database schema validation")
        # "database" overlaps → some penalty, but not max
        assert 0.0 < penalty < rl.MAX_PENALTY

    def test_penalty_capped_at_max(self):
        rl = RejectionLearner()
        # Even with perfect overlap, penalty should not exceed MAX_PENALTY
        rl.record_rejection("test query words", "bad", "ws1")
        penalty = rl.get_penalty("test query words")
        assert penalty <= rl.MAX_PENALTY

    def test_unrelated_query_near_zero(self):
        rl = RejectionLearner()
        rl.record_rejection("optimize database queries", "bad", "ws1")
        penalty = rl.get_penalty("frontend react component rendering")
        assert penalty < 0.05  # Very low — no word overlap

    def test_workspace_filtering(self):
        rl = RejectionLearner()
        rl.record_rejection("database migration", "bad", "ws1")
        # Should find something when filtering to ws1
        penalty_ws1 = rl.get_penalty("database migration", workspace_id="ws1")
        # Should find nothing when filtering to ws2
        penalty_ws2 = rl.get_penalty("database migration", workspace_id="ws2")
        assert penalty_ws1 > 0
        assert penalty_ws2 == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# TRENDS
# ══════════════════════════════════════════════════════════════════════════════

class TestTrends:
    def test_trends_empty(self):
        rl = RejectionLearner()
        trends = rl.get_trends("ws1")
        assert trends["total_rejections"] == 0
        assert trends["top_reasons"] == []
        assert trends["daily_counts"] == {}

    def test_trends_counts_recent_only(self):
        rl = RejectionLearner()
        old = datetime.now(timezone.utc) - timedelta(days=60)
        recent = datetime.now(timezone.utc) - timedelta(days=5)
        rl.record_rejection("old query", "old reason", "ws1", timestamp=old)
        rl.record_rejection("new query", "new reason", "ws1", timestamp=recent)
        trends = rl.get_trends("ws1", days=30)
        assert trends["total_rejections"] == 1

    def test_trends_top_reasons(self):
        rl = RejectionLearner()
        now = datetime.now(timezone.utc)
        rl.record_rejection("q1", "irrelevant", "ws1", timestamp=now)
        rl.record_rejection("q2", "irrelevant", "ws1", timestamp=now)
        rl.record_rejection("q3", "wrong approach", "ws1", timestamp=now)
        trends = rl.get_trends("ws1")
        assert trends["top_reasons"][0] == ("irrelevant", 2)

    def test_trends_filters_by_workspace(self):
        rl = RejectionLearner()
        now = datetime.now(timezone.utc)
        rl.record_rejection("q1", "bad", "ws1", timestamp=now)
        rl.record_rejection("q2", "bad", "ws2", timestamp=now)
        trends = rl.get_trends("ws1")
        assert trends["total_rejections"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

class TestRejectionSingleton:
    def test_singleton(self):
        import app.services.rejection_learner as mod
        mod._rejection_learner = None
        l1 = get_rejection_learner()
        l2 = get_rejection_learner()
        assert l1 is l2
        mod._rejection_learner = None
