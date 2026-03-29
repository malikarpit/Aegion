import os
import hashlib
import logging
import pathspec
from typing import AsyncGenerator, List
from datetime import datetime, timezone

from ...domain.repo import FileRecord
from ...core.time import TimeAuthority

logger = logging.getLogger(__name__)

class RepoScanner:
    """
    Recursively scans a workspace, respecting .gitignore rules.
    """

    def __init__(self, root_path: str):
        self.root_path = os.path.abspath(root_path)
        self.gitignore_spec = self._load_gitignore()

    def _load_gitignore(self) -> pathspec.PathSpec:
        """Load .gitignore if present, otherwise return empty spec."""
        gitignore_path = os.path.join(self.root_path, ".gitignore")
        patterns = []
        
        # Always ignore .git and common junk
        patterns.extend([".git/", ".idea/", ".vscode/", "__pycache__/", "*.pyc", ".DS_Store", ".venv/", "node_modules/"])

        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, "r") as f:
                    patterns.extend(f.read().splitlines())
            except Exception as e:
                logger.warning(f"Failed to read .gitignore: {e}")

        return pathspec.PathSpec.from_lines("gitignore", patterns)

    def _should_ignore(self, relative_path: str) -> bool:
        """Check if path matches ignore rules."""
        return self.gitignore_spec.match_file(relative_path)

    def _hash_content(self, content: bytes) -> str:
        """Calculate SHA-256 hash of content."""
        return hashlib.sha256(content).hexdigest()

    def _get_language(self, file_path: str) -> str:
        """Determine language from extension."""
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        if ext == ".py": return "python"
        if ext in [".ts", ".tsx"]: return "typescript"
        if ext in [".js", ".jsx"]: return "javascript"
        if ext == ".md": return "markdown"
        if ext in [".yml", ".yaml"]: return "yaml"
        if ext == ".json": return "json"
        return "text"

    async def scan_workspace(self) -> AsyncGenerator[FileRecord, None]:
        """
        Yields FileRecord for every non-ignored file in workspace.
        """
        for root, dirs, files in os.walk(self.root_path):
            # Calculate relative path for matching
            rel_root = os.path.relpath(root, self.root_path)
            if rel_root == ".":
                rel_root = ""

            # Filter directories in-place to prevent traversal
            # We must use a list copy to modify dirs
            dirs[:] = [d for d in dirs if not self._should_ignore(os.path.join(rel_root, d) + "/")]

            for file in files:
                rel_path = os.path.join(rel_root, file)
                
                if self._should_ignore(rel_path):
                    continue

                full_path = os.path.join(root, file)
                
                try:
                    # Get file stats
                    stat = os.stat(full_path)
                    
                    # Read content (binary to handle encoding issues safely initially)
                    with open(full_path, "rb") as f:
                        content_bytes = f.read()
                    
                    # Try to decode as text to count lines, if meaningful code
                    loc = 0
                    try:
                        text_content = content_bytes.decode('utf-8')
                        loc = len(text_content.splitlines())
                    except UnicodeDecodeError:
                        pass # Valid for binary files like images

                    record = FileRecord(
                        file_path=rel_path,
                        content_hash=self._hash_content(content_bytes),
                        language=self._get_language(rel_path),
                        size_bytes=stat.st_size,
                        last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                        loc=loc
                    )
                    
                    yield record

                except Exception as e:
                    logger.error(f"Error scanning file {rel_path}: {e}")
                    # In a real system, we might yield an error record or continue
                    continue
