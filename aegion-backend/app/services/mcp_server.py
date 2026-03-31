"""
MCP Server Manager.

Manages connections to external MCP servers (stdio/SSE transports)
and exposes their tools, resources, and prompts to the Aegion tool registry.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ..core.logging import logger


class MCPTransport(str, Enum):
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


@dataclass
class MCPToolDefinition:
    """A tool exposed by an MCP server."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_id: str


@dataclass
class MCPResourceDefinition:
    """A resource exposed by an MCP server."""
    uri: str
    name: str
    description: str
    mime_type: str
    server_id: str


@dataclass
class MCPServerConnection:
    """Represents a connected MCP server."""
    server_id: str
    name: str
    transport: MCPTransport
    command: Optional[str] = None         # For stdio: the command to run
    args: Optional[List[str]] = None      # For stdio: command arguments
    url: Optional[str] = None             # For SSE/HTTP: endpoint URL
    env: Optional[Dict[str, str]] = None  # Environment variables
    status: str = "disconnected"          # disconnected, connecting, connected, error
    tools: List[MCPToolDefinition] = field(default_factory=list)
    resources: List[MCPResourceDefinition] = field(default_factory=list)
    connected_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MCPServerManager:
    """
    Manages MCP server connections.

    Supports:
    - Registering MCP server configurations
    - Simulated connection lifecycle (connect/disconnect)
    - Tool and resource discovery from connected servers
    - Invoking tools on connected servers
    """

    def __init__(self):
        self._servers: Dict[str, MCPServerConnection] = {}
        self._invocation_log: List[Dict[str, Any]] = []

    def register_server(
        self,
        name: str,
        transport: MCPTransport,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        url: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MCPServerConnection:
        """Register an MCP server configuration."""
        # Validate transport-specific requirements
        if transport == MCPTransport.STDIO and not command:
            raise ValueError("stdio transport requires a 'command'")
        if transport in (MCPTransport.SSE, MCPTransport.HTTP) and not url:
            raise ValueError(f"{transport.value} transport requires a 'url'")

        # Check for duplicate names
        existing = [s for s in self._servers.values() if s.name == name]
        if existing:
            raise ValueError(f"Server '{name}' is already registered")

        server_id = str(uuid.uuid4())
        server = MCPServerConnection(
            server_id=server_id,
            name=name,
            transport=transport,
            command=command,
            args=args or [],
            url=url,
            env=env or {},
            metadata=metadata or {},
        )
        self._servers[server_id] = server
        logger.info(f"MCP server registered: {name} ({transport.value})")
        return server

    async def connect_server(self, server_id: str) -> MCPServerConnection:
        """
        Connect to an MCP server and discover its tools/resources.

        In production, this would:
        - stdio: spawn subprocess, send initialize request
        - SSE: open SSE connection, negotiate capabilities
        - HTTP: send initialize request to endpoint

        Currently: simulates connection and populates with built-in tools.
        """
        server = self._servers.get(server_id)
        if not server:
            raise ValueError(f"Server {server_id} not found")

        server.status = "connecting"
        logger.info(f"Connecting to MCP server: {server.name}")

        try:
            # Simulate connection + capability discovery
            await asyncio.sleep(0.05)  # Simulate network latency

            # In production, this is where we'd parse the server's
            # tools/list and resources/list responses.
            # For now, provide built-in tools based on server name.
            server.tools = self._discover_default_tools(server)
            server.resources = self._discover_default_resources(server)
            server.status = "connected"
            server.connected_at = datetime.now(timezone.utc)
            server.error_message = None

            logger.info(
                f"MCP server connected: {server.name} — "
                f"{len(server.tools)} tools, {len(server.resources)} resources"
            )
            return server

        except Exception as e:
            server.status = "error"
            server.error_message = str(e)
            logger.error(f"Failed to connect MCP server {server.name}: {e}")
            raise

    async def disconnect_server(self, server_id: str) -> None:
        """Disconnect from an MCP server."""
        server = self._servers.get(server_id)
        if not server:
            raise ValueError(f"Server {server_id} not found")

        server.status = "disconnected"
        server.tools = []
        server.resources = []
        server.connected_at = None
        logger.info(f"MCP server disconnected: {server.name}")

    def remove_server(self, server_id: str) -> None:
        """Remove a registered server."""
        if server_id not in self._servers:
            raise ValueError(f"Server {server_id} not found")
        name = self._servers[server_id].name
        del self._servers[server_id]
        logger.info(f"MCP server removed: {name}")

    def list_servers(self) -> List[MCPServerConnection]:
        """List all registered MCP servers."""
        return list(self._servers.values())

    def get_server(self, server_id: str) -> Optional[MCPServerConnection]:
        """Get a specific server by ID."""
        return self._servers.get(server_id)

    def list_all_tools(self) -> List[MCPToolDefinition]:
        """List all tools from all connected servers."""
        tools = []
        for server in self._servers.values():
            if server.status == "connected":
                tools.extend(server.tools)
        return tools

    def list_all_resources(self) -> List[MCPResourceDefinition]:
        """List all resources from all connected servers."""
        resources = []
        for server in self._servers.values():
            if server.status == "connected":
                resources.extend(server.resources)
        return resources

    async def invoke_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Invoke a tool on a connected MCP server.

        In production, this sends a tools/call JSON-RPC request.
        Currently returns a simulated response.
        """
        server = self._servers.get(server_id)
        if not server:
            raise ValueError(f"Server {server_id} not found")
        if server.status != "connected":
            raise ValueError(f"Server '{server.name}' is not connected")

        tool = next((t for t in server.tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found on server '{server.name}'")

        start = datetime.now(timezone.utc)

        # Simulate tool invocation
        result = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "tool": tool_name,
                        "arguments": arguments,
                        "server": server.name,
                        "status": "executed",
                    }),
                }
            ],
            "isError": False,
        }

        elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        log_entry = {
            "invocation_id": str(uuid.uuid4()),
            "server_id": server_id,
            "server_name": server.name,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "elapsed_ms": elapsed_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._invocation_log.append(log_entry)

        logger.info(f"MCP tool invoked: {server.name}/{tool_name} ({elapsed_ms}ms)")
        return result

    async def read_resource(
        self,
        server_id: str,
        resource_uri: str,
    ) -> Dict[str, Any]:
        """Read a resource from a connected MCP server."""
        server = self._servers.get(server_id)
        if not server:
            raise ValueError(f"Server {server_id} not found")
        if server.status != "connected":
            raise ValueError(f"Server '{server.name}' is not connected")

        resource = next((r for r in server.resources if r.uri == resource_uri), None)
        if not resource:
            raise ValueError(f"Resource '{resource_uri}' not found on '{server.name}'")

        return {
            "contents": [
                {
                    "uri": resource_uri,
                    "mimeType": resource.mime_type,
                    "text": f"Content of {resource.name} (simulated)",
                }
            ]
        }

    def get_invocation_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent tool invocation log."""
        return self._invocation_log[-limit:]

    # ─── Default Tool/Resource Discovery ───────────────────────────────

    def _discover_default_tools(
        self, server: MCPServerConnection
    ) -> List[MCPToolDefinition]:
        """
        Provide default tools based on server name/type.
        In production, replaced by actual tools/list RPC.
        """
        name_lower = server.name.lower()
        tools = []

        if "git" in name_lower or "github" in name_lower:
            tools = [
                MCPToolDefinition(
                    name="search_repositories",
                    description="Search GitHub repositories",
                    input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                    server_id=server.server_id,
                ),
                MCPToolDefinition(
                    name="get_file_contents",
                    description="Get file contents from a repository",
                    input_schema={"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "path": {"type": "string"}}},
                    server_id=server.server_id,
                ),
                MCPToolDefinition(
                    name="create_issue",
                    description="Create a GitHub issue",
                    input_schema={"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}}},
                    server_id=server.server_id,
                ),
            ]
        elif "postgres" in name_lower or "db" in name_lower:
            tools = [
                MCPToolDefinition(
                    name="query",
                    description="Execute a read-only SQL query",
                    input_schema={"type": "object", "properties": {"sql": {"type": "string"}}},
                    server_id=server.server_id,
                ),
                MCPToolDefinition(
                    name="list_tables",
                    description="List database tables",
                    input_schema={"type": "object", "properties": {}},
                    server_id=server.server_id,
                ),
            ]
        elif "filesystem" in name_lower or "fs" in name_lower:
            tools = [
                MCPToolDefinition(
                    name="read_file",
                    description="Read file contents",
                    input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                    server_id=server.server_id,
                ),
                MCPToolDefinition(
                    name="write_file",
                    description="Write content to a file",
                    input_schema={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
                    server_id=server.server_id,
                ),
                MCPToolDefinition(
                    name="list_directory",
                    description="List directory contents",
                    input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                    server_id=server.server_id,
                ),
            ]
        else:
            # Generic server — provide a single echo tool
            tools = [
                MCPToolDefinition(
                    name="echo",
                    description=f"Echo tool for {server.name}",
                    input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
                    server_id=server.server_id,
                ),
            ]

        return tools

    def _discover_default_resources(
        self, server: MCPServerConnection
    ) -> List[MCPResourceDefinition]:
        """Default resources based on server type."""
        name_lower = server.name.lower()

        if "postgres" in name_lower or "db" in name_lower:
            return [
                MCPResourceDefinition(
                    uri="postgres://schema",
                    name="Database Schema",
                    description="Current database schema",
                    mime_type="application/json",
                    server_id=server.server_id,
                ),
            ]
        return []


# ─── Singleton ──────────────────────────────────────────────────────

_mcp_manager: Optional[MCPServerManager] = None


def get_mcp_manager() -> MCPServerManager:
    """Get or create the MCP server manager singleton."""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPServerManager()
    return _mcp_manager
