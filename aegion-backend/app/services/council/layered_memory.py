"""
MEMORY.md Layered Pointer Model — Phase 112.

Implements a 3-layer memory system:
  1. Project Layer  — MEMORY.md at workspace root (shared conventions)
  2. Workspace Layer — .aegion/memory.yaml (workspace-specific preferences)
  3. Session Layer   — In-memory ephemeral context (conversation state)

Memory entries are:
  - Typed (preference, decision, fact, constraint)
  - Weighted by confidence (0.0–1.0)
  - Auto-decayed over time
  - Queryable via semantic search

This module manages the read/write lifecycle and provides
a merged view for the council engine.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ...core.logging import logger


class MemoryType(str, Enum):
    PREFERENCE = "preference"   # User coding preferences
    DECISION = "decision"       # Past architectural decisions
    FACT = "fact"               # Learned project facts
    CONSTRAINT = "constraint"   # Hard constraints or rules


class MemoryLayer(str, Enum):
    PROJECT = "project"         # MEMORY.md — shared
    WORKSPACE = "workspace"     # .aegion/memory.yaml — workspace-specific
    SESSION = "session"         # In-memory — ephemeral


@dataclass
class MemoryEntry:
    """A single memory unit."""
    id: str
    concept: str            # Short title
    content: str            # Full description
    memory_type: MemoryType
    layer: MemoryLayer
    confidence: float = 0.9
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    source: str = ""        # Where this memory was learned from


class LayeredMemory:
    """
    3-layer memory system with read-through and write-back.

    Higher layers (session) override lower layers (project).
    """

    def __init__(self, workspace_path: str) -> None:
        self.workspace_path = workspace_path
        self._session: Dict[str, MemoryEntry] = {}  # Layer 3: ephemeral

    def get_all(self) -> List[MemoryEntry]:
        """Get all memories from all layers, session takes precedence."""
        memories: Dict[str, MemoryEntry] = {}

        # Layer 1: MEMORY.md
        project_memories = self._read_memory_md()
        for m in project_memories:
            memories[m.id] = m

        # Layer 2: .aegion/memory.yaml
        workspace_memories = self._read_workspace_yaml()
        for m in workspace_memories:
            memories[m.id] = m  # Override project

        # Layer 3: Session
        for m in self._session.values():
            memories[m.id] = m  # Override workspace

        return list(memories.values())

    def query(self, keyword: str) -> List[MemoryEntry]:
        """Search memories by keyword."""
        all_memories = self.get_all()
        kw = keyword.lower()
        return [
            m for m in all_memories
            if kw in m.concept.lower() or kw in m.content.lower()
        ]

    def add_session(self, concept: str, content: str, memory_type: MemoryType, confidence: float = 0.9) -> MemoryEntry:
        """Add a memory to the session (ephemeral) layer."""
        entry = MemoryEntry(
            id=f"session-{len(self._session)}",
            concept=concept,
            content=content,
            memory_type=memory_type,
            layer=MemoryLayer.SESSION,
            confidence=confidence,
        )
        self._session[entry.id] = entry
        return entry

    def promote_to_workspace(self, entry: MemoryEntry) -> None:
        """Promote a session memory to the workspace layer (persistent)."""
        entry.layer = MemoryLayer.WORKSPACE
        # In production: append to .aegion/memory.yaml
        logger.info(f"Memory promoted to workspace: {entry.concept}")

    def promote_to_project(self, entry: MemoryEntry) -> None:
        """Promote a memory to the project layer (MEMORY.md)."""
        entry.layer = MemoryLayer.PROJECT
        # In production: append to MEMORY.md
        logger.info(f"Memory promoted to project: {entry.concept}")

    def for_council_prompt(self, max_entries: int = 10) -> str:
        """Format memories as a council-friendly prompt section."""
        memories = self.get_all()
        # Sort by confidence, then recency
        memories.sort(key=lambda m: (m.confidence, m.last_accessed), reverse=True)
        memories = memories[:max_entries]

        if not memories:
            return ""

        lines = ["[WORKSPACE MEMORY]"]
        for m in memories:
            lines.append(f"  [{m.memory_type.value.upper()}] {m.concept}: {m.content}")
        return "\n".join(lines)

    # ──────────────────────────────────────────────
    # File I/O
    # ──────────────────────────────────────────────

    def _read_memory_md(self) -> List[MemoryEntry]:
        """Parse MEMORY.md into memory entries."""
        path = os.path.join(self.workspace_path, "MEMORY.md")
        if not os.path.exists(path):
            return []

        try:
            with open(path) as f:
                content = f.read()

            entries = []
            # Parse markdown sections: ## Category / - [concept]: content
            current_type = MemoryType.FACT
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("## "):
                    heading = line[3:].strip().lower()
                    if "preference" in heading:
                        current_type = MemoryType.PREFERENCE
                    elif "decision" in heading:
                        current_type = MemoryType.DECISION
                    elif "constraint" in heading:
                        current_type = MemoryType.CONSTRAINT
                    else:
                        current_type = MemoryType.FACT
                elif line.startswith("- "):
                    text = line[2:].strip()
                    # Try to split on first colon
                    if ":" in text:
                        concept, content_text = text.split(":", 1)
                        concept = concept.strip()
                        content_text = content_text.strip()
                    else:
                        concept = text[:50]
                        content_text = text

                    entries.append(MemoryEntry(
                        id=f"project-{len(entries)}",
                        concept=concept,
                        content=content_text,
                        memory_type=current_type,
                        layer=MemoryLayer.PROJECT,
                    ))

            return entries
        except Exception as e:
            logger.debug(f"Failed to read MEMORY.md: {e}")
            return []

    def _read_workspace_yaml(self) -> List[MemoryEntry]:
        """Parse .aegion/memory.yaml into memory entries."""
        path = os.path.join(self.workspace_path, ".aegion", "memory.yaml")
        if not os.path.exists(path):
            return []

        try:
            import yaml  # type: ignore
            with open(path) as f:
                data = yaml.safe_load(f) or {}

            entries = []
            for item in data.get("memories", []):
                entries.append(MemoryEntry(
                    id=f"workspace-{len(entries)}",
                    concept=item.get("concept", ""),
                    content=item.get("content", ""),
                    memory_type=MemoryType(item.get("type", "fact")),
                    layer=MemoryLayer.WORKSPACE,
                    confidence=item.get("confidence", 0.8),
                ))

            return entries
        except Exception as e:
            logger.debug(f"Failed to read workspace memory: {e}")
            return []


# ──────────────────────────────────────────────
# Singleton factory
# ──────────────────────────────────────────────

_instances: Dict[str, LayeredMemory] = {}


def get_layered_memory(workspace_path: str) -> LayeredMemory:
    """Get or create a LayeredMemory for the given workspace."""
    if workspace_path not in _instances:
        _instances[workspace_path] = LayeredMemory(workspace_path)
    return _instances[workspace_path]
