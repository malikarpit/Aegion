from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class DiffHunkRecord(BaseModel):
    """Represents a specific block of changes in a commit."""
    file_path: str = Field(..., description="Path of the file changed")
    old_start: int = Field(..., description="Starting line in the old version")
    old_lines: int = Field(..., description="Number of lines in the old version")
    new_start: int = Field(..., description="Starting line in the new version")
    new_lines: int = Field(..., description="Number of lines in the new version")
    content_hash: str = Field(..., description="Hash of the hunk content for deduplication")

class CommitRecord(BaseModel):
    """Represents a Git commit."""
    sha: str = Field(..., description="Full Git commit SHA")
    message: str = Field(..., description="Commit message")
    author_name: str = Field(..., description="Name of the author")
    author_email: str = Field(..., description="Email of the author")
    timestamp: datetime = Field(..., description="Commit timestamp")
    parents: List[str] = Field(default_factory=list, description="Parent commit SHAs")
    intent_type: Literal["feat", "fix", "chore", "refactor", "docs", "style", "test", "other"] = Field("other", description="Inferred intent")
    changed_files: List[str] = Field(default_factory=list, description="List of modified file paths")
    diff_hunks: List[DiffHunkRecord] = Field(default_factory=list, description="Detailed diff hunks")

class CodeDecisionLink(BaseModel):
    """Links code artifacts to architectural decisions."""
    link_id: str = Field(..., description="Unique ID for this link")
    symbol_id: Optional[str] = Field(None, description="ID of the symbol involved")
    file_path: Optional[str] = Field(None, description="Path of the file involved")
    commit_sha: Optional[str] = Field(None, description="Commit SHA involved")
    adr_id: str = Field(..., description="ID of the ADR")
    link_type: Literal["implemented_by", "violates", "relates_to", "supersedes"] = Field(..., description="Type of relationship")
    created_at: datetime = Field(..., description="When this link was established")
    confidence: float = Field(1.0, description="Confidence score (if inferred by AI)")
