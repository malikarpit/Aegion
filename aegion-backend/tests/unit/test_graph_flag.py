"""
Graph Provider Feature Flag Tests.

Validates:
- Default behavior (Memory)
- Feature flag behavior (Neo4j -> fallback warning)
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from app.services.graph_provider import get_shared_graph, InMemoryKnowledgeGraph

class TestGraphProviderFlag:
    def teardown_method(self):
        # Reset singleton to ensure clean state
        import app.services.graph_provider as gp
        gp._shared_graph = None
        gp._shared_service = None

    def test_default_is_memory(self):
        with patch.dict(os.environ, {}, clear=True):
            graph = get_shared_graph()
            assert isinstance(graph, InMemoryKnowledgeGraph)

    def test_explicit_memory(self):
        with patch.dict(os.environ, {"GRAPH_BACKEND": "memory"}):
            graph = get_shared_graph()
            assert isinstance(graph, InMemoryKnowledgeGraph)

    def test_neo4j_fallback(self):
        with patch.dict(os.environ, {"GRAPH_BACKEND": "neo4j"}):
            with patch("app.adapters.neo4j_graph.Neo4jKnowledgeGraph") as MockNeo4j:
                graph = get_shared_graph()
                assert graph == MockNeo4j.return_value
                assert isinstance(graph, MagicMock)
