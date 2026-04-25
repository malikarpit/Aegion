"""
Tests for BFT Consensus Engine — Multi-Response Agreement Analysis.

Covers:
    - Semantic Jaccard similarity
    - Single-linkage clustering
    - Quorum detection (PBFT 2/3+1)
    - Confidence-weighted voting
    - Edge cases: empty, single, unanimous, split
    - Argument graph construction

Reference: Implementation plan Section 1.4
"""

import pytest

from app.services.council_kernel.consensus import (
    BFTConsensus,
    ConsensusResult,
    _single_linkage_clusters,
    _tokenize,
    semantic_jaccard,
)


# ──────────────────────────────────────────────────────────────────────────────
# Similarity Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSemanticJaccard:
    """Semantic Jaccard similarity function."""

    def test_identical_texts(self):
        """Identical texts should have similarity 1.0."""
        text = "The quick brown fox jumps over the lazy dog"
        assert semantic_jaccard(text, text) == 1.0

    def test_completely_different(self):
        """Completely different texts should have low similarity."""
        a = "Python database query optimization techniques"
        b = "Watercolor painting landscape tutorial introduction"
        sim = semantic_jaccard(a, b)
        assert sim < 0.15

    def test_similar_texts(self):
        """Texts about the same topic should have high similarity."""
        a = "Use async await for database queries to improve performance"
        b = "Database queries should use async await for better performance"
        sim = semantic_jaccard(a, b)
        assert sim > 0.5

    def test_empty_texts(self):
        """Both empty texts → 1.0 (trivially identical)."""
        assert semantic_jaccard("", "") == 1.0

    def test_one_empty(self):
        """One empty text → 0.0."""
        assert semantic_jaccard("hello world", "") == 0.0
        assert semantic_jaccard("", "hello world") == 0.0

    def test_stopwords_ignored(self):
        """Stopwords shouldn't affect similarity."""
        a = "the and or but"  # All stopwords
        b = "is was are were"  # All stopwords
        # After filtering, both are empty → 1.0
        assert semantic_jaccard(a, b) == 1.0


class TestTokenize:
    """Tokenization for similarity."""

    def test_basic_tokenize(self):
        tokens = _tokenize("Use PostgreSQL database for faster queries")
        assert "postgresql" in tokens
        assert "database" in tokens
        assert "faster" in tokens
        assert "queries" in tokens

    def test_stopwords_removed(self):
        tokens = _tokenize("the quick and the slow")
        assert "the" not in tokens
        assert "and" not in tokens
        assert "quick" in tokens
        assert "slow" in tokens

    def test_short_words_removed(self):
        tokens = _tokenize("a is to go do it")
        # All words are < 3 chars or stopwords
        assert len(tokens) == 0


