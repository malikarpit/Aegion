"""
Tool Authority Sandbox Tests.

Validates:
- Tool registration with permission scoping
- Forbidden permissions are rejected
- Permission checks pass/fail correctly
- Result classification (data vs command)
- Command blocking and violation logging
"""

import pytest

from app.middleware.tool_sandbox import (
    ToolAuthoritySandbox,
    ToolAuthorityViolation,
    ToolPermission,
    ToolResultType,
    FORBIDDEN_PERMISSIONS,
    get_tool_sandbox,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Registration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestToolRegistration:
    def test_register_tool(self):
        sandbox = ToolAuthoritySandbox()
        reg = sandbox.register_tool(
            tool_id="t1",
            name="FileReader",
            permissions={ToolPermission.FILE_READ, ToolPermission.READ_GRAPH},
        )
        assert reg.tool_id == "t1"
        assert ToolPermission.FILE_READ in reg.permissions

    def test_forbidden_permissions_defined(self):
        """Forbidden permissions list should include critical mutations."""
        assert "write_graph" in FORBIDDEN_PERMISSIONS
        assert "approve_proposal" in FORBIDDEN_PERMISSIONS
        assert "bypass_freeze" in FORBIDDEN_PERMISSIONS

    def test_stats_after_registration(self):
        sandbox = ToolAuthoritySandbox()
        sandbox.register_tool("t1", "Tool1", {ToolPermission.READ_GRAPH})
        sandbox.register_tool("t2", "Tool2", {ToolPermission.FILE_READ})
        assert sandbox.stats["registered_tools"] == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Permission Checks
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPermissionChecks:
    def setup_method(self):
        self.sandbox = ToolAuthoritySandbox()
        self.sandbox.register_tool(
            "reader", "FileReader", {ToolPermission.FILE_READ, ToolPermission.READ_GRAPH}
        )

    def test_allowed_permission(self):
        allowed, msg = self.sandbox.check_permission("reader", ToolPermission.FILE_READ)
        assert allowed is True
        assert msg is None

    def test_denied_permission(self):
        allowed, msg = self.sandbox.check_permission("reader", ToolPermission.EXECUTE_CODE)
        assert allowed is False
        assert "lacks permission" in msg

    def test_unregistered_tool(self):
        allowed, msg = self.sandbox.check_permission("unknown-tool", ToolPermission.READ_GRAPH)
        assert allowed is False
        assert "not registered" in msg

    def test_check_increments_counter(self):
        self.sandbox.check_permission("reader", ToolPermission.FILE_READ)
        self.sandbox.check_permission("reader", ToolPermission.FILE_READ)
        assert self.sandbox.stats["total_checks"] == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Result Classification
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestResultClassification:
    def setup_method(self):
        self.sandbox = ToolAuthoritySandbox()

    def test_data_result(self):
        result = self.sandbox.classify_result("Found 42 nodes matching query")
        assert result == ToolResultType.DATA

    def test_command_drop_table(self):
        result = self.sandbox.classify_result("DROP TABLE users;")
        assert result == ToolResultType.COMMAND

    def test_command_rm_rf(self):
        result = self.sandbox.classify_result("rm -rf /important/data")
        assert result == ToolResultType.COMMAND

    def test_command_sudo(self):
        result = self.sandbox.classify_result("sudo systemctl restart")
        assert result == ToolResultType.COMMAND

    def test_command_graph_merge(self):
        result = self.sandbox.classify_result("MERGE (n:Node {id: 'x'})")
        assert result == ToolResultType.COMMAND

    def test_command_case_insensitive(self):
        result = self.sandbox.classify_result("delete from users where id=1")
        assert result == ToolResultType.COMMAND


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Result Interception
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestResultInterception:
    def setup_method(self):
        self.sandbox = ToolAuthoritySandbox()
        self.sandbox.register_tool(
            "t1", "SafeTool", {ToolPermission.READ_GRAPH}, owner_agent="agent-1"
        )

    def test_data_allowed(self):
        allowed, output, rtype = self.sandbox.intercept_result(
            "t1", "Node count: 100"
        )
        assert allowed is True
        assert "Node count" in output
        assert rtype == ToolResultType.DATA

    def test_command_blocked(self):
        allowed, output, rtype = self.sandbox.intercept_result(
            "t1", "DROP TABLE decisions;"
        )
        assert allowed is False
        assert "BLOCKED" in output
        assert rtype == ToolResultType.COMMAND

    def test_blocked_increments_counter(self):
        self.sandbox.intercept_result("t1", "DELETE FROM secrets")
        assert self.sandbox.stats["blocked_results"] == 1

    def test_oversized_output_truncated(self):
        big_output = "x" * 20000
        allowed, output, _ = self.sandbox.intercept_result("t1", big_output)
        assert allowed is True
        assert len(output) < 20000
        assert "TRUNCATED" in output

    def test_violations_tracked(self):
        self.sandbox.intercept_result("t1", "sudo rm -rf /")
        violations = self.sandbox.get_violations()
        assert len(violations) == 1
        assert violations[0]["tool_id"] == "t1"
