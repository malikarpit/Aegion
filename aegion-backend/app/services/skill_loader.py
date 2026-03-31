"""
Aegion Skill Loader Service.

Loads skill blueprints from the filesystem (.aegion/skills/ directory).
Each skill is a directory with a SKILL.md (YAML frontmatter + markdown)
plus optional scripts/ and resources/ subdirectories.

Feature : Repo-checked skills with SKILL.md packaging.
"""

import os
import re
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
import hashlib

from ..core.logging import logger


class SkillLoader:
    """
    Scans workspace directories for SKILL.md files and parses
    them into SkillBlueprint-compatible dicts.

    Expected directory layout:
        .aegion/skills/
            my-skill/
                SKILL.md           # Required: YAML frontmatter + prompt body
                scripts/           # Optional: helper scripts
                    build.sh
                resources/         # Optional: supporting files
                    template.json
    """

    SKILL_DIR = ".aegion/skills"

    def _parse_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from SKILL.md content."""
        frontmatter = {}
        body = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                body = parts[2].strip()

                # Simple YAML parsing (key: value)
                for line in fm_text.split("\n"):
                    line = line.strip()
                    if ":" in line:
                        key, _, value = line.partition(":")
                        key = key.strip()
                        value = value.strip()
                        # Handle lists (- item)
                        if value == "":
                            continue
                        if value.startswith("[") and value.endswith("]"):
                            value = [v.strip().strip('"\'') for v in value[1:-1].split(",")]
                        elif value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        frontmatter[key] = value

        return frontmatter, body

    def _list_dir_files(self, dir_path: str) -> List[str]:
        """List filenames in a directory (non-recursive)."""
        if os.path.isdir(dir_path):
            return [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
        return []

    def load_skill(self, skill_dir: str) -> Optional[Dict[str, Any]]:
        """
        Load a single skill from its directory.

        Args:
            skill_dir: Path to the skill directory (must contain SKILL.md).

        Returns:
            Dict with skill blueprint fields, or None if invalid.
        """
        skill_md = os.path.join(skill_dir, "SKILL.md")
        if not os.path.isfile(skill_md):
            return None

        with open(skill_md, "r") as f:
            content = f.read()

        frontmatter, body = self._parse_frontmatter(content)
        skill_name = frontmatter.get("name", os.path.basename(skill_dir))

        # Generate signature from content
        sig = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Detect scripts and resources
        scripts = self._list_dir_files(os.path.join(skill_dir, "scripts"))
        resources = self._list_dir_files(os.path.join(skill_dir, "resources"))

        return {
            "skill_id": str(uuid.uuid4()),
            "name": skill_name,
            "version": frontmatter.get("version", "1.0.0"),
            "description": frontmatter.get("description", ""),
            "prompt_template": body,
            "category": frontmatter.get("category", "custom"),
            "author": frontmatter.get("author", "filesystem"),
            "signature": sig,
            "source_url": f"file://{skill_dir}",
            "tags": frontmatter.get("tags", []) if isinstance(frontmatter.get("tags"), list) else
                    [t.strip() for t in str(frontmatter.get("tags", "")).split(",") if t.strip()],
            "parameters": frontmatter.get("parameters", []) if isinstance(frontmatter.get("parameters"), list) else [],
            "scripts": scripts,
            "resources": resources,
            "created_at": datetime.now(timezone.utc),
        }

    def load_from_directory(self, workspace_path: str) -> List[Dict[str, Any]]:
        """
        Scan .aegion/skills/ in a workspace and load all valid skills.

        Args:
            workspace_path: Root path of the workspace.

        Returns:
            List of skill blueprint dicts.
        """
        skills_dir = os.path.join(workspace_path, self.SKILL_DIR)
        if not os.path.isdir(skills_dir):
            logger.info(f"No skills directory at {skills_dir}")
            return []

        skills = []
        for entry in os.listdir(skills_dir):
            entry_path = os.path.join(skills_dir, entry)
            if os.path.isdir(entry_path):
                skill = self.load_skill(entry_path)
                if skill:
                    skills.append(skill)
                    logger.info(f"Loaded skill from filesystem: {skill['name']} ({entry})")
                else:
                    logger.warning(f"Skipping invalid skill directory: {entry_path}")

        logger.info(f"Loaded {len(skills)} skills from {skills_dir}")
        return skills


# Singleton
_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    global _loader
    if _loader is None:
        _loader = SkillLoader()
    return _loader
