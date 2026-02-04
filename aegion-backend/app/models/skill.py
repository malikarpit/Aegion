"""
Aegion Data Models - Skill Blueprint.

Prompt/Skill blueprints with signature verification and provenance tracking.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class SkillCategory(str, Enum):
    """Category of a skill blueprint."""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    REFACTORING = "refactoring"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    DEBUGGING = "debugging"
    ARCHITECTURE = "architecture"
    CUSTOM = "custom"


class SkillStatus(str, Enum):
    """Installation/availability status."""
    AVAILABLE = "available"
    INSTALLED = "installed"
    DEPRECATED = "deprecated"


class SkillBlueprint(BaseModel):
    """A prompt/skill blueprint definition."""

    # Identity
    skill_id: str = Field(..., description="Unique skill ID")
    name: str = Field(..., description="Skill name")
    version: str = Field(default="1.0.0")

    # Content
    description: str = Field(default="")
    prompt_template: str = Field(..., description="The prompt template with {{placeholders}}")
    category: SkillCategory = Field(default=SkillCategory.CUSTOM)

    # Provenance
    author: str = Field(..., description="Blueprint author")
    signature: Optional[str] = Field(None, description="Cryptographic signature for verification")
    source_url: Optional[str] = Field(None, description="Origin URL")

    # Metadata
    tags: List[str] = Field(default_factory=list)
    parameters: List[str] = Field(default_factory=list, description="Required parameter names")
    status: SkillStatus = Field(default=SkillStatus.AVAILABLE)
    install_count: int = Field(default=0)

    # Governance
    doctrine_tags: List[str] = Field(default_factory=list, description="Doctrine compliance tags")
    review_status: str = Field(default="draft", description="Review status: draft|reviewed|approved|rejected")
    version_history: List[Dict[str, Any]] = Field(default_factory=list, description="Version history entries")

    # Packaging
    scripts: List[str] = Field(default_factory=list, description="Associated script paths")
    resources: List[str] = Field(default_factory=list, description="Associated resource paths")
    permission_manifest: Dict[str, Any] = Field(default_factory=dict, description="Required permissions for execution")

    # Attestation
    attestations: List[Dict[str, Any]] = Field(default_factory=list, description="Execution attestation chain")

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    installed_at: Optional[datetime] = None
