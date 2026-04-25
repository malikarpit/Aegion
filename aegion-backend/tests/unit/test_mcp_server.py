"""
Tests for MCP Server Manager — Phase R2: Integrations.

Covers:
    Registration:
        - STDIO server registration
        - SSE server registration
        - HTTP server registration
        - STDIO without command raises ValueError
        - SSE without URL raises ValueError
        - Duplicate name raises ValueError
        - Remove server

    Connection:
        - Connect discovers tools
        - Connect discovers resources
        - Disconnect clears tools
        - Connect nonexistent raises ValueError

    Tool Invocation:
        - Invoke tool success
        - Invoke on disconnected raises
        - Invoke nonexistent tool raises
        - Invocation log recorded

References:
    - MCP Specification (Anthropic, 2024)
"""

import pytest

from app.services.mcp_server import (
    MCPServerManager,
    MCPTransport,
    MCPToolDefinition,
    get_mcp_manager,
)


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

class TestMCPRegistration:
    """MCP server registration."""

    def test_register_stdio_server(self):
        mgr = MCPServerManager()
        server = mgr.register_server("git", MCPTransport.STDIO, command="git-mcp")
        assert server.name == "git"
        assert server.transport == MCPTransport.STDIO
        assert server.status == "disconnected"

    def test_register_sse_server(self):
        mgr = MCPServerManager()
        server = mgr.register_server("api", MCPTransport.SSE, url="http://localhost:3000/sse")
        assert server.transport == MCPTransport.SSE
        assert server.url == "http://localhost:3000/sse"

    def test_register_http_server(self):
        mgr = MCPServerManager()
        server = mgr.register_server("db", MCPTransport.HTTP, url="http://localhost:5000")
        assert server.transport == MCPTransport.HTTP

    def test_stdio_without_command_raises(self):
        mgr = MCPServerManager()
        with pytest.raises(ValueError, match="requires a 'command'"):
            mgr.register_server("bad", MCPTransport.STDIO)

    def test_sse_without_url_raises(self):
        mgr = MCPServerManager()
        with pytest.raises(ValueError, match="requires a 'url'"):
            mgr.register_server("bad", MCPTransport.SSE)

    def test_http_without_url_raises(self):
        mgr = MCPServerManager()
        with pytest.raises(ValueError, match="requires a 'url'"):
            mgr.register_server("bad", MCPTransport.HTTP)

    def test_duplicate_name_raises(self):
        mgr = MCPServerManager()
        mgr.register_server("git", MCPTransport.STDIO, command="git-mcp")
        with pytest.raises(ValueError, match="already registered"):
            mgr.register_server("git", MCPTransport.STDIO, command="git-mcp-2")

    def test_remove_server(self):
        mgr = MCPServerManager()
        server = mgr.register_server("git", MCPTransport.STDIO, command="git-mcp")
        mgr.remove_server(server.server_id)
        assert mgr.list_servers() == []

    def test_remove_nonexistent_raises(self):
        mgr = MCPServerManager()
        with pytest.raises(ValueError, match="not found"):
            mgr.remove_server("fake-id")

    def test_list_servers(self):
        mgr = MCPServerManager()
        mgr.register_server("a", MCPTransport.STDIO, command="a-cmd")
        mgr.register_server("b", MCPTransport.SSE, url="http://b")
        assert len(mgr.list_servers()) == 2


# ══════════════════════════════════════════════════════════════════════════════
# CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

class TestMCPConnection:
    """MCP server connection and tool discovery."""

    @pytest.mark.asyncio
    async def test_connect_discovers_tools(self):
        mgr = MCPServerManager()
        server = mgr.register_server("github", MCPTransport.STDIO, command="gh-mcp")
        connected = await mgr.connect_server(server.server_id)
        assert connected.status == "connected"
        assert len(connected.tools) > 0

    @pytest.mark.asyncio
    async def test_connect_discovers_resources(self):
        mgr = MCPServerManager()
        server = mgr.register_server("postgres-db", MCPTransport.SSE, url="http://db")
        connected = await mgr.connect_server(server.server_id)
        assert len(connected.resources) > 0

    @pytest.mark.asyncio
    async def test_disconnect_clears_tools(self):
        mgr = MCPServerManager()
        server = mgr.register_server("github", MCPTransport.STDIO, command="gh")
        await mgr.connect_server(server.server_id)
        await mgr.disconnect_server(server.server_id)
        assert server.status == "disconnected"
        assert server.tools == []

    @pytest.mark.asyncio
    async def test_connect_nonexistent_raises(self):
        mgr = MCPServerManager()
        with pytest.raises(ValueError, match="not found"):
            await mgr.connect_server("fake-id")

    @pytest.mark.asyncio
    async def test_connected_at_set(self):
        mgr = MCPServerManager()
        server = mgr.register_server("test", MCPTransport.STDIO, command="test-cmd")
        await mgr.connect_server(server.server_id)
        assert server.connected_at is not None


# ══════════════════════════════════════════════════════════════════════════════
# TOOL INVOCATION
# ══════════════════════════════════════════════════════════════════════════════

class TestMCPToolInvocation:
    """MCP tool invocation."""

    @pytest.mark.asyncio
    async def test_invoke_tool_success(self):
        mgr = MCPServerManager()
        server = mgr.register_server("github", MCPTransport.STDIO, command="gh")
        await mgr.connect_server(server.server_id)
        result = await mgr.invoke_tool(
            server.server_id,
            "search_repositories",
            {"query": "aegion"},
        )
        assert result["isError"] is False
        assert "content" in result

    @pytest.mark.asyncio
    async def test_invoke_on_disconnected_raises(self):
        mgr = MCPServerManager()
        server = mgr.register_server("github", MCPTransport.STDIO, command="gh")
        # Not connected
        with pytest.raises(ValueError, match="not connected"):
            await mgr.invoke_tool(server.server_id, "search_repositories", {})

    @pytest.mark.asyncio
    async def test_invoke_nonexistent_tool_raises(self):
        mgr = MCPServerManager()
        server = mgr.register_server("github", MCPTransport.STDIO, command="gh")
        await mgr.connect_server(server.server_id)
        with pytest.raises(ValueError, match="not found"):
            await mgr.invoke_tool(server.server_id, "nonexistent_tool", {})

    @pytest.mark.asyncio
    async def test_invocation_log_recorded(self):
        mgr = MCPServerManager()
        server = mgr.register_server("github", MCPTransport.STDIO, command="gh")
        await mgr.connect_server(server.server_id)
        await mgr.invoke_tool(server.server_id, "search_repositories", {"query": "test"})
        log = mgr.get_invocation_log()
        assert len(log) == 1
        assert log[0]["tool_name"] == "search_repositories"

    @pytest.mark.asyncio
    async def test_read_resource(self):
        mgr = MCPServerManager()
        server = mgr.register_server("postgres-db", MCPTransport.SSE, url="http://db")
        await mgr.connect_server(server.server_id)
        result = await mgr.read_resource(server.server_id, "postgres://schema")
        assert "contents" in result


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

class TestMCPSingleton:
    def test_singleton(self):
        import app.services.mcp_server as mod
        mod._mcp_manager = None
        m1 = get_mcp_manager()
        m2 = get_mcp_manager()
        assert m1 is m2
        mod._mcp_manager = None
