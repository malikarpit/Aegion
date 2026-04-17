"""
Drift Detection Service (Sentinel).

Detects code changes that do not have a corresponding Decision Intent.
Phase 8: Baseline implementation using git diff.
"""

import subprocess
import os
from typing import List, Dict, Optional
from pydantic import BaseModel

from ...core.logging import logger
from ...core.config import settings

class DriftAlert(BaseModel):
    file_path: str
    severity: str
    message: str
    diff_stat: str

class DriftDetector:
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def _run_git(self, args: List[str]) -> str:
        """Run a git command in the repo (W6.2: graceful fallback)."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            return result.stdout.strip()
        except FileNotFoundError:
            logger.warning("Git binary not found — drift detection unavailable")
            return ""
        except subprocess.TimeoutExpired:
            logger.warning("Git command timed out — drift detection degraded")
            return ""
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {e}")
            return ""
        except OSError as e:
            logger.warning(f"Git command OS error: {e}")
            return ""

    def _is_git_available(self) -> bool:
        """Check if git is available and repo is valid (W6.2)."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.repo_path,
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return False

    def check_drift(self, active_session_files: List[str]) -> List[DriftAlert]:
        """
        Check for modified files that are NOT part of the active session context.

        W6.2: Returns empty list with warning when git is unavailable
        instead of crashing.
        """
        if not self._is_git_available():
            logger.warning(
                "Drift detection skipped: git not available or not in a git repo"
            )
            return []

        # Get list of modified files (staged + unstaged)
        modified_files = []
        
        # Unstaged
        unstaged = self._run_git(["diff", "--name-only"])
        if unstaged:
            modified_files.extend(unstaged.splitlines())
            
        # Staged
        staged = self._run_git(["diff", "--name-only", "--cached"])
        if staged:
            modified_files.extend(staged.splitlines())
            
        # Deduplicate
        modified_files = list(set(modified_files))
        
        alerts = []
        for file_path in modified_files:
            # If file is not in active session (and not ignored), it's drift
            if file_path not in active_session_files:
                # Check if critical
                severity = "low"
                if "config" in file_path or "security" in file_path or "auth" in file_path:
                    severity = "high"
                
                # Get diff stat
                diff_stat = self._run_git(["diff", "--stat", file_path])
                
                alerts.append(DriftAlert(
                    file_path=file_path,
                    severity=severity,
                    message=f"File modified outside of active thought session: {file_path}",
                    diff_stat=diff_stat
                ))
                
        return alerts

# Singleton
_detector = None

def get_drift_detector() -> DriftDetector:
    global _detector
    if not _detector:
        # Assuming run from root or finding root
        _detector = DriftDetector(os.getcwd())
    return _detector
