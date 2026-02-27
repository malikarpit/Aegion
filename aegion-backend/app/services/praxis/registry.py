"""
Aegion Praxis - Execution Descriptor Registry.

Phase 4: Execution & Resilience
Central registry for executable action descriptors.
"""

from typing import List, Optional, Dict
import uuid

from ...contracts.execution import (
    ExecutionDescriptor,
    ActionType,
    RiskLevel
)
from ...core.logging import logger
from ...core.time import TimeAuthority


class DescriptorRegistry:
    """
    Central registry for execution descriptors.
    
    Manages registration, lookup, and validation of
    executable action types.
    """
    
    def __init__(self):
        self._descriptors: Dict[str, ExecutionDescriptor] = {}
        self._init_builtin_descriptors()
    
    def _init_builtin_descriptors(self):
        """Initialize built-in safe action descriptors."""
        builtins = [
            ExecutionDescriptor(
                descriptor_id="builtin-file-read",
                action_type=ActionType.FILE_READ,
                name="File Read",
                description="Read file contents",
                risk_level=RiskLevel.SAFE,
                requires_sandbox=False,
                created_at=TimeAuthority.now(),
                created_by="system"
            ),
            ExecutionDescriptor(
                descriptor_id="builtin-file-write",
                action_type=ActionType.FILE_WRITE,
                name="File Write",
                description="Write to file",
                risk_level=RiskLevel.MODERATE,
                requires_sandbox=True,
                created_at=TimeAuthority.now(),
                created_by="system"
            ),
            ExecutionDescriptor(
                descriptor_id="builtin-file-delete",
                action_type=ActionType.FILE_DELETE,
                name="File Delete",
                description="Delete file or directory",
                risk_level=RiskLevel.DANGEROUS,
                requires_sandbox=True,
                requires_approval=True,
                created_at=TimeAuthority.now(),
                created_by="system"
            ),
            ExecutionDescriptor(
                descriptor_id="builtin-shell",
                action_type=ActionType.SHELL_COMMAND,
                name="Shell Command",
                description="Execute shell command",
                risk_level=RiskLevel.DANGEROUS,
                requires_sandbox=True,
                requires_approval=True,
                timeout_ms=60000,
                created_at=TimeAuthority.now(),
                created_by="system"
            ),
            ExecutionDescriptor(
                descriptor_id="builtin-api-call",
                action_type=ActionType.API_CALL,
                name="API Call",
                description="External API request",
                risk_level=RiskLevel.MODERATE,
                requires_sandbox=False,
                timeout_ms=30000,
                created_at=TimeAuthority.now(),
                created_by="system"
            ),
        ]
        
        for desc in builtins:
            self._descriptors[desc.descriptor_id] = desc
    
    async def register(
        self,
        action_type: ActionType,
        name: str,
        description: str,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        requires_sandbox: bool = False,
        requires_approval: bool = False,
        timeout_ms: int = 30000,
        created_by: str = "system"
    ) -> ExecutionDescriptor:
        """Register a new execution descriptor."""
        descriptor_id = f"desc-{uuid.uuid4().hex[:12]}"
        
        descriptor = ExecutionDescriptor(
            descriptor_id=descriptor_id,
            action_type=action_type,
            name=name,
            description=description,
            risk_level=risk_level,
            requires_sandbox=requires_sandbox,
            requires_approval=requires_approval,
            timeout_ms=timeout_ms,
            created_at=TimeAuthority.now(),
            created_by=created_by
        )
        
        self._descriptors[descriptor_id] = descriptor
        
        logger.audit(
            action="DESCRIPTOR_REGISTERED",
            actor=created_by,
            target=descriptor_id,
            justification=f"Registered: {name}",
            metadata={"action_type": action_type.value, "risk_level": risk_level.value}
        )
        
        return descriptor
    
    async def get(self, descriptor_id: str) -> Optional[ExecutionDescriptor]:
        """Get a descriptor by ID."""
        return self._descriptors.get(descriptor_id)
    
    async def get_by_action_type(self, action_type: ActionType) -> List[ExecutionDescriptor]:
        """Get all descriptors for an action type."""
        return [
            d for d in self._descriptors.values()
            if d.action_type == action_type
        ]
    
    async def list_all(self, risk_level: Optional[RiskLevel] = None) -> List[ExecutionDescriptor]:
        """List all descriptors, optionally filtered by risk level."""
        descriptors = list(self._descriptors.values())
        if risk_level:
            descriptors = [d for d in descriptors if d.risk_level == risk_level]
        return descriptors
    
    async def validate_context(
        self,
        descriptor_id: str,
        context: str
    ) -> bool:
        """Check if a descriptor allows execution in a given context."""
        descriptor = self._descriptors.get(descriptor_id)
        if not descriptor:
            return False
        
        # Check denied contexts first
        if context in descriptor.denied_contexts:
            return False
        
        # Check allowed contexts
        if "*" in descriptor.allowed_contexts:
            return True
        
        return context in descriptor.allowed_contexts


# Singleton
_registry: Optional[DescriptorRegistry] = None


def get_descriptor_registry() -> DescriptorRegistry:
    """Get singleton descriptor registry."""
    global _registry
    if _registry is None:
        _registry = DescriptorRegistry()
    return _registry
