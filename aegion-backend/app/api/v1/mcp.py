"""
Aegion API v1 - MCP Tool Registry.

Model Context Protocol compatible tool registration and invocation.
Enables external tool extensibility via a standard protocol.

Feature: MCP/ACP-style extensibility.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid
import httpx

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger


router = APIRouter(prefix="/tools", tags=["mcp-tools"])


# ========== In-Memory Store ==========
_tool_registry: dict[str, "ToolRegistration"] = {}


# ========== Models ==========


class ToolRegistration(BaseModel):
    """An externally registered tool."""
    tool_id: str
    name: str
    description: str
    input_schema: Dict[str, Any]  # JSON Schema for tool inputs
    handler_url: Optional[str] = None  # HTTP endpoint for remote tools
    handler_type: str = "http"  # http, local, stdio
    version: str = "1.0.0"
    provider: str = "external"
    registered_by: str
    registered_at: datetime
    enabled: bool = True
    metadata: Dict[str, Any] = {}


class RegisterToolRequest(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler_url: Optional[str] = None
    handler_type: str = "http"
    version: str = "1.0.0"
    metadata: Optional[Dict[str, Any]] = None


class InvokeToolRequest(BaseModel):
    arguments: Dict[str, Any]
    timeout_seconds: int = 30


class ToolResponse(BaseModel):
    tool_id: str
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler_type: str
    version: str
    provider: str
    enabled: bool
    registered_at: str


class InvokeResponse(BaseModel):
    tool_id: str
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    duration_ms: int = 0


# ========== Endpoints ==========


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def register_tool(
    request: RegisterToolRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Register an external tool (MCP pattern)."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # Check for duplicate name
    existing = [t for t in _tool_registry.values() if t.name == request.name]
    if existing:
        raise HTTPException(status_code=409, detail=f"Tool '{request.name}' already registered")

    tool_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    tool = ToolRegistration(
        tool_id=tool_id,
        name=request.name,
        description=request.description,
        input_schema=request.input_schema,
        handler_url=request.handler_url,
        handler_type=request.handler_type,
        version=request.version,
        registered_by=user.user_id,
        registered_at=now,
        metadata=request.metadata or {},
    )

    _tool_registry[tool_id] = tool
    logger.info(f"Tool registered: {tool_id} name={request.name}")

    return ToolResponse(
        tool_id=tool.tool_id,
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema,
        handler_type=tool.handler_type,
        version=tool.version,
        provider=tool.provider,
        enabled=tool.enabled,
        registered_at=tool.registered_at.isoformat(),
    )


@router.get("", response_model=List[ToolResponse])
async def list_tools(
    enabled_only: bool = True,
    user: AuthorityContext = Depends(get_current_user),
):
    """List all registered tools."""
    tools = list(_tool_registry.values())
    if enabled_only:
        tools = [t for t in tools if t.enabled]

    return [
        ToolResponse(
            tool_id=t.tool_id,
            name=t.name,
            description=t.description,
            input_schema=t.input_schema,
            handler_type=t.handler_type,
            version=t.version,
            provider=t.provider,
            enabled=t.enabled,
            registered_at=t.registered_at.isoformat(),
        )
        for t in tools
    ]

# ========== MCP Server Management ==========

from ...services.mcp_server import get_mcp_manager, MCPTransport


class RegisterMCPServerRequest(BaseModel):
    name: str
    transport: str  # "stdio", "sse", "http"
    command: Optional[str] = None
    args: Optional[List[str]] = None
    url: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None


class MCPServerResponse(BaseModel):
    server_id: str
    name: str
    transport: str
    status: str
    tool_count: int = 0
    resource_count: int = 0
    connected_at: Optional[str] = None
    error_message: Optional[str] = None


class MCPToolResponse(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_id: str
    server_name: Optional[str] = None


class MCPInvokeRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]


def _server_to_response(server) -> MCPServerResponse:
    return MCPServerResponse(
        server_id=server.server_id,
        name=server.name,
        transport=server.transport.value,
        status=server.status,
        tool_count=len(server.tools),
        resource_count=len(server.resources),
        connected_at=server.connected_at.isoformat() if server.connected_at else None,
        error_message=server.error_message,
    )


@router.post("/mcp/servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def register_mcp_server(
    request: RegisterMCPServerRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Register an external MCP server configuration."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    mgr = get_mcp_manager()
    try:
        transport = MCPTransport(request.transport)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid transport: {request.transport}")

    try:
        server = mgr.register_server(
            name=request.name,
            transport=transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            metadata=request.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return _server_to_response(server)


@router.get("/mcp/servers", response_model=List[MCPServerResponse])
async def list_mcp_servers(
    user: AuthorityContext = Depends(get_current_user),
):
    """List all registered MCP servers."""
    mgr = get_mcp_manager()
    return [_server_to_response(s) for s in mgr.list_servers()]


@router.post("/mcp/servers/{server_id}/connect", response_model=MCPServerResponse)
async def connect_mcp_server(
    server_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Connect to a registered MCP server and discover tools/resources."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    mgr = get_mcp_manager()
    try:
        server = await mgr.connect_server(server_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _server_to_response(server)


@router.post("/mcp/servers/{server_id}/disconnect")
async def disconnect_mcp_server(
    server_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Disconnect from an MCP server."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    mgr = get_mcp_manager()
    try:
        await mgr.disconnect_server(server_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "disconnected", "server_id": server_id}


@router.delete("/mcp/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_mcp_server(
    server_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Remove a registered MCP server."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    mgr = get_mcp_manager()
    try:
        mgr.remove_server(server_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/mcp/tools", response_model=List[MCPToolResponse])
async def list_mcp_tools(
    user: AuthorityContext = Depends(get_current_user),
):
    """List all tools from all connected MCP servers."""
    mgr = get_mcp_manager()
    tools = mgr.list_all_tools()
    servers = {s.server_id: s.name for s in mgr.list_servers()}
    return [
        MCPToolResponse(
            name=t.name,
            description=t.description,
            input_schema=t.input_schema,
            server_id=t.server_id,
            server_name=servers.get(t.server_id),
        )
        for t in tools
    ]


@router.post("/mcp/servers/{server_id}/invoke")
async def invoke_mcp_tool(
    server_id: str,
    request: MCPInvokeRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Invoke a tool on a connected MCP server."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    mgr = get_mcp_manager()
    try:
        result = await mgr.invoke_tool(server_id, request.tool_name, request.arguments)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get("/{tool_name}", response_model=ToolResponse)
async def get_tool(
    tool_name: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get a specific tool by name."""
    tool = next((t for t in _tool_registry.values() if t.name == tool_name), None)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    return ToolResponse(
        tool_id=tool.tool_id,
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema,
        handler_type=tool.handler_type,
        version=tool.version,
        provider=tool.provider,
        enabled=tool.enabled,
        registered_at=tool.registered_at.isoformat(),
    )


