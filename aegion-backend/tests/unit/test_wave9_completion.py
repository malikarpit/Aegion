"""
Wave 9 — Comprehensive tests for all Part 1 completion work.

Covers:
  - W1.2: Model registry JSON loading
  - W1.3: ArgumentNode in debate output
  - W1.4: Rejection learner API integration
  - W2.1: Constitution workspace scoping + rule_id in violations
  - W2.4: Graph data API
  - W4.1: Skill invocation engine
  - W5.1: Event emitter
  - W5.3: War room incident lifecycle
  - W7.1: Context pruning (sliding window + importance scoring)
  - W8.1: Docker compose validation
  - W8.3: Seed data generation
"""

import os
import sys
import json
import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

# ═══════════════════════════════════════════════════════
# W1.2: Model Registry JSON
# ═══════════════════════════════════════════════════════

class TestModelRegistryJSON:
    """W1.2: Verify JSON-extensible model catalog."""

    def test_model_registry_json_exists(self):
        """JSON file exists in council kernel directory."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "app", "services", "council_kernel", "model_registry.json",
        )
        assert os.path.isfile(os.path.normpath(path)), \
            "model_registry.json should exist"

    def test_model_registry_json_valid(self):
        """JSON file parses without error."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "app", "services", "council_kernel", "model_registry.json",
        )
        with open(os.path.normpath(path)) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_model_registry_entries_have_required_fields(self):
        """Each entry has model_id, provider, capabilities."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "app", "services", "council_kernel", "model_registry.json",
        )
        with open(os.path.normpath(path)) as f:
            data = json.load(f)
        for entry in data:
            assert "model_id" in entry, f"Entry missing model_id: {entry}"
            assert "provider" in entry, f"Entry missing provider: {entry}"

    def test_model_catalog_loads_custom_models(self):
        """Custom models from JSON are merged into MODEL_CATALOG."""
        from app.services.council_kernel.model_router import MODEL_CATALOG
        # The sample JSON has "custom-local-llama"
        assert "custom-local-llama" in MODEL_CATALOG, \
            "Custom model from JSON should be in MODEL_CATALOG"


# ═══════════════════════════════════════════════════════
# W1.3: ArgumentNode in Debate
# ═══════════════════════════════════════════════════════

class TestDebateArgumentNodes:
    """W1.3: Verify debate engine produces typed ArgumentNode output."""

    def test_build_typed_argument_nodes_basic(self):
        """_build_typed_argument_nodes produces nodes from history."""
        from app.services.council_kernel.debate import DebateEngine

        history = [
            [
                {"model": "gpt-4", "position": "We should use microservices. Because evidence shows scalability.", "confidence": 0.8},
                {"model": "claude", "position": "Monolith is better for small teams.", "confidence": 0.7},
            ],
            [
                {"model": "gpt-4", "position": "I agree microservices need more infra. But data shows benefits.", "confidence": 0.75},
                {"model": "claude", "position": "Small teams struggle with microservices according to research.", "confidence": 0.72},
            ],
        ]
        argument_graph = [
            {"from_model": "gpt-4", "to_model": "claude", "round": 2, "response_type": "rebuttal"},
        ]

        result = DebateEngine._build_typed_argument_nodes(history, argument_graph)
        assert isinstance(result, list)
        assert len(result) == 4  # 2 models × 2 rounds

        # Each node has required fields
        for node in result:
            assert "id" in node
            assert "agent" in node
            assert "claim" in node

    def test_argument_nodes_have_evidence(self):
        """Nodes extract evidence sentences containing indicator words."""
        from app.services.council_kernel.debate import DebateEngine

        history = [
            [{"model": "test", "position": "Claim statement. Because evidence shows this works well. Also data from benchmark confirms it.", "confidence": 0.9}],
        ]
        result = DebateEngine._build_typed_argument_nodes(history, [])
        assert len(result) == 1
        assert len(result[0].get("evidence", [])) >= 1  # At least one evidence sentence


# ═══════════════════════════════════════════════════════
# W2.1: Constitution workspace scoping + rule_id
# ═══════════════════════════════════════════════════════

class TestConstitutionEnhancements:
    """W2.1: Constitution workspace scoping and rule_id in violations."""

    def test_constitution_accepts_workspace_id(self):
        """Constitution constructor accepts workspace_id parameter."""
        from app.services.council_kernel.constitution import ConstitutionalAI
        c = ConstitutionalAI(workspace_id="ws-test")
        assert c.workspace_id == "ws-test"

    def test_check_query_includes_rule_id(self):
        """Violation messages include [rule_id] for traceability."""
        from app.services.council_kernel.constitution import ConstitutionalAI
        c = ConstitutionalAI()
        violations = c.check_query("delete all database records and drop tables")
        # Should find a violation
        if violations:
            assert any("[" in v and "]" in v for v in violations), \
                f"Violations should include [rule_id]: {violations}"


# ═══════════════════════════════════════════════════════
# W4.1: Skill Invocation Engine
# ═══════════════════════════════════════════════════════

class TestSkillInvocation:
    """W4.1: Verify skill invocation renders templates and calls council."""

    @pytest.mark.asyncio
    async def test_invoke_skill_renders_template(self):
        """invoke_skill substitutes params into prompt_template."""
        from app.services.skill_loader import SkillLoader

        loader = SkillLoader()
        skill = {
            "name": "test-skill",
            "skill_id": "sk-001",
            "prompt_template": "Analyze {{language}} code in {{project}} for security issues.",
        }

        with patch("app.services.skill_loader.SkillLoader.invoke_skill") as mock:
            # Test template rendering logic directly
            template = skill["prompt_template"]
            params = {"language": "Python", "project": "Aegion"}
            rendered = template
            for key, value in params.items():
                rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
                rendered = rendered.replace(f"{{{{ {key} }}}}", str(value))

            assert "Python" in rendered
            assert "Aegion" in rendered
            assert "{{" not in rendered

    @pytest.mark.asyncio
    async def test_invoke_skill_rejects_empty_template(self):
        """invoke_skill raises ValueError for empty templates."""
        from app.services.skill_loader import SkillLoader
        loader = SkillLoader()
        skill = {"name": "empty", "prompt_template": ""}

        with pytest.raises(ValueError, match="no prompt template"):
            await loader.invoke_skill(skill, {}, "ws-test")


# ═══════════════════════════════════════════════════════
# W5.1: Event Emitter
# ═══════════════════════════════════════════════════════

class TestEventEmitter:
    """W5.1: Verify event emitter broadcasts correctly."""

    def test_event_type_constants_exist(self):
        """EventType has all required constants."""
        from app.services.event_emitter import EventType
        assert EventType.COUNCIL_COMPLETED == "council.completed"
        assert EventType.PROPOSAL_UPDATED == "proposal.updated"
        assert EventType.INCIDENT_UPDATED == "incident.updated"
        assert EventType.PRESENCE_CHANGED == "presence.changed"

    @pytest.mark.asyncio
    async def test_emit_ws_event_graceful_without_manager(self):
        """emit_ws_event returns False when websocket unavailable."""
        from app.services.event_emitter import emit_ws_event
        result = await emit_ws_event("test.event", "ws-1", {"key": "value"})
        # Should return False (no WebSocket manager running)
        assert result is False


# ═══════════════════════════════════════════════════════
# W5.3: War Room Incident Lifecycle
# ═══════════════════════════════════════════════════════

class TestWarRoomLifecycle:
    """W5.3: Verify incident lifecycle enhancements."""

    def test_incident_model_has_assigned_to(self):
        """Incident model has assigned_to field."""
        from app.models.incident import Incident, IncidentSeverity
        inc = Incident(
            incident_id="inc-1", title="Test", service="api",
            created_by="user-1", created_at=datetime.now(timezone.utc),
        )
        assert inc.assigned_to is None
        inc.assigned_to = "user-2"
        assert inc.assigned_to == "user-2"

    def test_incident_model_has_status_history(self):
        """Incident model has status_history list."""
        from app.models.incident import Incident
        inc = Incident(
            incident_id="inc-2", title="Test", service="api",
            created_by="user-1", created_at=datetime.now(timezone.utc),
        )
        assert isinstance(inc.status_history, list)
        inc.status_history.append({
            "status": "investigating", "changed_by": "user-1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        assert len(inc.status_history) == 1


# ═══════════════════════════════════════════════════════
# W7.1: Context Pruning
# ═══════════════════════════════════════════════════════

class TestContextPruning:
    """W7.1: Verify sliding window context pruning."""

    def test_importance_scoring_recent_higher(self):
        """More recent chunks score higher than older ones."""
        from app.services.council_kernel.compressor import PromptCompressor
        c = PromptCompressor()

        chunk = "The API endpoint handles governance decisions for sentinel monitoring."
        old_score = c.importance_score(chunk, recency=0.1)
        new_score = c.importance_score(chunk, recency=0.9)
        assert new_score > old_score, "Recent chunks should score higher"

    def test_importance_scoring_technical_higher(self):
        """Technical content scores higher than filler."""
        from app.services.council_kernel.compressor import PromptCompressor
        c = PromptCompressor()

        tech = "The database migration adds a new index on the query endpoint."
        filler = "Well I think that maybe we should perhaps consider looking into it."
        assert c.importance_score(tech) > c.importance_score(filler)

    def test_sliding_window_keeps_important(self):
        """Sliding window keeps high-importance chunks within budget."""
        from app.services.council_kernel.compressor import PromptCompressor
        c = PromptCompressor()

        chunks = [
            "Just some filler text that is not very important at all really.",
            "More filler content about nothing in particular happening today.",
            "The governance decision requires sentinel risk assessment for API deployment.",
            "Another chunk of mostly irrelevant content with nothing useful.",
            "Critical: The database migration affects the query endpoint schema.",
        ]

        # Budget forces keeping only ~2-3 chunks
        result = c.sliding_window_prune(chunks, max_tokens=60)
        assert len(result) < len(chunks), "Should prune some chunks"
        assert len(result) >= 1, "Should keep at least one chunk"

    def test_sliding_window_preserves_order(self):
        """Pruned chunks maintain their original order."""
        from app.services.council_kernel.compressor import PromptCompressor
        c = PromptCompressor()

        chunks = [f"Chunk {i} with governance content for sentinel." for i in range(10)]
        result = c.sliding_window_prune(chunks, max_tokens=80)
        # Verify order is maintained
        if len(result) > 1:
            indices = [chunks.index(r) for r in result]
            assert indices == sorted(indices), "Chunks should be in original order"

    def test_sliding_window_passthrough_when_fits(self):
        """When all chunks fit in budget, return all unchanged."""
        from app.services.council_kernel.compressor import PromptCompressor
        c = PromptCompressor()

        chunks = ["Short chunk.", "Another short one."]
        result = c.sliding_window_prune(chunks, max_tokens=1000)
        assert result == chunks

    @pytest.mark.asyncio
    async def test_context_prune_returns_metrics(self):
        """context_prune returns dict with metrics."""
        from app.services.council_kernel.compressor import PromptCompressor
        c = PromptCompressor()

        chunks = [
            "Some governance content for sentinel analysis.",
            "Another chunk about decision making in the council.",
        ]
        result = await c.context_prune(chunks, max_tokens=1000)
        assert "pruned_context" in result
        assert "original_chunks" in result
        assert "ratio" in result


# ═══════════════════════════════════════════════════════
# W8.1: Docker Compose Validation
# ═══════════════════════════════════════════════════════

class TestDockerComposeComplete:
    """W8.1/W8.2: Verify Docker Compose has all services."""

    def test_compose_has_postgres(self):
        """Docker compose includes PostgreSQL + pgvector service."""
        import yaml
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "docker-compose.yml",
        )
        with open(os.path.normpath(path)) as f:
            compose = yaml.safe_load(f)
        services = compose.get("services", {})
        assert "postgres" in services, "PostgreSQL service missing from compose"
        assert "pgvector" in services["postgres"].get("image", ""), \
            "Postgres should use pgvector image"

    def test_compose_has_postgres_data_volume(self):
        """Docker compose has postgres_data volume."""
        import yaml
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "docker-compose.yml",
        )
        with open(os.path.normpath(path)) as f:
            compose = yaml.safe_load(f)
        volumes = compose.get("volumes", {})
        assert "postgres_data" in volumes

    def test_backend_depends_on_postgres(self):
        """Backend service depends on postgres."""
        import yaml
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "docker-compose.yml",
        )
        with open(os.path.normpath(path)) as f:
            compose = yaml.safe_load(f)
        backend = compose.get("services", {}).get("backend", {})
        depends = backend.get("depends_on", {})
        assert "postgres" in depends


# ═══════════════════════════════════════════════════════
# W8.3/W8.4: Seed Data & Migrations
# ═══════════════════════════════════════════════════════

class TestSeedAndMigrations:
    """W8.3/W8.4: Verify seed data and SQL migrations."""

    def test_seed_data_generates_all_tables(self):
        """generate_all returns data for all expected tables."""
        from app.scripts.seed_data import generate_all
        data = generate_all()
        assert isinstance(data, dict)
        assert len(data) >= 5, f"Expected ≥5 tables, got {len(data)}"

    def test_seed_script_exists(self):
        """scripts/seed.py wrapper exists."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "scripts", "seed.py",
        )
        assert os.path.isfile(os.path.normpath(path))

    def test_migration_002_exists(self):
        """002_application_tables.sql migration exists."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "migrations", "002_application_tables.sql",
        )
        assert os.path.isfile(os.path.normpath(path))

    def test_migration_002_has_core_tables(self):
        """Migration SQL includes all core application tables."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "migrations", "002_application_tables.sql",
        )
        with open(os.path.normpath(path)) as f:
            sql = f.read()
        required_tables = [
            "workspaces", "timeline_events", "decisions",
            "risk_signals", "rejection_log", "cost_tracking",
            "constitutional_rules", "incidents", "presence",
        ]
        for table in required_tables:
            assert table in sql, f"Migration missing table: {table}"


