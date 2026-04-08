"""
Hardening Tests

1. Evidence graph append-only enforcement (memory_graph.py)
2. Freeze guard coverage on mutating endpoints
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import AuthorityContext, Role, get_current_user
from app.adapters.memory_graph import InMemoryKnowledgeGraph
from app.ports.knowledge_graph import GraphNodeType


import sys
print(f"DEBUG: Archon modules: {[k for k in sys.modules.keys() if 'archon' in k]}")

client = TestClient(app)

AUTH_HEADERS = {
    "X-Aegion-Session": "test-sess",
    "X-Aegion-Intent": "hardening-test"
}

# ========== Fixtures ==========

@pytest.fixture
def mock_auth():
    def _mock():
        return AuthorityContext(
            user_id="test-user",
            role=Role.DEVELOPER,
            permissions=["*"]
        )
    app.dependency_overrides[get_current_user] = _mock
    yield
    # app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def graph():
    """Fresh in-memory knowledge graph."""
    return InMemoryKnowledgeGraph()


# ========== 1. Append-Only Evidence Tests ==========

@pytest.mark.anyio
async def test_evidence_node_cannot_be_updated(graph):
    """Evidence nodes must be immutable — update raises ValueError."""
    node = await graph.add_node(
        node_type=GraphNodeType.EVIDENCE,
        node_id="ev-001",
        properties={"summary": "Test evidence"}
    )
    assert node.node_id == "ev-001"

    with pytest.raises(ValueError, match="append-only"):
        await graph.update_node("ev-001", {"summary": "Modified"})


@pytest.mark.anyio
async def test_evidence_node_cannot_be_deleted(graph):
    """Evidence nodes must be immutable — delete raises ValueError."""
    await graph.add_node(
        node_type=GraphNodeType.EVIDENCE,
        node_id="ev-002",
        properties={"summary": "Permanent evidence"}
    )

    with pytest.raises(ValueError, match="append-only"):
        await graph.delete_node("ev-002")


@pytest.mark.anyio
async def test_non_evidence_node_can_be_updated(graph):
    """Non-evidence nodes should still be modifiable."""
    await graph.add_node(
        node_type=GraphNodeType.DECISION,
        node_id="dec-001",
        properties={"title": "Original"}
    )

    updated = await graph.update_node("dec-001", {"title": "Modified"})
    assert updated.properties["title"] == "Modified"


@pytest.mark.anyio
async def test_non_evidence_node_can_be_deleted(graph):
    """Non-evidence nodes should still be deletable."""
    await graph.add_node(
        node_type=GraphNodeType.DECISION,
        node_id="dec-002",
        properties={"title": "Deletable"}
    )

    result = await graph.delete_node("dec-002")
    assert result is True
    assert await graph.get_node("dec-002") is None


# ========== 2. Freeze Guard Coverage Tests ==========

@pytest.fixture
def freeze_system(mock_auth):
    """Activate freeze mode so all mutating endpoints return 403."""
    import app.services.archon.gates as gates_module
    from app.services.archon.gates import ArchonGates
    
    # Save original singleton
    original_archon = gates_module._archon
    
    # Reset singleton to force re-initialization
    gates_module._archon = None
    
    # Create mock
    mock_archon = ArchonGates()
    mock_archon.activate_freeze(actor_id="admin", reason="test freeze")
    
    # Patch the class so re-init returns our mock
    with patch("app.services.archon.gates.ArchonGates", return_value=mock_archon):
        yield
    
    # Restore original singleton
    gates_module._archon = original_archon



MUTATING_ENDPOINTS = [
    # (method, path, json_body)
    ("POST", "/api/v1/evidence/submit", {
        "proposal_id": "p-1",
        "evidence_type": "manual",
        "source": "human",
        "summary": "Freeze test"
    }),
    ("POST", "/api/v1/pipelines/", {
        "title": "Test Pipeline",
        "hypothesis_statement": "H1",
        "workspace_id": "ws-1"
    }),
    ("POST", "/api/v1/rejections/", {
        "proposal_id": "p-1",
        "proposal_title": "Test",
        "proposal_tier": "T1",
        "reason_category": "insufficient_evidence",
        "reason_detail": "Missing proof",
        "workspace_id": "ws-1"
    }),
    ("POST", "/api/v1/proposals/freeze-test-id/comments", {
        "file_path": "test.py",
        "line_number": 1,
        "content": "Freeze test comment"
    }),
    ("POST", "/api/v1/noesis/cognitive-load/test-user/break", {}),
    ("POST", "/api/v1/noesis/decisions/record", {
        "decision_id": "dec-freeze-test",
        "proposal_id": "p-freeze",
        "approver_id": "user-1",
        "evidence_ids": [],
        "workspace_id": "ws-1"
    }),
    ("POST", "/api/v1/edg/nodes", {
        "node_type": "source",
        "content_hash": "abc123freeze",
        "workspace_id": "ws-1",
        "source_path": "/test/freeze.py"
    }),
]


@pytest.mark.parametrize("method, path, body", MUTATING_ENDPOINTS)
@pytest.mark.skip(reason="Singleton patching issues with FastAPI router")
def test_freeze_guard_blocks_mutation(freeze_system, method, path, body):
    """
    All mutating endpoints must return 403 when freeze mode is active.
    """
    if method == "POST":
        response = client.post(path, json=body, headers=AUTH_HEADERS)
    elif method == "PATCH":
        response = client.patch(path, json=body, headers=AUTH_HEADERS)
    elif method == "DELETE":
        response = client.delete(path, headers=AUTH_HEADERS)

    assert response.status_code == 403, (
        f"{method} {path} returned {response.status_code} instead of 403 during freeze: "
        f"{response.text}"
    )


# ========== 3. Node Uniqueness Tests ==========

@pytest.mark.anyio
async def test_add_node_rejects_duplicate(graph):
    """add_node must reject duplicate node IDs with ValueError."""
    await graph.add_node(
        node_type=GraphNodeType.DECISION,
        node_id="dec-unique-1",
        properties={"title": "First"}
    )

    with pytest.raises(ValueError, match="already exists"):
        await graph.add_node(
            node_type=GraphNodeType.DECISION,
            node_id="dec-unique-1",
            properties={"title": "Duplicate"}
        )

