"""
Aegion Tool Authority Sandbox: Governance Hardening.

Enforces tool execution boundaries:
- Tools cannot write to the graph directly (must go through Archon)
- Tools cannot bypass governance (no freeze bypass, no direct approval)
- Tool results classified as "data" vs "command" — commands are blocked
- Per-tool permission scoping

Doctrine: "Tools are extensions of an agent's senses, not its authority."
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from ..core.logging import logger


class ToolResultType(str, Enum):
    """Classification of tool execution result."""
    DATA = "data"           # Safe: read-only data
    COMMAND = "command"     # Blocked: attempts to mutate state
    QUERY = "query"         # Safe: database/graph query
    SIDE_EFFECT = "side_effect"  # Flagged: external API calls, file writes


class ToolPermission(str, Enum):
    """Permissions that can be granted to tools."""
    READ_GRAPH = "read_graph"
    READ_MEMORY = "read_memory"
    EXECUTE_CODE = "execute_code"
    NETWORK_ACCESS = "network_access"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"


# Permissions that tools must NEVER have
FORBIDDEN_PERMISSIONS: Set[str] = {
    "write_graph",       # Must go through Archon
    "approve_proposal",  # Must go through governance
    "bypass_freeze",     # No freeze bypass
    "modify_governance", # No governance mutation
    "escalate_privilege",# No privilege escalation
}


# Patterns that indicate a tool result is a command (not data)
_COMMAND_PATTERNS = [
    "DROP TABLE", "DELETE FROM", "UPDATE ", "INSERT INTO",
    "ALTER TABLE", "TRUNCATE",
    "rm -rf", "rm -f", "sudo ",
    "chmod ", "chown ",
    "MERGE ", "CREATE ", "SET ",  # Graph mutations
    "approve(", "bypass_freeze(",
]


@dataclass
class ToolRegistration:
    """Registered tool with its permission scope."""
    tool_id: str
    name: str
    permissions: Set[ToolPermission]
    max_output_size: int = 10000  # Max output in chars
    rate_limit: int = 60         # Calls per minute
    owner_agent: str = "unknown"


class ToolAuthoritySandbox:
    """
    Enforces authority boundaries for tool execution.

    Tools operate within a strict permission sandbox:
    - Cannot write to graph (must go through Archon service)
    - Cannot bypass governance (no direct approvals)
    - Results are classified and commands are blocked
    """

    def __init__(self):
        self._registered_tools: Dict[str, ToolRegistration] = {}
        self._blocked_results: int = 0
        self._total_checks: int = 0
        self._violations: List[Dict[str, str]] = []

    def register_tool(
        self,
        tool_id: str,
        name: str,
        permissions: Set[ToolPermission],
        owner_agent: str = "unknown",
    ) -> ToolRegistration:
        """Register a tool with its permission scope."""
        # Validate no forbidden permissions
        for perm in permissions:
            if perm.value in FORBIDDEN_PERMISSIONS:
                raise ToolAuthorityViolation(
                    f"Cannot grant forbidden permission '{perm.value}' to tool '{name}'"
                )

        reg = ToolRegistration(
            tool_id=tool_id,
            name=name,
            permissions=permissions,
            owner_agent=owner_agent,
        )
        self._registered_tools[tool_id] = reg
        return reg

    def check_permission(
        self, tool_id: str, required_permission: ToolPermission
    ) -> Tuple[bool, Optional[str]]:
        """Check if a tool has a specific permission."""
        self._total_checks += 1

        if tool_id not in self._registered_tools:
            return False, f"Tool '{tool_id}' is not registered"

        tool = self._registered_tools[tool_id]
        if required_permission not in tool.permissions:
            self._record_violation(tool_id, f"Missing permission: {required_permission.value}")
            return False, f"Tool '{tool.name}' lacks permission: {required_permission.value}"

        return True, None

    def classify_result(self, output: str) -> ToolResultType:
        """
        Classify a tool's output as data or command.

        Commands (mutations, privileged operations) are blocked.
        """
        output_upper = output.upper()

        for pattern in _COMMAND_PATTERNS:
            if pattern.upper() in output_upper:
                return ToolResultType.COMMAND

        return ToolResultType.DATA

    def intercept_result(
        self, tool_id: str, output: str
    ) -> Tuple[bool, str, ToolResultType]:
        """
        Intercept and validate a tool's output.

        Returns:
            (allowed, sanitized_output, result_type)
        """
        result_type = self.classify_result(output)

        if result_type == ToolResultType.COMMAND:
            self._blocked_results += 1
            self._record_violation(tool_id, f"Command output blocked: {output[:100]}")
            return False, "[BLOCKED: Tool attempted to return a command]", result_type

        # Truncate oversized output
        tool = self._registered_tools.get(tool_id)
        max_size = tool.max_output_size if tool else 10000
        if len(output) > max_size:
            output = output[:max_size] + f"\n[TRUNCATED: output exceeded {max_size} chars]"

        return True, output, result_type

    def _record_violation(self, tool_id: str, detail: str) -> None:
        violation = {
            "tool_id": tool_id,
            "detail": detail,
        }
        self._violations.append(violation)
        logger.warning(
            "TOOL_AUTHORITY_VIOLATION",
            extra=violation,
        )

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "registered_tools": len(self._registered_tools),
            "total_checks": self._total_checks,
            "blocked_results": self._blocked_results,
            "violations": len(self._violations),
        }

    def get_violations(self) -> List[Dict[str, str]]:
        return list(self._violations)


class ToolAuthorityViolation(Exception):
    """Raised when a tool attempts to exceed its authority."""
    pass


# ========== Singleton ==========

_tool_sandbox: Optional[ToolAuthoritySandbox] = None


def get_tool_sandbox() -> ToolAuthoritySandbox:
    global _tool_sandbox
    if _tool_sandbox is None:
        _tool_sandbox = ToolAuthoritySandbox()
    return _tool_sandbox
