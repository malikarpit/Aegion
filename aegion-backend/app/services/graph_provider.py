"""
Aegion Shared Graph Provider.

Doctrine: "One graph. One truth. All modules speak to the same knowledge base."

Centralizes the graph singleton so that all API modules share a single
graph instance. Supports three backends:

  - GRAPH_BACKEND=memory    (default) — InMemoryKnowledgeGraph + JSON snapshots
  - GRAPH_BACKEND=postgres  (Phase 6) — PostgresKnowledgeGraph via Supabase
  - GRAPH_BACKEND=neo4j              — Neo4jKnowledgeGraph (requires running Neo4j)

Persistence:
  Memory:   JSON snapshot file (data/graph_snapshot.json), auto-flushed every 30s.
  Postgres: Durable by default via Supabase PostgreSQL — no snapshot needed.
  Neo4j:    Durable by default — no snapshot needed.
"""

import os
import json
import asyncio
import atexit
import signal
from typing import Optional, Dict, Any, Union

from ..adapters.memory_graph import InMemoryKnowledgeGraph
from ..adapters.postgres.postgres_graph import PostgresKnowledgeGraph, PostgresConfig
from ..ports.knowledge_graph import KnowledgeGraphPort
from ..services.noesis import GraphService
from ..core.logging import logger

_shared_graph: Optional[KnowledgeGraphPort] = None
_shared_service: Optional[GraphService] = None
_snapshot_path: Optional[str] = None
_dirty: bool = False
_auto_flush_task: Optional[asyncio.Task] = None
_shutdown_registered: bool = False
_backend_type: str = "memory"  # or "neo4j"

# Default persistence location
_DEFAULT_SNAPSHOT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
)
_DEFAULT_SNAPSHOT_PATH = os.path.join(_DEFAULT_SNAPSHOT_DIR, "graph_snapshot.json")
_AUTO_FLUSH_INTERVAL = 30.0  # seconds


def _ensure_data_dir() -> None:
    """Create data directory if it doesn't exist."""
    os.makedirs(os.path.dirname(_DEFAULT_SNAPSHOT_PATH), exist_ok=True)


