"""
Integration Tests — MCP, Browser, ChatOps.

Tests all Phase E enhancements:
- MCP Server management (register, connect, discover tools, invoke)
- Browser tool (fetch, browse, extract)
- ChatOps (webhook config, notifications, log)
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import AuthorityContext, Role, get_current_user


def mock_dev_auth():
    return AuthorityContext(
        user_id="dev-user",
        role=Role.DEVELOPER,
        permissions=["propose"]
    )


@pytest.fixture(autouse=True)
def _override_auth():
    """Ensure auth override is set for every test in this module."""
    app.dependency_overrides[get_current_user] = mock_dev_auth
    yield
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)
AUTH_HEADERS = {
    "X-Aegion-Session": "test-sess-phase-e",
    "X-Aegion-Intent": "test-intent",
}


# ─── MCP Server Management ────────────────────────────────────────


class TestMCPServerManagement:
    """Tests for MCP server registration, connection, and tool discovery."""

    def test_register_mcp_server(self):
        """Register an MCP server with stdio transport."""
        response = client.post(
            "/api/v1/tools/mcp/servers",
            json={
                "name": "test-github-server",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-github-server"
        assert data["transport"] == "stdio"
        assert data["status"] == "disconnected"
        self.__class__.server_id = data["server_id"]

    def test_list_mcp_servers(self):
        """List registered MCP servers."""
        response = client.get("/api/v1/tools/mcp/servers", headers=AUTH_HEADERS)
        assert response.status_code == 200
        servers = response.json()
        assert len(servers) >= 1
        assert any(s["name"] == "test-github-server" for s in servers)

    def test_connect_mcp_server(self):
        """Connect to a registered MCP server and discover tools."""
        server_id = self.__class__.server_id
        response = client.post(
            f"/api/v1/tools/mcp/servers/{server_id}/connect",
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["tool_count"] > 0  # Should discover GitHub tools

    def test_list_mcp_tools(self):
        """List all tools from connected MCP servers."""
        response = client.get("/api/v1/tools/mcp/tools", headers=AUTH_HEADERS)
        assert response.status_code == 200
        tools = response.json()
        assert len(tools) > 0
        # GitHub server should expose search_repositories
        tool_names = [t["name"] for t in tools]
        assert "search_repositories" in tool_names

    def test_invoke_mcp_tool(self):
        """Invoke a tool on a connected MCP server."""
        server_id = self.__class__.server_id
        response = client.post(
            f"/api/v1/tools/mcp/servers/{server_id}/invoke",
            json={
                "tool_name": "search_repositories",
                "arguments": {"query": "aegion"},
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert data["isError"] is False

    def test_disconnect_mcp_server(self):
        """Disconnect from an MCP server."""
        server_id = self.__class__.server_id
        response = client.post(
            f"/api/v1/tools/mcp/servers/{server_id}/disconnect",
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "disconnected"

    def test_remove_mcp_server(self):
        """Remove a registered MCP server."""
        server_id = self.__class__.server_id
        response = client.delete(
            f"/api/v1/tools/mcp/servers/{server_id}",
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 204


# ─── Browser Tool ─────────────────────────────────────────────────


class TestBrowserTool:
    """Tests for browser tool: browse, extract."""

    def test_browser_browse(self):
        """Browse a page and extract content."""
        from unittest.mock import patch
        # Mock the underlying HTTP request or the entire browser service to avoid SSL errors
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = mock_client_class.return_value.__aenter__.return_value
            mock_resp = mock_client.get.return_value
            mock_resp.status_code = 200
            mock_resp.text = "<html><head><title>Mocked Example</title></head><body><h1>Hello</h1><p>Test Content</p></body></html>"
            mock_resp.url = "https://example.com"
            mock_resp.headers = {"content-type": "text/html"}
            
            response = client.post(
                "/api/v1/tools/browser/browse",
                json={
                    "url": "https://example.com",
                    "extract_text": True,
                    "actions": [
                        {"type": "wait", "delay_ms": 100},
                    ],
                },
                headers=AUTH_HEADERS,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "https://example.com"
        assert "title" in data
        assert data["actions_executed"] == 1

    def test_browser_extract(self):
        """Extract structured data from a page."""
        from unittest.mock import patch
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = mock_client_class.return_value.__aenter__.return_value
            mock_resp = mock_client.get.return_value
            mock_resp.status_code = 200
            mock_resp.text = "<html><head><title>Mocked Example</title></head><body><h1>Hello</h1><a href='#'>Link</a></body></html>"
            mock_resp.url = "https://example.com"
            mock_resp.headers = {"content-type": "text/html"}
            
            response = client.post(
                "/api/v1/tools/browser/extract",
                json={
                    "url": "https://example.com",
                    "extract_links": True,
                    "extract_headings": True,
                },
                headers=AUTH_HEADERS,
            )
        assert response.status_code == 200
        data = response.json()
        assert "title" in data
        assert isinstance(data["headings"], list)
        assert isinstance(data["links"], list)

    def test_browser_screenshot_not_configured(self):
        """Screenshot returns not_configured when engine unset."""
        response = client.post(
            "/api/v1/tools/browser/screenshot",
            json={"url": "https://example.com"},
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("not_configured", "not_implemented")


# ─── ChatOps ──────────────────────────────────────────────────────


class TestChatOps:
    """Tests for ChatOps webhook config and notifications."""

    def test_configure_webhook(self):
        """Configure a Slack webhook for a workspace."""
        response = client.post(
            "/api/v1/chatops/webhooks/configure",
            json={
                "workspace_id": "ws-test-001",
                "webhook_url": "https://hooks.slack.com/services/FAKE/WEBHOOK/URL",
                "channel": "#test-channel",
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["workspace_id"] == "ws-test-001"
        assert data["enabled"] is True

    def test_list_webhooks(self):
        """List all configured webhooks."""
        response = client.get("/api/v1/chatops/webhooks", headers=AUTH_HEADERS)
        assert response.status_code == 200
        webhooks = response.json()
        assert len(webhooks) >= 1

    def test_get_webhook(self):
        """Get webhook for a specific workspace."""
        response = client.get(
            "/api/v1/chatops/webhooks/ws-test-001",
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["channel"] == "#test-channel"

    def test_send_notification(self):
        """Send a manual notification (will fail delivery to fake URL, but tests the flow)."""
        response = client.post(
            "/api/v1/chatops/notify",
            json={
                "workspace_id": "ws-test-001",
                "event_type": "proposal.created",
                "title": "Test Proposal",
                "message": "A test proposal was created.",
                "level": "info",
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        # Delivery may fail (fake URL) but the endpoint should work

    def test_notification_log(self):
        """Get notification delivery history."""
        response = client.get(
            "/api/v1/chatops/notifications/log",
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        log = response.json()
        assert isinstance(log, list)

    def test_remove_webhook(self):
        """Remove webhook config."""
        response = client.delete(
            "/api/v1/chatops/webhooks/ws-test-001",
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "removed"