@router.post("/{tool_name}/invoke", response_model=InvokeResponse)
async def invoke_tool(
    tool_name: str,
    request: InvokeToolRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Invoke a registered tool with arguments."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    tool = next((t for t in _tool_registry.values() if t.name == tool_name), None)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    if not tool.enabled:
        raise HTTPException(status_code=403, detail=f"Tool '{tool_name}' is disabled")

    start = datetime.now(timezone.utc)

    try:
        if tool.handler_type == "http" and tool.handler_url:
            # Remote HTTP tool invocation
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    tool.handler_url,
                    json={"arguments": request.arguments},
                    timeout=request.timeout_seconds,
                )
                resp.raise_for_status()
                result = resp.json()
        else:
            # Local/mock invocation
            result = {
                "tool": tool_name,
                "arguments": request.arguments,
                "status": "executed",
                "message": f"Tool '{tool_name}' executed (local handler)",
            }

        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        logger.info(f"Tool invoked: {tool_name} by {user.user_id}, duration={elapsed}ms")

        return InvokeResponse(
            tool_id=tool.tool_id,
            tool_name=tool.name,
            success=True,
            result=result,
            duration_ms=elapsed,
        )

    except Exception as e:
        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        logger.error(f"Tool invocation failed: {tool_name}: {e}")

        return InvokeResponse(
            tool_id=tool.tool_id,
            tool_name=tool.name,
            success=False,
            error=str(e),
            duration_ms=elapsed,
        )


@router.delete("/{tool_name}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_tool(
    tool_name: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Unregister a tool."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    tool = next((t for t in _tool_registry.values() if t.name == tool_name), None)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    del _tool_registry[tool.tool_id]
    logger.info(f"Tool unregistered: {tool_name}")