def _load_snapshot(path: str) -> Optional[Dict[str, Any]]:
    """Load snapshot from disk. Returns None if file doesn't exist."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load graph snapshot from {path}: {e}")
        return None


def _save_snapshot_sync(snapshot: Dict[str, Any], path: str) -> None:
    """
    Atomically save snapshot to disk (temp-file + os.replace).

    This is synchronous for use in signal handlers and atexit.
    """
    _ensure_data_dir()
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(snapshot, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except OSError as e:
        logger.error(f"Failed to save graph snapshot: {e}")


def _sync_flush_if_dirty(signum=None, frame=None) -> None:
    """Synchronous emergency flush for signal handlers + atexit."""
    global _dirty
    if not _dirty or _shared_graph is None:
        return

    try:
        import asyncio as _aio

        loop = None
        try:
            loop = _aio.get_running_loop()
        except RuntimeError:
            pass

        if loop and loop.is_running():
            # Can't await in signal handler — use sync export
            snapshot = _export_snapshot_sync()
        else:
            snapshot = _aio.run(_shared_graph.export_snapshot())

        if snapshot:
            _save_snapshot_sync(snapshot, _snapshot_path or _DEFAULT_SNAPSHOT_PATH)
            _dirty = False
            logger.info("Graph snapshot flushed on shutdown")
    except Exception as e:
        logger.error(f"Failed to flush graph on shutdown: {e}")


def _export_snapshot_sync() -> Optional[Dict[str, Any]]:
    """Synchronous snapshot export (for signal handlers)."""
    if _shared_graph is None:
        return None

    from datetime import datetime, timezone

    nodes_data = {}
    for nid, n in _shared_graph._nodes.items():
        nodes_data[nid] = {
            "node_id": n.node_id,
            "node_type": n.node_type.value,
            "properties": n.properties,
            "labels": list(n.labels),
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "updated_at": n.updated_at.isoformat() if n.updated_at else None,
        }

    edges_data = {}
    for eid, e in _shared_graph._edges.items():
        edges_data[eid] = {
            "edge_id": e.edge_id,
            "source_id": e.source_id,
            "target_id": e.target_id,
            "edge_type": e.edge_type.value,
            "properties": e.properties,
            "weight": e.weight,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }

    return {
        "nodes": nodes_data,
        "edges": edges_data,
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


def _register_shutdown_handlers() -> None:
    """Register signal + atexit handlers for crash-safe graph persistence."""
    global _shutdown_registered
    if _shutdown_registered:
        return
    _shutdown_registered = True

    atexit.register(_sync_flush_if_dirty)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            prev = signal.getsignal(sig)
            def _handler(s, f, _prev=prev):
                _sync_flush_if_dirty(s, f)
                if callable(_prev) and _prev not in (signal.SIG_IGN, signal.SIG_DFL):
                    _prev(s, f)
            signal.signal(sig, _handler)
        except (ValueError, OSError):
            pass  # Can't set signals outside main thread


async def _auto_flush_loop() -> None:
    """Background task: periodically persist dirty graph to disk."""
    global _dirty
    while True:
        await asyncio.sleep(_AUTO_FLUSH_INTERVAL)
        if _dirty and _shared_graph is not None:
            try:
                await persist_graph()
            except Exception as e:
                logger.error(f"Auto-flush failed: {e}")


# ========== Public API ==========


def get_shared_graph_service() -> GraphService:
    """
    Get the application-wide shared GraphService instance.

    All modules MUST use this instead of creating standalone graphs.
    """
    global _shared_graph, _shared_service
    if _shared_service is None:
        _shared_graph = InMemoryKnowledgeGraph()
        _shared_service = GraphService(_shared_graph)
    return _shared_service


def get_shared_graph() -> KnowledgeGraphPort:
    """Get the raw graph adapter (for low-level operations)."""
    global _shared_graph, _shared_service, _backend_type
    if _shared_graph is None:
        backend = os.getenv("GRAPH_BACKEND", "postgres").lower()
        if backend == "postgres":
            logger.info("Creating PostgresKnowledgeGraph backend (Phase 87)")
            _shared_graph = PostgresKnowledgeGraph(
                PostgresConfig(
                    host=os.getenv("SUPABASE_DB_HOST", "localhost"),
                    port=int(os.getenv("SUPABASE_DB_PORT", "54322")),
                    database=os.getenv("SUPABASE_DB_NAME", "postgres"),
                    user=os.getenv("SUPABASE_DB_USER", "postgres"),
                    password=os.getenv("SUPABASE_DB_PASSWORD", "postgres"),
                )
            )
        elif backend == "neo4j":
            try:
                from ..adapters.neo4j_graph import Neo4jKnowledgeGraph
            except ImportError:
                logger.error("GRAPH_BACKEND=neo4j but neo4j adapter not installed — falling back to memory")
                _shared_graph = InMemoryKnowledgeGraph()
                _backend_type = "memory"
                _shared_service = GraphService(_shared_graph)
                return _shared_graph
            
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "password")
            database = os.getenv("NEO4J_DATABASE", "neo4j")
            
            logger.info(f"Creating Neo4j graph adapter ({uri})")
            _shared_graph = Neo4jKnowledgeGraph(
                uri=uri, user=user, password=password, database=database
            )
        else:
            logger.info("Creating InMemoryKnowledgeGraph backend")
            _shared_graph = InMemoryKnowledgeGraph()
            
        # Ensure service is also initialized
        _backend_type = backend
        _shared_service = GraphService(_shared_graph)
        
    return _shared_graph


async def check_graph_connection() -> bool:
    """
    Verify that the graph backend is reachable and responsive.
    Raises RuntimeError if connection is broken.
    """
    if _shared_graph is None:
        raise RuntimeError("Graph not initialized")

    if _backend_type == "neo4j":
        try:
             await _shared_graph.get_statistics()
             return True
        except Exception as e:
             raise RuntimeError(f"Neo4j liveness check failed: {e}")
    elif _backend_type == "postgres":
        try:
             healthy = await _shared_graph.health_check()
             if not healthy:
                 raise RuntimeError("PostgreSQL graph health check returned False")
             return True
        except RuntimeError:
             raise
        except Exception as e:
             raise RuntimeError(f"PostgreSQL graph liveness check failed: {e}")
    else:
        # Memory graph is always 'connected' if the object exists
        return True


async def initialize_graph(
    snapshot_path: str = _DEFAULT_SNAPSHOT_PATH,
) -> GraphService:
    """
    Initialize the graph backend and return the shared service.

    - Memory backend: loads JSON snapshot from disk.
    - Neo4j backend:  connects to Neo4j, initializes schema.

    Should be called once at application startup (e.g., in lifespan hook).
    """
    global _shared_graph, _shared_service, _snapshot_path, _auto_flush_task, _backend_type

    _snapshot_path = snapshot_path
    
    # Determine backend
    backend = os.getenv("GRAPH_BACKEND", "postgres").lower()
    _backend_type = backend
    
    if backend == "neo4j":
        # ── Neo4j lifecycle ──
        try:
            from ..adapters.neo4j_graph import Neo4jKnowledgeGraph
        except ImportError:
            logger.error("GRAPH_BACKEND=neo4j but neo4j adapter not installed — falling back to postgres")
            backend = "postgres"
            _backend_type = "postgres"
        
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        database = os.getenv("NEO4J_DATABASE", "neo4j")
        
        neo4j_graph = Neo4jKnowledgeGraph(
            uri=uri, user=user, password=password, database=database
        )
        
        # Retry loop for connection
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await neo4j_graph.connect()
                break
            except Exception as e:
                logger.warning(f"Neo4j connection attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1.0)
        
        _shared_graph = neo4j_graph
        _shared_service = GraphService(_shared_graph)
        
        # Immediate integrity check
        try:
            await check_graph_connection()
            stats = await neo4j_graph.get_statistics()
            logger.info(
                f"Neo4j graph ready: {stats['total_nodes']} nodes, "
                f"{stats['total_edges']} edges (db={database})"
            )
        except Exception as e:
            logger.critical(f"Graph integrity check failed: {e}")
            await neo4j_graph.disconnect()
            raise RuntimeError(f"Could not verify graph connection: {e}")

    elif backend == "postgres":
        # ── PostgreSQL lifecycle ──
        pg_graph = PostgresKnowledgeGraph(
            PostgresConfig(
                host=os.getenv("SUPABASE_DB_HOST", "localhost"),
                port=int(os.getenv("SUPABASE_DB_PORT", "54322")),
                database=os.getenv("SUPABASE_DB_NAME", "postgres"),
                user=os.getenv("SUPABASE_DB_USER", "postgres"),
                password=os.getenv("SUPABASE_DB_PASSWORD", "postgres"),
            )
        )
        
        # Retry loop for connection
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await pg_graph.connect()
                break
            except Exception as e:
                logger.warning(f"PostgreSQL graph connection attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1.0)
        
        _shared_graph = pg_graph
        _shared_service = GraphService(_shared_graph)
        
        # Integrity check
        try:
            await check_graph_connection()
            stats = await pg_graph.get_statistics()
            logger.info(
                f"PostgreSQL graph ready: {stats['total_nodes']} nodes, "
                f"{stats['total_edges']} edges"
            )
        except Exception as e:
            logger.critical(f"PostgreSQL graph integrity check failed: {e}")
            await pg_graph.disconnect()
            raise RuntimeError(f"Could not verify PostgreSQL graph connection: {e}")
            
    else:
        # ── Memory backend lifecycle ──
        service = get_shared_graph_service()
        
        # Load snapshot if available
        snapshot = _load_snapshot(snapshot_path)
        if snapshot:
            await _shared_graph.import_snapshot(snapshot)
            node_count = len(_shared_graph._nodes)
            edge_count = len(_shared_graph._edges)
            logger.info(
                f"Graph rehydrated from {snapshot_path}: "
                f"{node_count} nodes, {edge_count} edges"
            )
        else:
            logger.info("No graph snapshot found, starting with empty graph")
        
        # Register crash safety (memory only)
        _register_shutdown_handlers()
        
        # Start auto-flush background task (memory only)
        try:
            loop = asyncio.get_running_loop()
            _auto_flush_task = loop.create_task(
                _auto_flush_loop(), name="graph-auto-flush"
            )
        except RuntimeError:
            pass  # No event loop — skip auto-flush (tests)

    return _shared_service


async def persist_graph(
    snapshot_path: Optional[str] = None,
) -> None:
    """
    Save current graph state to disk.

    Uses atomic write (temp-file + os.replace) for crash safety.
    Called by auto-flush background task and shutdown handlers.
    
    No-op for Neo4j backend (Neo4j handles its own durability).
    """
    global _dirty

    if _shared_graph is None:
        return
    
    if _backend_type == "neo4j":
        return  # Neo4j handles its own persistence
    if _backend_type == "postgres":
        return  # PostgreSQL is durable by default

    path = snapshot_path or _snapshot_path or _DEFAULT_SNAPSHOT_PATH
    snapshot = await _shared_graph.export_snapshot()
    _save_snapshot_sync(snapshot, path)
    _dirty = False


async def shutdown_graph() -> None:
    """
    Gracefully shut down the graph backend.
    
    - Memory: final flush to disk.
    - Neo4j:  close driver connection.
    """
    global _auto_flush_task
    
    if _auto_flush_task and not _auto_flush_task.done():
        _auto_flush_task.cancel()
        try:
            await _auto_flush_task
        except asyncio.CancelledError:
            pass
    
    if _backend_type == "neo4j" and _shared_graph is not None:
        await _shared_graph.disconnect()
        logger.info("Neo4j graph disconnected")
    elif _backend_type == "postgres" and _shared_graph is not None:
        await _shared_graph.disconnect()
        logger.info("PostgreSQL graph disconnected")
    else:
        await persist_graph()
        logger.info("In-memory graph persisted on shutdown")


def mark_graph_dirty() -> None:
    """
    Mark the graph as having unsaved changes.

    Called by services after mutating the graph.
    The auto-flush task will persist the graph within 30 seconds.
    No-op for Neo4j backend.
    """
    global _dirty
    if _backend_type != "neo4j":
        _dirty = True
