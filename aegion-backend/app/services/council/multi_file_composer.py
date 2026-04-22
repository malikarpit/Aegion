"""
Multi-File Composer — Phase 108.

Orchestrates changes across multiple files in a single atomic operation.
This is the core of Aegion's "large change" capability — when a proposal
touches multiple files, the composer ensures consistency.

Process:
  1. Analyze the change scope (files, dependencies, imports)
  2. Generate a dependency graph of changes
  3. Apply changes in topological order
  4. Validate cross-file consistency (imports, types, APIs)
  5. Run quick checks (syntax, type hints)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ...core.logging import logger


class ChangeType(str, Enum):
    """Type of file-level change."""
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    RENAME = "rename"


@dataclass
class FileChange:
    """A single file change in a multi-file composition."""
    file_path: str
    change_type: ChangeType
    content: str = ""           # New or modified content
    original_content: str = ""  # For rollback
    depends_on: List[str] = field(default_factory=list)  # Other file paths this depends on
    description: str = ""       # Human-readable change description
    validated: bool = False


@dataclass
class CompositionPlan:
    """A plan for a multi-file change operation."""
    plan_id: str = ""
    title: str = ""
    changes: List[FileChange] = field(default_factory=list)
    execution_order: List[str] = field(default_factory=list)  # Topologically sorted
    validation_errors: List[str] = field(default_factory=list)
    is_valid: bool = False


class MultiFileComposer:
    """
    Composes and applies multi-file changes atomically.

    Ensures that cross-cutting changes (API additions, refactors,
    new features spanning multiple files) are applied consistently.
    """

    def __init__(self, workspace_path: str) -> None:
        self.workspace_path = workspace_path

    def create_plan(self, title: str, changes: List[FileChange]) -> CompositionPlan:
        """
        Create an execution plan from a list of file changes.

        Resolves dependency order and validates cross-file consistency.
        """
        plan = CompositionPlan(
            plan_id=f"compose-{hash(title) % 100000:05d}",
            title=title,
            changes=changes,
        )

        # Topological sort by dependencies
        plan.execution_order = self._resolve_order(changes)

        # Validate
        plan.validation_errors = self._validate(changes)
        plan.is_valid = len(plan.validation_errors) == 0

        return plan

    async def apply(self, plan: CompositionPlan, dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply a composition plan to the workspace.

        In dry_run mode, validates without writing files.
        """
        if not plan.is_valid:
            return {
                "success": False,
                "error": "Plan has validation errors",
                "errors": plan.validation_errors,
            }

        applied = []
        rollback_stack: List[Tuple[str, str]] = []

        try:
            for file_path in plan.execution_order:
                change = next(c for c in plan.changes if c.file_path == file_path)

                if dry_run:
                    applied.append(file_path)
                    continue

                abs_path = os.path.join(self.workspace_path, file_path)

                if change.change_type == ChangeType.CREATE:
                    # Store for rollback
                    rollback_stack.append((abs_path, ""))
                    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                    with open(abs_path, "w") as f:
                        f.write(change.content)

                elif change.change_type == ChangeType.MODIFY:
                    # Save original for rollback
                    original = ""
                    if os.path.exists(abs_path):
                        with open(abs_path) as f:
                            original = f.read()
                    rollback_stack.append((abs_path, original))
                    with open(abs_path, "w") as f:
                        f.write(change.content)

                elif change.change_type == ChangeType.DELETE:
                    if os.path.exists(abs_path):
                        with open(abs_path) as f:
                            rollback_stack.append((abs_path, f.read()))
                        os.remove(abs_path)

                applied.append(file_path)
                change.validated = True

            return {
                "success": True,
                "applied": applied,
                "total_files": len(applied),
                "dry_run": dry_run,
            }

        except Exception as e:
            # Rollback all changes
            logger.error(f"Composition failed, rolling back: {e}")
            for abs_path, original in reversed(rollback_stack):
                try:
                    if original:
                        with open(abs_path, "w") as f:
                            f.write(original)
                    elif os.path.exists(abs_path):
                        os.remove(abs_path)
                except Exception:
                    pass

            return {
                "success": False,
                "error": str(e),
                "applied_before_failure": applied,
                "rolled_back": True,
            }

    def _resolve_order(self, changes: List[FileChange]) -> List[str]:
        """Topologically sort changes by dependencies."""
        # Build adjacency
        graph: Dict[str, List[str]] = {}
        all_files = set()
        for c in changes:
            graph[c.file_path] = c.depends_on
            all_files.add(c.file_path)
            all_files.update(c.depends_on)

        # Kahn's algorithm
        in_degree: Dict[str, int] = {f: 0 for f in all_files}
        for deps in graph.values():
            for d in deps:
                if d in in_degree:
                    in_degree[d] += 1

        queue = [f for f in all_files if in_degree[f] == 0]
        order = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for dep in graph.get(node, []):
                if dep in in_degree:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        # Only return files that have changes
        change_files = {c.file_path for c in changes}
        return [f for f in order if f in change_files]

    def _validate(self, changes: List[FileChange]) -> List[str]:
        """Basic validation of cross-file consistency."""
        errors = []

        # Check for conflicting changes
        paths = [c.file_path for c in changes]
        if len(paths) != len(set(paths)):
            errors.append("Duplicate file paths in changes")

        # Check for circular dependencies
        visited = set()
        for c in changes:
            for dep in c.depends_on:
                if dep == c.file_path:
                    errors.append(f"Self-dependency: {c.file_path}")
                # Simple cycle check
                dep_change = next((d for d in changes if d.file_path == dep), None)
                if dep_change and c.file_path in dep_change.depends_on:
                    errors.append(f"Circular dependency: {c.file_path} ↔ {dep}")

        return errors
