"""
Aegion Memory Extractor Service.

Automatically extracts memory entries from agent runs, decisions, and proposals.

Feature: Auto-generated memory from agent actions.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
import re

from ..core.logging import logger


class MemoryExtractor:
    """
    Extracts knowledge patterns from agent activity and converts
    them into memory entries for future agent context.
    """

    # Patterns that indicate memorable information
    EXTRACT_PATTERNS = [
        {
            "name": "preference",
            "pattern": r"(?:prefer|always|never|should|must)\s+(.+?)(?:\.|$)",
            "tags": ["preference", "auto"],
            "confidence": 0.7,
        },
        {
            "name": "convention",
            "pattern": r"(?:convention|standard|pattern|practice)[\s:]+(.+?)(?:\.|$)",
            "tags": ["convention", "auto"],
            "confidence": 0.8,
        },
        {
            "name": "architecture",
            "pattern": r"(?:architecture|design|structure|layer|module)[\s:]+(.+?)(?:\.|$)",
            "tags": ["architecture", "auto"],
            "confidence": 0.75,
        },
        {
            "name": "dependency",
            "pattern": r"(?:depends on|requires|uses|imports)\s+(.+?)(?:\.|$)",
            "tags": ["dependency", "auto"],
            "confidence": 0.65,
        },
        {
            "name": "warning",
            "pattern": r"(?:warning|caution|careful|avoid|don't)\s+(.+?)(?:\.|$)",
            "tags": ["warning", "auto"],
            "confidence": 0.7,
        },
    ]

    def extract_from_run(
        self,
        task_id: str,
        run_result: str,
        run_logs: List[str],
        workspace_id: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Extract memory candidates from a task run's results and logs.

        Returns a list of memory entry dicts ready for storage.
        """
        entries = []
        full_text = f"{run_result}\n" + "\n".join(run_logs)

        for pattern_def in self.EXTRACT_PATTERNS:
            matches = re.findall(pattern_def["pattern"], full_text, re.IGNORECASE)
            for match in matches:
                match = match.strip()
                if len(match) < 10 or len(match) > 500:
                    continue  # Skip too short or too long

                entry = {
                    "memory_id": str(uuid.uuid4()),
                    "key": f"auto:{pattern_def['name']}:{match[:50]}",
                    "value": match,
                    "scope": "repository",
                    "scope_id": workspace_id,
                    "tags": pattern_def["tags"],
                    "source": f"auto:run:{task_id}",
                    "confidence": pattern_def["confidence"],
                    "created_by": "system",
                    "created_at": datetime.now(timezone.utc),
                }
                entries.append(entry)

        if entries:
            logger.info(f"Extracted {len(entries)} memory candidates from run on task {task_id}")

        return entries

    def extract_from_decision(
        self,
        decision_id: str,
        decision_text: str,
        rationale: str,
        workspace_id: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Extract memorable patterns from a governance decision.
        """
        entries = []

        # Decisions always get stored as high-confidence memory
        if rationale and len(rationale) > 20:
            entries.append({
                "memory_id": str(uuid.uuid4()),
                "key": f"decision:{decision_id[:8]}",
                "value": rationale,
                "scope": "repository",
                "scope_id": workspace_id,
                "tags": ["decision", "auto", "rationale"],
                "source": f"auto:decision:{decision_id}",
                "confidence": 0.9,
                "created_by": "system",
                "created_at": datetime.now(timezone.utc),
            })

        # Also extract patterns from decision text
        for pattern_def in self.EXTRACT_PATTERNS:
            matches = re.findall(pattern_def["pattern"], decision_text, re.IGNORECASE)
            for match in matches:
                match = match.strip()
                if len(match) < 10:
                    continue

                entries.append({
                    "memory_id": str(uuid.uuid4()),
                    "key": f"auto:{pattern_def['name']}:{match[:50]}",
                    "value": match,
                    "scope": "repository",
                    "scope_id": workspace_id,
                    "tags": pattern_def["tags"] + ["from_decision"],
                    "source": f"auto:decision:{decision_id}",
                    "confidence": pattern_def["confidence"] + 0.1,  # Boost for decision context
                    "created_by": "system",
                    "created_at": datetime.now(timezone.utc),
                })

        if entries:
            logger.info(f"Extracted {len(entries)} memory candidates from decision {decision_id}")

        return entries

    def extract_from_proposal(
        self,
        proposal_id: str,
        reasoning_summary: str,
        alternatives_rejected: List[str],
        workspace_id: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Extract learned patterns from an approved proposal's reasoning.
        """
        entries = []

        # Record rejected alternatives as "don't do this" memory
        for alt in alternatives_rejected:
            if len(alt) > 10:
                entries.append({
                    "memory_id": str(uuid.uuid4()),
                    "key": f"rejected:{alt[:50]}",
                    "value": f"Rejected alternative: {alt}",
                    "scope": "repository",
                    "scope_id": workspace_id,
                    "tags": ["rejected_alternative", "auto"],
                    "source": f"auto:proposal:{proposal_id}",
                    "confidence": 0.6,
                    "created_by": "system",
                    "created_at": datetime.now(timezone.utc),
                })

        return entries


# Singleton
_extractor: Optional[MemoryExtractor] = None


def get_memory_extractor() -> MemoryExtractor:
    global _extractor
    if _extractor is None:
        _extractor = MemoryExtractor()
    return _extractor