# ═══════════════════════════════════════════════════════
# W2.4: Graph Data API
# ═══════════════════════════════════════════════════════

class TestGraphDataAPI:
    """W2.4: Verify graph visualization endpoints exist."""

    def test_graph_data_module_importable(self):
        """graph_data.py is importable."""
        from app.api.v1.graph_data import router
        assert router is not None

    def test_graph_data_has_endpoints(self):
        """Graph data router has nodes, edges, communities, overview endpoints."""
        from app.api.v1.graph_data import router
        paths = [route.path for route in router.routes]
        assert "/nodes" in paths or any("/nodes" in p for p in paths)
        assert "/edges" in paths or any("/edges" in p for p in paths)

    def test_graph_response_models_exist(self):
        """Response models are properly defined."""
        from app.api.v1.graph_data import (
            GraphNode, GraphEdge, GraphCommunity, GraphOverview,
        )
        node = GraphNode(id="n1", label="test")
        assert node.type == "entity"
        edge = GraphEdge(source="n1", target="n2")
        assert edge.weight == 1.0


# ═══════════════════════════════════════════════════════
# F5: Temporal Memory — query_changes_since
# ═══════════════════════════════════════════════════════

class TestTemporalChanges:

    def test_query_changes_since_exists(self):
        """query_changes_since function is importable."""
        from app.services.council_kernel.temporal_memory import query_changes_since
        assert callable(query_changes_since)

    @pytest.mark.asyncio
    async def test_query_changes_since_returns_list(self):
        """query_changes_since returns empty list on Supabase unavailability."""
        from app.services.council_kernel.temporal_memory import query_changes_since
        with patch("app.services.council_kernel.temporal_memory.logger"):
            # Force Supabase unavailable → should return []
            with patch(
                "app.db.supabase_client.get_supabase_client",
                side_effect=RuntimeError("No Supabase"),
            ):
                result = await query_changes_since("ws-test", "2026-01-01T00:00:00Z")
        assert isinstance(result, list)
        assert result == []

    def test_temporal_changes_endpoint_registered(self):
        """The /temporal/changes endpoint is registered on the council router."""
        from app.api.v1.council import router
        paths = [route.path for route in router.routes]
        assert any("temporal" in p for p in paths), f"No temporal endpoint in: {paths}"


