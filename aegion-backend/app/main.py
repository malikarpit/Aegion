"""
Aegion Backend - FastAPI Application Entry Point.

Contract-first API: the OpenAPI spec at /openapi.json is the single
source of truth. Generated TS clients consume this spec directly.
"""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from .core.middleware import SessionGuardMiddleware
from .core.config import settings
from .core.cloud_logging import logger
from .api.v1 import router as api_v1_router
from .api.v1 import features
from .core.route_validator import validate_route_uniqueness

# Middleware imports
from .middleware.forensic_readiness import CorrelationIDMiddleware
from .middleware.security_headers import SecurityHeadersMiddleware, RequestSizeLimitMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.workspace_isolation import WorkspaceIsolationMiddleware
from .middleware.cors_config import setup_cors
from app.core.config import settings
from app.adapters.persistence.event_store import FileEventStore, InMemoryEventStore
from app.services.chronos.timeline import get_timeline_service
from .core.instrumentation import setup_instrumentation

# Global Event Store
event_store = None


# ── Lifespan (startup/shutdown) ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: runs on startup and shutdown."""
    # ── Startup ──
    global event_store
    session_repo = None
    
    if settings.storage_mode == "LOCAL":
        # Ensure .aegion directory exists
        os.makedirs(".aegion", exist_ok=True)
        event_store = FileEventStore(".aegion/events.jsonl")
        
        # Initialize Council Repository
        from app.adapters.persistence.council_repository import FileCouncilRepository
        council_repo = FileCouncilRepository(".aegion/council_sessions")
        
        # Initialize Session Repository
        from app.adapters.persistence.session_repository import FileSessionRepository
        session_repo = FileSessionRepository(".aegion/sessions")
        
        print(f"📦 Initialized File persistence for {settings.storage_mode} mode")
    else:
        # TEAM mode: use PostgreSQL for persistent, shared storage
        from app.adapters.postgres import create_postgres_repository
        try:
            postgres_repo = create_postgres_repository()
            await postgres_repo.connect() # Ensure connection
            
            session_repo = postgres_repo
            event_store = InMemoryEventStore()  # Events still in-memory (migrate to PG later)
            council_repo = None  # CouncilRepo uses postgres_repo for persistence (TODO: implement PG adapter)
            print(f"🐘 Initialized PostgresSessionRepo for {settings.storage_mode} mode")
        except Exception as e:
            logger.critical(f"🔥 TEAM mode requires PostgreSQL but connection failed: {e}")
            raise RuntimeError(
                f"TEAM mode requires a running PostgreSQL instance. "
                f"Connection failed: {e}. "
                f"Either start PostgreSQL or switch to STORAGE_MODE=LOCAL."
            ) from e

    app.state.event_store = event_store
    app.state.session_repo = session_repo
    
    # Initialize CouncilService
    from app.services.council.council_service import CouncilService
    # We can inject LLM port if needed, or let it fallback/configure itself
    # Check if we have an LLM adapter available globally or if service handles it.
    # Service init: def __init__(self, llm_port=None, repository=None)
    # We'll inject repo. LLM port is optional or can be added later if we have a global one.
    # For now, we assume LLM gateway handles its own config or we pass None (degraded/mock)
    # The LangGraph orchestrator uses its own LLM logic.
    # Ideally we pass the same LLM adapter.
    # Simple init for now
    app.state.council_service = CouncilService(repository=council_repo)

    # Initialize ACK (Aegion Council Kernel) Engine
    try:
        from app.services.council_kernel.engine import CouncilEngine
        council_engine = CouncilEngine()

        # Collect API keys from environment variables
        api_keys = {}
        env_key_map = {
            "openai_key": "OPENAI_API_KEY",
            "anthropic_key": "ANTHROPIC_API_KEY",
            "deepseek_key": "DEEPSEEK_API_KEY",
            "google_key": "GOOGLE_API_KEY",
            "xai_key": "XAI_API_KEY",
            "mistral_key": "MISTRAL_API_KEY",
            "cohere_key": "COHERE_API_KEY",
            "ollama_url": "OLLAMA_URL",
        }
        for key_name, env_var in env_key_map.items():
            val = os.environ.get(env_var)
            if val:
                api_keys[key_name] = val

        # Also try Vault for any keys stored there
        try:
            from app.services.vault import get_vault
            vault = get_vault()
            for key_name, env_var in env_key_map.items():
                if key_name not in api_keys:
                    vault_val = vault.get_secret(env_var, actor_id="council_engine")
                    if vault_val:
                        api_keys[key_name] = vault_val
        except Exception:
            pass  # Vault may not be initialized yet

        if api_keys:
            await council_engine.configure(api_keys)
            logger.info(f"ACK Council Engine configured with {len(council_engine.model_router.providers)} providers")
        else:
            logger.warning("ACK Council Engine initialized with NO providers (no API keys found)")

        app.state.council_engine = council_engine

        # Wire engine into v1 CouncilService for bridged LLM calls
        app.state.council_service.council_engine = council_engine

    except Exception as e:
        logger.warning(f"ACK Council Engine initialization failed (non-fatal): {e}")
        app.state.council_engine = None

    # Initialize & Hydrate Timeline Service
    timeline_service = get_timeline_service(event_store)
    await timeline_service.hydrate()

    # Initialize Governance Conflict Service
    from app.services.governance_conflict import conflict_service
    conflict_service._event_store = event_store
    try:
        await conflict_service.hydrate()  # Restore all active conflicts
    except Exception as e:
        logger.warning(f"Failed to hydrate conflict service: {e}")

    from .services.graph_provider import initialize_graph, shutdown_graph
    
    # Initialize Vault (loads secrets from Supabase vault_secrets table)
    try:
        from .services.vault import get_vault
        vault = get_vault()
        await vault.initialize()
        logger.info("Aegion startup: vault initialized")
    except Exception as e:
        logger.warning(f"Vault initialization failed (non-fatal, using env fallback): {e}")
    
    try:
        logger.info("Aegion startup: initializing graph...")
        await initialize_graph()
    except Exception as e:
        logger.critical(f"🔥🔥🔥 Deployment Failed: Graph backend unreachable. {e}")
        # We must re-raise to abort startup
        raise RuntimeError("Graph backend initialization failed") from e
    # ── Route Uniqueness Validation ──
    validate_route_uniqueness(app)
    logger.info("Aegion startup: all routes validated, graph ready")
    yield
    # ── Shutdown ──
    logger.info("Aegion shutdown: closing graph backend...")
    await shutdown_graph()
    logger.info("Aegion shutdown: graph backend closed")
    
    if hasattr(app.state, "session_repo") and hasattr(app.state.session_repo, "disconnect"):
        await app.state.session_repo.disconnect()
        
    print("🛑 Shutting down Event Store")


