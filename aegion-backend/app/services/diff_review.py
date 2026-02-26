"""
Diff Review System — Phase 35: AI-Powered Code Review.

Parses git diffs, sends hunks to the ACK council for security and quality review,
and produces per-file and per-hunk risk assessments.

Features:
  - Unified diff parsing into structured hunks
  - Per-hunk risk scoring via Sentinel pattern engine
  - Full-diff AI review via ACK PARENT council
  - Summarized review with actionable suggestions
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..core.logging import logger


class DiffHunk:
    """A single hunk from a unified diff."""

    def __init__(
        self,
        file_path: str,
        old_start: int,
        old_count: int,
        new_start: int,
        new_count: int,
        content: str,
    ) -> None:
        self.file_path = file_path
        self.old_start = old_start
        self.old_count = old_count
        self.new_start = new_start
        self.new_count = new_count
        self.content = content
        self.additions = sum(1 for line in content.splitlines() if line.startswith("+") and not line.startswith("+++"))
        self.deletions = sum(1 for line in content.splitlines() if line.startswith("-") and not line.startswith("---"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "old_start": self.old_start,
            "new_start": self.new_start,
            "additions": self.additions,
            "deletions": self.deletions,
            "content": self.content[:2000],  # Cap for API response
        }


class DiffReviewEngine:
    """
    Reviews git diffs using a combination of pattern analysis and AI council.
    """

    _HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")

    def parse_diff(self, diff_text: str) -> List[DiffHunk]:
        """Parse a unified diff into structured hunks."""
        hunks = []
        current_file = "unknown"
        current_hunk_lines: List[str] = []
        current_header = None

        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                # Flush previous hunk
                if current_header and current_hunk_lines:
                    hunks.append(self._make_hunk(current_file, current_header, current_hunk_lines))
                    current_hunk_lines = []
                    current_header = None
                # Extract file path
                parts = line.split(" b/")
                if len(parts) > 1:
                    current_file = parts[1]

            elif line.startswith("+++") or line.startswith("---"):
                continue  # Skip file headers

            elif line.startswith("@@"):
                # Flush previous hunk
                if current_header and current_hunk_lines:
                    hunks.append(self._make_hunk(current_file, current_header, current_hunk_lines))

                match = self._HUNK_HEADER_RE.match(line)
                if match:
                    current_header = (
                        int(match.group(1)), int(match.group(2) or 1),
                        int(match.group(3)), int(match.group(4) or 1),
                    )
                current_hunk_lines = [line]
            else:
                current_hunk_lines.append(line)

        # Flush final hunk
        if current_header and current_hunk_lines:
            hunks.append(self._make_hunk(current_file, current_header, current_hunk_lines))

        return hunks

    def _make_hunk(self, file_path: str, header: tuple, lines: List[str]) -> DiffHunk:
        return DiffHunk(
            file_path=file_path,
            old_start=header[0], old_count=header[1],
            new_start=header[2], new_count=header[3],
            content="\n".join(lines),
        )

    async def review(
        self,
        workspace_id: str,
        diff_text: str,
        review_focus: str = "general",
    ) -> Dict[str, Any]:
        """
        Full diff review: parse → pattern scan → AI review.

        Args:
            workspace_id: Current workspace.
            diff_text:    Unified diff string.
            review_focus: "general", "security", "performance"

        Returns:
            files_changed, hunks, per_file_risks, ai_review, overall_risk
        """
        hunks = self.parse_diff(diff_text)

        # Group hunks by file
        files: Dict[str, List[DiffHunk]] = {}
        for hunk in hunks:
            files.setdefault(hunk.file_path, []).append(hunk)

        # Per-file risk scan
        from .sentinel.council_bridge import get_sentinel_bridge
        sentinel = get_sentinel_bridge()

        per_file_risks = []
        highest_risk = 0.0

        for file_path, file_hunks in files.items():
            combined_content = "\n".join(h.content for h in file_hunks)
            risk_result = await sentinel.analyze_change(
                workspace_id, {"content": combined_content, "files": [file_path]}
            )
            per_file_risks.append({
                "file": file_path,
                "risk_score": risk_result["risk_score"],
                "signals": risk_result["signals"],
                "hunks": len(file_hunks),
                "additions": sum(h.additions for h in file_hunks),
                "deletions": sum(h.deletions for h in file_hunks),
            })
            highest_risk = max(highest_risk, risk_result["risk_score"])

        # AI review via council (only for non-trivial diffs)
        ai_review = None
        if len(hunks) > 0 and highest_risk > 0.1:
            try:
                from .council_kernel.engine import get_council_engine
                from .council_kernel.types import CouncilType

                engine = get_council_engine()

                # Build review prompt
                focus_instructions = {
                    "security": "Focus on security vulnerabilities, injection risks, and data exposure.",
                    "performance": "Focus on performance regressions, N+1 queries, and memory leaks.",
                    "general": "Review for correctness, maintainability, and potential issues.",
                }
                diff_excerpt = diff_text[:6000]  # Cap for token limits

                result = await engine.consult(
                    workspace_id=workspace_id,
                    query=(
                        f"Review this code diff. {focus_instructions.get(review_focus, '')}\n\n"
                        f"```diff\n{diff_excerpt}\n```\n\n"
                        "Provide: 1) Summary of changes 2) Potential issues 3) Suggestions"
                    ),
                    council_type=CouncilType.PARENT if highest_risk > 0.5 else CouncilType.CHILD,
                )
                ai_review = {
                    "synthesis": result.synthesis,
                    "consensus": result.consensus_score,
                    "models_used": result.models_used,
                    "cost_usd": result.total_cost_usd,
                }
            except Exception as exc:
                logger.warning(f"AI diff review failed: {exc}")
                ai_review = {"error": str(exc)}

        return {
            "files_changed": len(files),
            "total_hunks": len(hunks),
            "total_additions": sum(h.additions for h in hunks),
            "total_deletions": sum(h.deletions for h in hunks),
            "per_file_risks": per_file_risks,
            "overall_risk_score": highest_risk,
            "recommended_tier": sentinel._recommend_tier(highest_risk),
            "ai_review": ai_review,
        }


# Singleton
_diff_review: Optional[DiffReviewEngine] = None

def get_diff_review() -> DiffReviewEngine:
    global _diff_review
    if _diff_review is None:
        _diff_review = DiffReviewEngine()
    return _diff_review
