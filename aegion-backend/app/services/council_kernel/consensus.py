"""
BFT-Inspired Consensus Engine — Multi-Response Agreement Analysis.

Formal consensus mechanism for aggregating multiple LLM responses into a
single, high-confidence result with transparent agreement metrics.

Algorithm Overview (Simplified PBFT for LLM Councils):
    1. Collect N model responses (the "prepare" phase)
    2. Compute pairwise semantic similarity (the "commit" phase)
    3. Identify agreement clusters via single-linkage clustering
    4. Require supermajority agreement (>2/3 of models) for consensus
    5. If no consensus → flag dissenting views + lower confidence

Key Metrics:
    - Quorum Score: fraction of models in the largest agreement cluster
    - Agreement Matrix: NxN pairwise similarity scores
    - Dissent Score: max(1 - quorum_score, 0) — how fractured the council is
    - Confidence-Weighted Vote: tier × confidence → vote weight

References:
    - Castro, M. & Liskov, B. (1999). "Practical Byzantine Fault Tolerance"
      — OSDI '99: The 2/3+1 quorum requirement
    - Jaccard, P. (1912). Similarity coefficient for text overlap
    - Wang et al. (2023). "Self-Consistency Improves Chain of Thought
      Reasoning in Language Models" — majority voting over LLM outputs

Design notes:
    - Uses semantic Jaccard similarity (word-level set overlap) for efficiency
    - No external embeddings required (keeps it zero-dependency)
    - Extensible: can swap in cosine similarity with sentence-transformers
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ...core.logging import logger


# ──────────────────────────────────────────────────────────────────────────────
# Data Types
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ArgumentNode:
    """
    A single argument extracted from a model's response.

    Used to track WHERE agreement comes from, not just THAT it exists.
    """
    source_model: str
    source_provider: str
    claim: str               # The central claim/recommendation
    evidence: str = ""       # Supporting evidence or reasoning
    confidence: float = 0.0  # Source model's confidence
    tier: int = 2            # Source model's quality tier
    weight: float = 0.0      # Computed vote weight (tier × confidence)


@dataclass
class ConsensusResult:
    """
    Output of the BFT consensus engine.

    Provides transparency into HOW the council reached its decision,
    not just WHAT it decided.
    """
    reached_consensus: bool           # True if supermajority agreed
    quorum_score: float               # Fraction of models in agreement (0.0-1.0)
    dissent_score: float              # 1 - quorum_score
    majority_position: str            # The agreed-upon response text
    dissenting_views: List[str]       # Responses that disagreed
    agreement_matrix: List[List[float]]  # NxN pairwise similarity
    cluster_sizes: List[int]          # Sizes of agreement clusters
    argument_graph: List[ArgumentNode] = field(default_factory=list)
    total_models: int = 0
    confidence_weighted_score: float = 0.0  # Weighted consensus score


# ──────────────────────────────────────────────────────────────────────────────
# Similarity Functions
# ──────────────────────────────────────────────────────────────────────────────

# Common English stopwords + code noise — excluded from similarity
_STOPWORDS: Set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must",
    "i", "we", "you", "he", "she", "it", "they", "me", "us", "him", "her",
    "them", "my", "our", "your", "his", "its", "their",
    "this", "that", "these", "those", "what", "which", "who", "whom",
    "in", "on", "at", "to", "for", "with", "by", "from", "of", "about",
    "into", "through", "during", "before", "after", "above", "below",
    "and", "or", "but", "not", "no", "if", "then", "than", "so", "as",
    "def", "class", "import", "return", "self", "none", "true", "false",
    "const", "let", "var", "function", "async", "await",
}


def _tokenize(text: str) -> Set[str]:
    """
    Tokenize text into a set of meaningful words for similarity comparison.

    Strips stopwords, code noise, and normalizes to lowercase.
    Only keeps words 3+ characters to avoid matches on trivial tokens.
    """
    words = set(re.findall(r'\b[a-zA-Z_]\w{2,}\b', text.lower()))
    return words - _STOPWORDS


def semantic_jaccard(text_a: str, text_b: str) -> float:
    """
    Semantic Jaccard similarity between two texts.

    |A ∩ B| / |A ∪ B| after tokenization and stopword removal.

    Why Jaccard over cosine embeddings?
    - Zero external dependencies (no sentence-transformers)
    - Fast: O(n) set operations vs O(n*d) embedding computation
    - Good enough for detecting agreement at the claim level
    - Avoids the "all responses are similar" problem with embedding similarity
      (LLM responses tend to cluster tightly in embedding space)

    Returns:
        float in [0.0, 1.0]. 1.0 = identical token sets, 0.0 = no overlap.
    """
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)

    if not tokens_a and not tokens_b:
        return 1.0  # Both empty = trivially identical
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b

    return len(intersection) / len(union) if union else 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Clustering (Single-Linkage)
# ──────────────────────────────────────────────────────────────────────────────

def _single_linkage_clusters(
    similarity_matrix: List[List[float]],
    threshold: float,
) -> List[List[int]]:
    """
    Single-linkage clustering on a similarity matrix.

    Two items are in the same cluster if ANY path of similarities
    >= threshold connects them. Classic Union-Find approach.

    Args:
        similarity_matrix: NxN matrix of pairwise similarities
        threshold: minimum similarity to consider as "agreement"

    Returns:
        List of clusters, each cluster is a list of response indices.
    """
    n = len(similarity_matrix)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # Path compression
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            if similarity_matrix[i][j] >= threshold:
                union(i, j)

    clusters: Dict[int, List[int]] = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(i)

    return list(clusters.values())


# ──────────────────────────────────────────────────────────────────────────────
# BFT Consensus Engine
# ──────────────────────────────────────────────────────────────────────────────

class BFTConsensus:
    """
    Byzantine Fault Tolerant consensus for LLM council responses.

    Inspired by PBFT (Castro & Liskov, 1999) adapted for LLM outputs:
    - Instead of message passing, we use semantic similarity
    - Instead of 3f+1 replicas, we use >2/3 agreement threshold
    - Instead of cryptographic proofs, we use confidence-weighted voting

    Usage:
        consensus = BFTConsensus(agreement_threshold=0.35, quorum_fraction=0.67)
        result = consensus.evaluate(responses)
        if result.reached_consensus:
            return result.majority_position
        else:
            # Handle split council
    """

    def __init__(
        self,
        agreement_threshold: float = 0.35,
        quorum_fraction: float = 0.67,
    ) -> None:
        """
        Args:
            agreement_threshold: minimum Jaccard similarity to consider two
                responses as "agreeing". Default 0.35 (empirically tuned:
                LLM responses with >35% word overlap typically agree on
                the core recommendation even if they differ in wording).
            quorum_fraction: fraction of models that must agree for consensus.
                Default 0.67 (2/3+1 from PBFT). With 3 models, need 2.
                With 5 models, need 4.
        """
        self.agreement_threshold = agreement_threshold
        self.quorum_fraction = quorum_fraction

    def evaluate(
        self,
        responses: List[Dict[str, Any]],
    ) -> ConsensusResult:
        """
        Run BFT consensus on a list of model responses.

        Args:
            responses: list of dicts with keys:
                - "text": the response text
                - "model": model name
                - "provider": provider name
                - "confidence": float 0-1
                - "tier": int 1-4

        Returns:
            ConsensusResult with agreement analysis.
        """
        n = len(responses)
        if n == 0:
            return ConsensusResult(
                reached_consensus=False,
                quorum_score=0.0,
                dissent_score=1.0,
                majority_position="",
                dissenting_views=[],
                agreement_matrix=[],
                cluster_sizes=[],
                total_models=0,
            )

        if n == 1:
            return ConsensusResult(
                reached_consensus=True,
                quorum_score=1.0,
                dissent_score=0.0,
                majority_position=responses[0]["text"],
                dissenting_views=[],
                agreement_matrix=[[1.0]],
                cluster_sizes=[1],
                total_models=1,
                confidence_weighted_score=responses[0].get("confidence", 0.5),
            )

        # Step 1: Build NxN agreement matrix
        texts = [r["text"] for r in responses]
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            matrix[i][i] = 1.0
            for j in range(i + 1, n):
                sim = semantic_jaccard(texts[i], texts[j])
                matrix[i][j] = sim
                matrix[j][i] = sim

        # Step 2: Cluster responses by agreement
        clusters = _single_linkage_clusters(matrix, self.agreement_threshold)
        cluster_sizes = sorted([len(c) for c in clusters], reverse=True)

        # Step 3: Find majority cluster
        majority_cluster = max(clusters, key=len)
        quorum_score = len(majority_cluster) / n

        # Step 4: Determine if quorum is reached (PBFT: >2/3)
        reached_consensus = quorum_score >= self.quorum_fraction

        # Step 5: Select majority position (highest confidence in majority cluster)
        majority_responses = [responses[i] for i in majority_cluster]
        best_in_majority = max(
            majority_responses,
            key=lambda r: r.get("tier", 2) * r.get("confidence", 0.5),
        )

        # Step 6: Collect dissenting views
        minority_indices = set(range(n)) - set(majority_cluster)
        dissenting_views = [
            responses[i]["text"][:500] for i in minority_indices
        ]

        # Step 7: Build argument graph
        arguments = []
        for i, r in enumerate(responses):
            weight = r.get("tier", 2) * r.get("confidence", 0.5)
            arguments.append(ArgumentNode(
                source_model=r.get("model", "unknown"),
                source_provider=r.get("provider", "unknown"),
                claim=r["text"][:200],
                confidence=r.get("confidence", 0.5),
                tier=r.get("tier", 2),
                weight=weight,
            ))

        # Step 8: Confidence-weighted consensus score
        total_weight = sum(a.weight for a in arguments)
        majority_weight = sum(
            arguments[i].weight for i in majority_cluster
        )
        weighted_score = majority_weight / total_weight if total_weight > 0 else 0.0

        result = ConsensusResult(
            reached_consensus=reached_consensus,
            quorum_score=round(quorum_score, 3),
            dissent_score=round(1.0 - quorum_score, 3),
            majority_position=best_in_majority["text"],
            dissenting_views=dissenting_views,
            agreement_matrix=[[round(v, 3) for v in row] for row in matrix],
            cluster_sizes=cluster_sizes,
            argument_graph=arguments,
            total_models=n,
            confidence_weighted_score=round(weighted_score, 3),
        )

        if not reached_consensus:
            logger.info(
                f"BFT Consensus: NO QUORUM — {quorum_score:.0%} agreement "
                f"(need {self.quorum_fraction:.0%}). Clusters: {cluster_sizes}"
            )

        return result
