"""
Aegion Thought-Commit Protocol Contracts.

Defines the core states and link types for the "Git for Thoughts" layer.
This contract is shared between the backend domain logic and API models.
"""

from enum import Enum


class ThoughtState(str, Enum):
    """
    Lifecycle state of a Thought Artifact.
    
    States:
      - DRAFT: Mutable, work-in-progress.
      - SEALED: Immutable, cryptographically signed, ready for linking.
      - SUPERSEDED: Valid but replaced by a newer line of reasoning.
      - ORPHANED: Warning state; linked code has changed without updated reasoning.
    """
    DRAFT = "draft"
    SEALED = "sealed"
    SUPERSEDED = "superseded"
    ORPHANED = "orphaned"


class ThoughtLinkType(str, Enum):
    """
    Semantics of the link between a Thought Artifact and other entities.
    """
    EXPLAINS = "explains"          # Thought -> Commit (Standard reasoning)
    SUPERSEDES = "supersedes"      # Thought -> Thought (Evolution of reasoning)
    REFERENCES = "references"      # Thought -> Evidence/Context
    DERIVES_FROM = "derives_from"  # Thought -> Proposal/Council (Upstream provenance)