# ── OpenAPI tag metadata (drives generated docs & client grouping) ──
API_TAGS = [
    {"name": "sessions", "description": "Session lifecycle management"},
    {"name": "proposals", "description": "Governance proposal CRUD & approval"},
    {"name": "decisions", "description": "Immutable decision records & supersession"},
    {"name": "council", "description": "AI council invocation"},
    {"name": "workspaces", "description": "Workspace & team management"},
    {"name": "sentinel", "description": "Drift detection & risk alerts"},
    {"name": "noesis", "description": "Knowledge graph & topology"},
    {"name": "chronos", "description": "Artifact timeline & lineage"},
    {"name": "architecture", "description": "ADR graph & timeline"},
    {"name": "ghost-text", "description": "Inline completion suggestions"},
    {"name": "drafts", "description": "Draft persistence & recovery"},
    {"name": "evidence", "description": "Evidence & dependency graph"},
    {"name": "health", "description": "Health & readiness probes"},
    {"name": "audit", "description": "Tamper-resistant audit log"},
    {"name": "praxis", "description": "Execution descriptors & sandbox"},
    {"name": "pipelines", "description": "Nexus decision pipelines"},
    {"name": "rejections", "description": "Rejection artifacts"},
    {"name": "recovery", "description": "Session recovery"},
    {"name": "stream", "description": "Server-sent events"},
    {"name": "websocket", "description": "WebSocket channels"},
]

app = FastAPI(
    title="Aegion API",
    description="The governed AI development platform backend.",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=API_TAGS,
    contact={"name": "Aegion Team", "email": "team@aegion.io"},
    license_info={"name": "Proprietary"},
    servers=[
        {"url": "http://localhost:8000", "description": "Local dev"},
        {"url": "https://api.aegion.io", "description": "Production"},
    ],
)

logger.info(f"Starting Aegion Backend v0.1.0 in {settings.environment} mode")


# ── Middleware Chain ─────────────────────────────────────────────────────
#
# FastAPI/Starlette processes middleware in REVERSE add order:
#   last added = first to execute on request, last to execute on response.
#
# Desired request flow (outermost → innermost):
#   1. CorrelationID   — assigns X-Correlation-ID before anything else
#   2. SecurityHeaders — HSTS, CSP, X-Frame-Options on every response
#   3. RequestSizeLimit — reject oversized payloads early
#   4. RateLimit       — block abusive clients before auth check
#   5. SessionGuard    — enforce X-Aegion-Session header
#   6. WorkspaceIsolation — scope every request to a workspace
#
# So we add them in REVERSE order (innermost first → outermost last):

app.add_middleware(WorkspaceIsolationMiddleware)
app.add_middleware(SessionGuardMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CorrelationIDMiddleware)

# CORS is added via helper (uses FastAPI's CORSMiddleware internally)
setup_cors(app)

# Initialize OpenTelemetry Instrumentation
setup_instrumentation(app)

# Note: WebSocketThrottleMiddleware and ToolSandboxMiddleware are applied
# at the route/dependency level, not as global middleware. They operate on
# specific connection types and require request-context information that
# is only available after session resolution.
#
# SessionSecurityMiddleware provides utility functions (fingerprinting,
# concurrent session checks) consumed by route handlers as needed.
#
# ObservabilityMiddleware provides MetricsCollector/TracingCollector singletons
# accessed by services — not an HTTP middleware class.


# ── API v1 Routes ────────────────────────────────────────────────────────
app.include_router(api_v1_router, prefix=settings.api_prefix)
app.include_router(features.router, prefix=f"{settings.api_prefix}/system")


# ── Stable OpenAPI schema (frozen contract) ──
def frozen_openapi_schema():
    """Return cached OpenAPI schema — prevents regeneration on every request."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=API_TAGS,
        servers=app.servers,
        contact=app.contact,
        license_info=app.license_info,
    )
    app.openapi_schema = schema
    return schema


app.openapi = frozen_openapi_schema  # type: ignore[assignment]


# Root endpoint (no /health duplicate — health is in api/v1/health.py)
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Aegion Backend",
        "version": "0.1.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "status": "operational"
    }


# Prometheus Metrics Endpoint
@app.get("/metrics", tags=["observability"])
async def metrics():
    """Expose Prometheus metrics for scraping."""
    from .services.archon.metrics import get_metrics_service, PROMETHEUS_AVAILABLE, CONTENT_TYPE_LATEST
    from fastapi.responses import Response

    service = get_metrics_service()
    data = service.get_metrics_data()
    
    if PROMETHEUS_AVAILABLE:
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    else:
        return Response(content=data, media_type="text/plain")
