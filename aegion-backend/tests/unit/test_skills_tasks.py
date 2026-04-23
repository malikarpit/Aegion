"""
Tests for Skills & Tasks — Phase R3.

Covers:
    SkillBlueprint model:
        - Field validation
        - Category enum values
        - Status enum values

    SkillLoader:
        - Frontmatter parsing
        - Load from nonexistent directory
        - Singleton

    Task model:
        - Status enum values
        - Priority enum values

    TaskRun model:
        - RunStatus enum

    BatchProcessor:
        - Priority delay mapping
        - Enqueue creates job
"""

import os
import pytest
import tempfile

from app.models.skill import SkillBlueprint, SkillCategory, SkillStatus
from app.models.task import Task, TaskStatus, TaskPriority, TaskRun, RunStatus
from app.services.skill_loader import SkillLoader, get_skill_loader
from app.services.batch_processor import BatchProcessor, PRIORITY_DELAYS


# ══════════════════════════════════════════════════════════════════════════════
# SKILL MODEL
# ══════════════════════════════════════════════════════════════════════════════

class TestSkillModel:
    """SkillBlueprint data model."""

    def test_skill_fields(self):
        from datetime import datetime, timezone
        skill = SkillBlueprint(
            skill_id="sk-1",
            name="code_review",
            description="Review code changes",
            prompt_template="Review this: {code}",
            category=SkillCategory.CODE_REVIEW,
            author="test",
            created_at=datetime.now(timezone.utc),
        )
        assert skill.name == "code_review"
        assert skill.category == SkillCategory.CODE_REVIEW

    def test_skill_categories(self):
        cats = [e.value for e in SkillCategory]
        assert "code_generation" in cats
        assert "code_review" in cats
        assert len(cats) >= 5

    def test_skill_status_values(self):
        statuses = [e.value for e in SkillStatus]
        assert len(statuses) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# SKILL LOADER
# ══════════════════════════════════════════════════════════════════════════════

class TestSkillLoader:
    """Skill loading from filesystem."""

    def test_frontmatter_parsing(self):
        loader = SkillLoader()
        content = '---\nname: test_skill\nversion: 1.0.0\ncategory: code_review\n---\nPrompt body'
        fm, body = loader._parse_frontmatter(content)
        assert fm["name"] == "test_skill"
        assert fm["version"] == "1.0.0"
        assert body == "Prompt body"

    def test_frontmatter_no_yaml(self):
        loader = SkillLoader()
        content = "Just plain text"
        fm, body = loader._parse_frontmatter(content)
        assert fm == {}
        assert body == "Just plain text"

    def test_load_from_nonexistent_directory(self):
        loader = SkillLoader()
        skills = loader.load_from_directory("/nonexistent/path")
        assert skills == []

    def test_load_skill_no_skill_md(self):
        loader = SkillLoader()
        with tempfile.TemporaryDirectory() as td:
            result = loader.load_skill(td)
            assert result is None

    def test_load_skill_valid(self):
        loader = SkillLoader()
        with tempfile.TemporaryDirectory() as td:
            skill_md = os.path.join(td, "SKILL.md")
            with open(skill_md, "w") as f:
                f.write("---\nname: my_skill\nversion: 2.0.0\ncategory: testing\n---\nDo something")
            result = loader.load_skill(td)
            assert result is not None
            assert result["name"] == "my_skill"
            assert result["version"] == "2.0.0"
            assert result["prompt_template"] == "Do something"

    def test_singleton(self):
        import app.services.skill_loader as mod
        old = mod._loader
        mod._loader = None
        l1 = get_skill_loader()
        l2 = get_skill_loader()
        assert l1 is l2
        mod._loader = old


# ══════════════════════════════════════════════════════════════════════════════
# TASK MODEL
# ══════════════════════════════════════════════════════════════════════════════

class TestTaskModel:
    """Task and TaskRun data models."""

    def test_task_status_values(self):
        statuses = [e.value for e in TaskStatus]
        assert len(statuses) >= 2

    def test_task_priority_values(self):
        priorities = [e.value for e in TaskPriority]
        assert len(priorities) >= 2

    def test_task_run_status(self):
        statuses = [e.value for e in RunStatus]
        assert len(statuses) >= 2

    def test_task_model_instantiation(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        task = Task(
            task_id="t-1",
            session_id="s-1",
            workspace_id="ws-1",
            title="Review PR",
            description="Review the pull request",
            created_by="alice",
            created_at=now,
            updated_at=now,
        )
        assert task.title == "Review PR"


# ══════════════════════════════════════════════════════════════════════════════
# BATCH PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

class TestBatchProcessor:
    """Batch processing queue."""

    def test_priority_delays(self):
        assert PRIORITY_DELAYS["immediate"] == 0
        assert PRIORITY_DELAYS["soon"] == 300
        assert PRIORITY_DELAYS["deferred"] == 3600
        assert PRIORITY_DELAYS["batch"] == 86400

    @pytest.mark.asyncio
    async def test_enqueue_creates_job(self):
        bp = BatchProcessor()
        job = await bp.enqueue("ws1", "test query", priority="deferred")
        assert job["workspace_id"] == "ws1"
        assert job["query"] == "test query"
        assert job["priority"] == "deferred"
        assert job["status"] == "queued"

    @pytest.mark.asyncio
    async def test_enqueue_immediate(self):
        bp = BatchProcessor()
        job = await bp.enqueue("ws1", "urgent", priority="immediate")
        assert job["priority"] == "immediate"

    @pytest.mark.asyncio
    async def test_enqueue_with_metadata(self):
        bp = BatchProcessor()
        job = await bp.enqueue("ws1", "q", metadata={"source": "nightly"})
        assert job["metadata"]["source"] == "nightly"
