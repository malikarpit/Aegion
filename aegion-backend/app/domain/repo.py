from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class SymbolRecord(BaseModel):
    """Represents a code symbol (class, function, variable) found in a file."""
    symbol_id: str = Field(..., description="Unique identifier for the symbol (e.g., hash or qualified name)")
    name: str = Field(..., description="Name of the symbol")
    type: Literal["class", "function", "variable", "interface", "module"] = Field(..., description="Type of symbol")
    file_path: str = Field(..., description="Relative path to the file containing the symbol")
    line_start: int = Field(..., description="Start line number (1-indexed)")
    line_end: int = Field(..., description="End line number (1-indexed)")
    parent_symbol: Optional[str] = Field(None, description="ID of the parent symbol (e.g., class for a method)")
    signature: Optional[str] = Field(None, description="Function signature or type definition")
    docstring: Optional[str] = Field(None, description="Extracted docstring or comment block")

class DependencyEdge(BaseModel):
    """Represents a relationship between files (import, call, inheritance)."""
    source_file: str = Field(..., description="Path of the source file")
    target_file: str = Field(..., description="Path of the target file being imported or used")
    type: Literal["import", "call", "inherits", "implements"] = Field(..., description="Type of dependency")
    line_number: Optional[int] = Field(None, description="Line number where the dependency occurs")

class FileRecord(BaseModel):
    """Represents a file in the workspace."""
    file_path: str = Field(..., description="Relative path from workspace root")
    content_hash: str = Field(..., description="SHA-256 hash of file content")
    language: str = Field(..., description="Programming language (python, typescript, etc.)")
    size_bytes: int = Field(..., description="File size in bytes")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    loc: int = Field(0, description="Lines of code")
    symbols: List[SymbolRecord] = Field(default_factory=list, description="Symbols defined in this file")
    dependencies: List[DependencyEdge] = Field(default_factory=list, description="Outgoing dependencies")

class WorkspaceScan(BaseModel):
    """Represents a complete or partial scan of the workspace."""
    scan_id: str = Field(..., description="Unique ID for this scan operation")
    workspace_id: str = Field(..., description="ID of the workspace scanned")
    start_time: datetime = Field(..., description="When the scan started")
    end_time: Optional[datetime] = Field(None, description="When the scan completed")
    status: Literal["pending", "in_progress", "completed", "failed", "cancelled"] = Field("pending", description="Current status")
    files_scanned: int = Field(0, description="Number of files processed")
    files_failed: int = Field(0, description="Number of files that failed processing")
    total_symbols: int = Field(0, description="Total symbols indexed")
    commits_mined: int = Field(0, description="Total commits mined")
    errors: List[str] = Field(default_factory=list, description="List of error messages")

from .git_models import CommitRecord

class ContextPackage(BaseModel):
    """
    A smart bundle of repo intelligence for a specific set of files.
    Used by Agents/Council to understand context.
    """
    workspace_id: str = Field(..., description="Workspace ID")
    target_files: List[str] = Field(..., description="Files requested for context")
    file_records: List[FileRecord] = Field(..., description="Detailed file info (without full content)")
    related_symbols: List[SymbolRecord] = Field(..., description="Symbols defined in these files")
    relevant_commits: List[CommitRecord] = Field(..., description="Relevant history for these files")
    generated_at: datetime = Field(default_factory=datetime.now, description="Generation timestamp")

