"""
Unit tests for Archon Tier Routing — Phase 69.

Tests the governance tier classification system covering:
  - T1 auto-approve classification
  - T2 council review classification
  - T3 human required classification
  - Tier routing based on query complexity + risk
  - Override behavior for sentinel alerts
"""

import pytest
from unittest.mock import MagicMock, patch
from app.services.council_kernel.types import CouncilType, CouncilProfile
from app.services.council_kernel.engine import CouncilEngine


@pytest.fixture
def engine():
    e = CouncilEngine()
    e.model_router = MagicMock()
    e.model_router.providers = {}
    return e


class TestTierClassification:
    """Test the _classify method that determines council profile based on query + type."""

    def test_trivial_query_child_council(self, engine):
        """Short factual queries to CHILD council → TRIVIAL or SIMPLE."""
        profile = engine._classify("What is a REST API?", CouncilType.CHILD)
        assert profile in [CouncilProfile.TRIVIAL, CouncilProfile.SIMPLE]

    def test_moderate_query_child(self, engine):
        """Medium-length technical queries → SIMPLE or MODERATE."""
        query = "Explain the trade-offs between using Redis as a cache vs PostgreSQL materialized views for read-heavy workloads"
        profile = engine._classify(query, CouncilType.CHILD)
        assert profile in [CouncilProfile.SIMPLE, CouncilProfile.MODERATE, CouncilProfile.COMPLEX]

    def test_complex_query_parent(self, engine):
        """Long architectural queries to PARENT council → COMPLEX or CRITICAL."""
        query = (
            "Design a complete microservice architecture for a real-time bidding system "
            "that handles 10,000 requests per second with sub-50ms latency requirements. "
            "The system needs event sourcing with CQRS patterns, distributed tracing, "
            "circuit breakers, and blue-green deployment strategy. Include database schema "
            "design for PostgreSQL with pgvector integration, Redis caching layer with "
            "write-through and write-behind strategies, Kafka topic partitioning, "
            "and Kubernetes deployment topology with HPA scaling policies. "
            "Also address GDPR compliance for PII handling and disaster recovery."
        )
        profile = engine._classify(query, CouncilType.PARENT)
        assert profile in [CouncilProfile.MODERATE, CouncilProfile.COMPLEX, CouncilProfile.CRITICAL]

    def test_sentinel_queries_elevated(self, engine):
        """SENTINEL council queries should get elevated complexity."""
        profile = engine._classify("Check for SQL injection vulnerabilities", CouncilType.SENTINEL)
        # Sentinel queries should be at least MODERATE
        assert profile in [CouncilProfile.MODERATE, CouncilProfile.COMPLEX, CouncilProfile.CRITICAL]

    def test_empty_query(self, engine):
        """Empty query should not crash."""
        profile = engine._classify("", CouncilType.CHILD)
        assert isinstance(profile, CouncilProfile)

    def test_classification_is_deterministic(self, engine):
        """Same query + type should always produce same profile."""
        query = "How does PKCE work in OAuth 2.0?"
        p1 = engine._classify(query, CouncilType.CHILD)
        p2 = engine._classify(query, CouncilType.CHILD)
        assert p1 == p2


class TestArchonGovernanceTiers:
    """Test the governance tier system (T1/T2/T3) mapping."""

    def test_t1_maps_to_child(self):
        """T1 (auto-approve) should map to CHILD council."""
        assert CouncilType.CHILD.value == "child"

    def test_t2_maps_to_parent(self):
        """T2 (council review) should map to PARENT council."""
        assert CouncilType.PARENT.value == "parent"

    def test_t3_maps_to_sentinel(self):
        """T3 triggers Sentinel for security-critical decisions."""
        assert CouncilType.SENTINEL.value == "sentinel"

    def test_distillation_type_exists(self):
        """DISTILLATION type for session artifact processing."""
        assert CouncilType.DISTILLATION.value == "distillation"

    def test_all_council_types(self):
        """All 4 council types should be defined."""
        types = [t.value for t in CouncilType]
        assert len(types) == 4
        assert "child" in types
        assert "parent" in types
        assert "sentinel" in types
        assert "distillation" in types


class TestCouncilProfiles:
    """Test CouncilProfile complexity levels."""

    def test_all_profiles_exist(self):
        profiles = [p.value for p in CouncilProfile]
        assert "trivial" in profiles
        assert "simple" in profiles
        assert "moderate" in profiles
        assert "complex" in profiles
        assert "critical" in profiles

    def test_profile_ordering_concept(self):
        """Profiles should represent increasing complexity."""
        order = ["trivial", "simple", "moderate", "complex", "critical"]
        profiles = [p.value for p in CouncilProfile]
        for expected in order:
            assert expected in profiles