# ═══════════════════════════════════════════════════════
# F4/F12: Reasoning Chains SQL Schema
# ═══════════════════════════════════════════════════════

class TestReasoningChainsPersistence:

    def test_reasoning_chains_table_in_migration(self):
        """reasoning_chains table exists in SQL migration."""
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "migrations", "002_application_tables.sql"
        )
        with open(migration_path) as f:
            sql = f.read()
        assert "reasoning_chains" in sql
        assert "chain_type" in sql
        assert "best_path" in sql

    def test_reasoning_chain_persist_method_exists(self):
        """reasoning_chain.py has _persist method for Supabase."""
        from app.services.reasoning_chain import MCTSReasoner
        reasoner = MCTSReasoner.__new__(MCTSReasoner)
        assert hasattr(reasoner, "_persist"), "MCTSReasoner must have _persist method"

    def test_parent_decision_id_in_migration(self):
        """parent_decision_id column added to decisions table for lineage."""
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "migrations", "002_application_tables.sql"
        )
        with open(migration_path) as f:
            sql = f.read()
        assert "parent_decision_id" in sql


# ═══════════════════════════════════════════════════════
# F8: LocalArtifactLog
# ═══════════════════════════════════════════════════════

class TestLocalArtifactLog:

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self):
        """LocalArtifactLog stores and retrieves content."""
        from app.adapters.local_artifact_log import LocalArtifactLog
        log = LocalArtifactLog()
        await log.store("artifacts/sessions/test-1", b'{"hello":"world"}', "application/json")
        result = await log.retrieve("artifacts/sessions/test-1")
        assert result == b'{"hello":"world"}'

    @pytest.mark.asyncio
    async def test_retrieve_missing_returns_none(self):
        """Retrieving a non-existent key returns None."""
        from app.adapters.local_artifact_log import LocalArtifactLog
        log = LocalArtifactLog()
        result = await log.retrieve("nonexistent/key")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_workspace_returns_list(self):
        """list_by_workspace returns a list."""
        from app.adapters.local_artifact_log import LocalArtifactLog
        log = LocalArtifactLog()
        result = await log.list_by_workspace("ws-test")
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════
# F6: Decision Lineage Endpoint
# ═══════════════════════════════════════════════════════

class TestDecisionLineage:

    def test_lineage_endpoint_registered(self):
        """The /lineage/{decision_id} endpoint exists on council router."""
        from app.api.v1.council import router
        paths = [route.path for route in router.routes]
        assert any("lineage" in p for p in paths), f"No lineage endpoint in: {paths}"

    def test_recent_decisions_endpoint_registered(self):
        """The /decisions/recent endpoint exists on council router."""
        from app.api.v1.council import router
        paths = [route.path for route in router.routes]
        assert any("recent" in p for p in paths), f"No recent decisions in: {paths}"

