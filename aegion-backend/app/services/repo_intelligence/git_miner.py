import git
import re
import logging
from typing import AsyncGenerator, List, Dict
from datetime import datetime, timezone
from ...domain.git_models import CommitRecord, DiffHunkRecord

logger = logging.getLogger(__name__)

class GitMiner:
    """
    Extracts commit history and diffs using GitPython.
    """

    def __init__(self, root_path: str):
        self.root_path = root_path
        try:
            self.repo = git.Repo(root_path, search_parent_directories=True)
        except git.InvalidGitRepositoryError:
            self.repo = None
            logger.warning(f"No git repository found at {root_path}")

    def _infer_intent(self, message: str) -> str:
        """Guess intent from commit message (Conventional Commits)."""
        lower_msg = message.lower()
        if re.match(r"^(feat|feature)(\(.*\))?:", lower_msg): return "feat"
        if re.match(r"^(fix|bugfix)(\(.*\))?:", lower_msg): return "fix"
        if re.match(r"^(chore|ci|build)(\(.*\))?:", lower_msg): return "chore"
        if re.match(r"^(refactor|perf)(\(.*\))?:", lower_msg): return "refactor"
        if re.match(r"^docs(\(.*\))?:", lower_msg): return "docs"
        if re.match(r"^test(\(.*\))?:", lower_msg): return "test"
        if re.match(r"^style(\(.*\))?:", lower_msg): return "style"
        return "other"

    async def mine_history(self, limit: int = 100) -> AsyncGenerator[CommitRecord, None]:
        """Yields commits from HEAD backwards."""
        if not self.repo:
            return

        try:
            # Iterate commits
            for commit in self.repo.iter_commits('HEAD', max_count=limit):
                
                # Extract changed files and diffs
                changed_files = []

                if commit.parents:
                    diffs = commit.diff(commit.parents[0])
                else:
                    diffs = commit.diff(git.NULL_TREE)

                for diff_item in diffs:
                    if diff_item.a_path: changed_files.append(diff_item.a_path)
                    if diff_item.b_path: changed_files.append(diff_item.b_path)

                # Deduplicate files
                changed_files = list(set(changed_files))

                # Extract diff hunks (limited per commit for performance)
                diff_hunks = []
                import hashlib
                for diff_item in diffs:
                    if len(diff_hunks) >= 20:  # Cap hunks per commit
                        break
                    try:
                        file_path = diff_item.b_path or diff_item.a_path or "unknown"
                        # Parse the unified diff text for hunk headers
                        diff_text = diff_item.diff
                        if isinstance(diff_text, bytes):
                            diff_text = diff_text.decode("utf-8", errors="replace")
                        if not diff_text:
                            continue
                        # Extract @@ hunk headers
                        import re
                        for match in re.finditer(
                            r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@",
                            diff_text
                        ):
                            old_start = int(match.group(1))
                            old_lines = int(match.group(2)) if match.group(2) else 1
                            new_start = int(match.group(3))
                            new_lines = int(match.group(4)) if match.group(4) else 1
                            # Hash the hunk content for deduplication
                            hunk_content = diff_text[match.start():match.start() + 500]
                            content_hash = hashlib.sha256(hunk_content.encode()).hexdigest()[:16]
                            from app.domain.git_models import DiffHunkRecord
                            diff_hunks.append(DiffHunkRecord(
                                file_path=file_path,
                                old_start=old_start,
                                old_lines=old_lines,
                                new_start=new_start,
                                new_lines=new_lines,
                                content_hash=content_hash,
                            ))
                    except Exception:
                        pass  # Skip unparseable diffs

                record = CommitRecord(
                    sha=commit.hexsha,
                    message=commit.message.strip(),
                    author_name=commit.author.name,
                    author_email=commit.author.email,
                    timestamp=datetime.fromtimestamp(commit.committed_date, tz=timezone.utc),
                    parents=[p.hexsha for p in commit.parents],
                    intent_type=self._infer_intent(commit.message),
                    changed_files=changed_files,
                    diff_hunks=diff_hunks
                )
                
                yield record

        except Exception as e:
            logger.error(f"Error mining git history: {e}")

    def get_branch_diff(self, base_branch: str = "main", head_branch: str = "HEAD") -> List[Dict[str, str]]:
        """
        Compare two branches and return changed files with status (A/M/D).
        """
        changes = []
        if not self.repo:
            return changes

        try:
            # Check if branches exist
            base_commit = self.repo.commit(base_branch)
            head_commit = self.repo.commit(head_branch)

            diffs = base_commit.diff(head_commit)
            
            for diff in diffs:
                change_type = diff.change_type # 'A', 'M', 'D', 'R'
                file_path = diff.b_path if diff.b_path else diff.a_path
                
                changes.append({
                    "file_path": file_path,
                    "change_type": change_type,
                    "score": diff.score # Similarity score for renames
                })
                
        except Exception as e:
            logger.error(f"Error computing diff between {base_branch} and {head_branch}: {e}")
            
        return changes