# ──────────────────────────────────────────────────────────────────────────────
# Clustering Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSingleLinkageClustering:
    """Single-linkage clustering on similarity matrix."""

    def test_all_similar(self):
        """All items similar → one cluster."""
        matrix = [
            [1.0, 0.8, 0.7],
            [0.8, 1.0, 0.9],
            [0.7, 0.9, 1.0],
        ]
        clusters = _single_linkage_clusters(matrix, 0.5)
        assert len(clusters) == 1
        assert sorted(clusters[0]) == [0, 1, 2]

    def test_two_clusters(self):
        """Two groups with low inter-group similarity → two clusters."""
        matrix = [
            [1.0, 0.9, 0.1, 0.1],
            [0.9, 1.0, 0.1, 0.1],
            [0.1, 0.1, 1.0, 0.8],
            [0.1, 0.1, 0.8, 1.0],
        ]
        clusters = _single_linkage_clusters(matrix, 0.5)
        assert len(clusters) == 2
        sizes = sorted([len(c) for c in clusters])
        assert sizes == [2, 2]

    def test_all_dissimilar(self):
        """No items similar → N singletons."""
        matrix = [
            [1.0, 0.1, 0.1],
            [0.1, 1.0, 0.1],
            [0.1, 0.1, 1.0],
        ]
        clusters = _single_linkage_clusters(matrix, 0.5)
        assert len(clusters) == 3

    def test_chain_linkage(self):
        """A-B similar, B-C similar but A-C not → all in one cluster (single-linkage)."""
        matrix = [
            [1.0, 0.6, 0.2],
            [0.6, 1.0, 0.6],
            [0.2, 0.6, 1.0],
        ]
        clusters = _single_linkage_clusters(matrix, 0.5)
        # Single-linkage chains A→B→C
        assert len(clusters) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Consensus Engine Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestBFTConsensus:
    """BFT consensus evaluation."""

    @pytest.fixture
    def engine(self):
        return BFTConsensus(agreement_threshold=0.35, quorum_fraction=0.67)

    def test_empty_responses(self, engine):
        """Empty input → no consensus."""
        result = engine.evaluate([])
        assert result.reached_consensus is False
        assert result.quorum_score == 0.0
        assert result.total_models == 0

    def test_single_response(self, engine):
        """Single response → automatic consensus."""
        result = engine.evaluate([{
            "text": "Use PostgreSQL for this workload",
            "model": "gpt-4o",
            "provider": "openai",
            "confidence": 0.9,
            "tier": 3,
        }])
        assert result.reached_consensus is True
        assert result.quorum_score == 1.0
        assert result.total_models == 1

    def test_unanimous_agreement(self, engine):
        """All responses agree → consensus with high quorum."""
        responses = [
            {
                "text": "Use PostgreSQL for the database layer with proper indexing and connection pooling",
                "model": "gpt-4o",
                "provider": "openai",
                "confidence": 0.85,
                "tier": 3,
            },
            {
                "text": "PostgreSQL is the right choice for the database with indexing optimization and connection pooling",
                "model": "claude-sonnet-4",
                "provider": "anthropic",
                "confidence": 0.9,
                "tier": 3,
            },
            {
                "text": "I recommend PostgreSQL as your database engine with proper connection pooling and indexing",
                "model": "gemini-2.5-pro",
                "provider": "google",
                "confidence": 0.88,
                "tier": 4,
            },
        ]
        result = engine.evaluate(responses)
        assert result.reached_consensus is True
        assert result.quorum_score >= 0.67
        assert len(result.dissenting_views) == 0

    def test_split_council(self):
        """Two models agree, one disagrees → check quorum."""
        engine = BFTConsensus(agreement_threshold=0.35, quorum_fraction=0.66)  # Slightly below 2/3 for 3-model case
        responses = [
            {
                "text": "Use PostgreSQL for relational data storage with ACID compliance and indexing",
                "model": "gpt-4o",
                "provider": "openai",
                "confidence": 0.85,
                "tier": 3,
            },
            {
                "text": "PostgreSQL is ideal for relational data with ACID transactions and indexing",
                "model": "claude-sonnet-4",
                "provider": "anthropic",
                "confidence": 0.9,
                "tier": 3,
            },
            {
                "text": "MongoDB is better for flexible schema evolution and horizontal scaling",
                "model": "gemini-2.5-flash",
                "provider": "google",
                "confidence": 0.7,
                "tier": 2,
            },
        ]
        result = engine.evaluate(responses)
        # 2/3 agree on PostgreSQL → consensus
        assert result.reached_consensus is True
        assert result.quorum_score >= 0.66
        assert len(result.dissenting_views) >= 1
        assert "MongoDB" in result.dissenting_views[0]

    def test_total_disagreement(self, engine):
        """Three completely different answers → no consensus."""
        responses = [
            {
                "text": "Implement real-time synchronization using WebSocket protocol connections",
                "model": "gpt-4o",
                "provider": "openai",
                "confidence": 0.7,
                "tier": 3,
            },
            {
                "text": "Database migration scripts should follow sequential versioning patterns",
                "model": "claude-sonnet-4",
                "provider": "anthropic",
                "confidence": 0.6,
                "tier": 3,
            },
            {
                "text": "Container orchestration with Kubernetes deployment manifests",
                "model": "gemini-2.5-flash",
                "provider": "google",
                "confidence": 0.5,
                "tier": 2,
            },
        ]
        result = engine.evaluate(responses)
        # All different topics → no consensus
        assert result.quorum_score < 0.67 or len(result.cluster_sizes) > 1

    def test_agreement_matrix_shape(self, engine):
        """Agreement matrix should be NxN."""
        responses = [
            {"text": "answer one", "model": "m1", "provider": "p1", "confidence": 0.8, "tier": 2},
            {"text": "answer two", "model": "m2", "provider": "p2", "confidence": 0.7, "tier": 2},
            {"text": "answer three", "model": "m3", "provider": "p3", "confidence": 0.6, "tier": 2},
        ]
        result = engine.evaluate(responses)
        assert len(result.agreement_matrix) == 3
        assert all(len(row) == 3 for row in result.agreement_matrix)
        # Diagonal should be 1.0
        for i in range(3):
            assert result.agreement_matrix[i][i] == 1.0

    def test_argument_graph_populated(self, engine):
        """Argument graph should have one node per response."""
        responses = [
            {"text": "Use caching", "model": "m1", "provider": "openai", "confidence": 0.8, "tier": 3},
            {"text": "Add indexing", "model": "m2", "provider": "anthropic", "confidence": 0.7, "tier": 2},
        ]
        result = engine.evaluate(responses)
        assert len(result.argument_graph) == 2
        assert result.argument_graph[0].source_model == "m1"
        assert result.argument_graph[1].source_model == "m2"

    def test_confidence_weighted_score(self, engine):
        """Higher-tier models should have more voting weight."""
        responses = [
            {"text": "PostgreSQL database with indexing optimization",
             "model": "o3", "provider": "openai", "confidence": 0.95, "tier": 4},
            {"text": "PostgreSQL is best for database with proper indexing",
             "model": "claude-opus-4", "provider": "anthropic", "confidence": 0.9, "tier": 4},
            {"text": "Use SQLite instead for simplicity",
             "model": "gpt-4o-mini", "provider": "openai", "confidence": 0.5, "tier": 1},
        ]
        result = engine.evaluate(responses)
        # High-tier models agree → weighted score should be high
        assert result.confidence_weighted_score > 0.5

    def test_dissent_score(self, engine):
        """Dissent score should be 1 - quorum_score."""
        responses = [
            {"text": "answer alpha", "model": "m1", "provider": "p1", "confidence": 0.8, "tier": 2},
        ]
        result = engine.evaluate(responses)
        assert result.dissent_score == pytest.approx(1.0 - result.quorum_score, abs=0.01)
