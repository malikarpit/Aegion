# Aegion Runtime Flow

> **Last Updated**: 2026-02-14
> Reflects the current production architecture after Enterprise Hardening Phases 1–5.

---

## 1. System Overview

Aegion is a **Governed Cognitive Infrastructure** platform. It combines AI-assisted reasoning with cryptographic governance to make, track, and audit decisions over a shared knowledge graph.

```
┌──────────────────────────────────────────────────────────────┐
│                        NGINX (TLS 1.3)                       │
│  Security headers · HSTS · Rate limit · Proxy to :8000       │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│               FastAPI Application (:8000)                     │
│                                                               │
│  ┌─ Global Middleware Chain ────────────────────────────────┐  │
│  │ CorrelationID → SecurityHeaders → RequestSizeLimit       │  │
│  │ → RateLimit → SessionGuard → WorkspaceIsolation          │  │
│  │ + CORS (via CORSMiddleware)                               │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌─ API v1 (44 route modules) ────────────────────────────┐  │
│  │ sessions · proposals · council · decisions · evidence    │  │
│  │ noesis · chronos · sentinel · praxis · audit · agents    │  │
│  │ ghost-text · websocket · stream · tasks · skills · ...   │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌─ Service Layer ─────────────────────────────────────────┐  │
│  │ Archon · Praxis · Noesis · Chronos · Council · Sentinel │  │
│  │ Collaboration · AI Safety · Audit Store · Leader Election│  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌─ Adapter Layer (DI Container) ──────────────────────────┐  │
│  │ Database: Firestore | Postgres                           │  │
│  │ Auth:     Firebase  | Keycloak                           │  │
│  │ AI:       LangGraph | Custom                             │  │
│  │ Events:   InProcess | PubSub | Kafka                     │  │
│  │ Storage:  GCS       | Local                              │  │
│  │ Graph:    Memory    | Neo4j (feature flag)               │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

## 2. Request Lifecycle

Every inbound request passes through the following stages:

### Stage 1: Edge (NGINX)

| Step | What Happens |
|------|-------------|
| TLS Termination | TLS 1.3 only. Older protocols rejected. |
| Security Headers | `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security` injected. |
| Rate Limit (L7) | Connection-level rate limit (100 req/s per IP). |
| Proxy Pass | Request forwarded to `localhost:8000` (FastAPI). |

### Stage 2: Middleware Chain (FastAPI)

Middleware executes **top-down on request**, **bottom-up on response**.  
FastAPI/Starlette processes middleware in reverse `add_middleware` order (last added = outermost).

#### Global Middleware (wired in `main.py`)

| Order | Middleware | Purpose | File |
|-------|-----------|---------|------|
| 1 | `CorrelationIDMiddleware` | Generates `X-Correlation-ID` (UUID4), attaches to request context. Timestamps in UTC ISO-8601. | `middleware/forensic_readiness.py` |
| 2 | `SecurityHeadersMiddleware` | Adds CSP, HSTS, X-Content-Type, referrer policy to every response. | `middleware/security_headers.py` |
| 3 | `RequestSizeLimitMiddleware` | Rejects payloads exceeding configurable size limit (default 10 MB). | `middleware/security_headers.py` |
| 4 | `RateLimitMiddleware` | Per-client sliding-window rate limit. In-memory or Redis backend. | `middleware/rate_limit.py` |
| 5 | `SessionGuardMiddleware` | Enforces `X-Aegion-Session` header on non-exempt routes. Rejects 401 if missing. | `core/middleware.py` |
| 6 | `WorkspaceIsolationMiddleware` | Scopes every request to a single workspace. Cross-workspace access blocked. | `middleware/workspace_isolation.py` |
| — | `CORSMiddleware` | Origin allow-list via `setup_cors()`. Credentials, headers, methods configured. | `middleware/cors_config.py` |

#### Route-Level Components (not global middleware)

| Component | How It's Used | File |
|-----------|--------------|------|
| `MetricsCollector` / `TracingCollector` | Singletons accessed by services for request timing, counters, histograms. | `middleware/observability.py` |
| Session security utilities | Fingerprinting, concurrent session checks — called by route handlers as needed. | `middleware/session_security.py` |
| `WebSocketThrottleMiddleware` | Applied per-connection on WS/SSE routes (requires session context). | `middleware/websocket_throttle.py` |
| `ToolSandboxMiddleware` | Applied at the tool-execution route level (requires authority context). | `middleware/tool_sandbox.py` |
| API key validation | Dependency injection via `get_current_user` — not a middleware class. | `core/security.py` |
| Input validation | Handled by Pydantic models and route-level validators. | Route modules |

### Stage 3: Route Handler

The request reaches one of the 44 API v1 route modules. Each module:
1. Extracts path/query/body parameters.
2. Calls the appropriate **Service** (business logic).
3. The service interacts with **Adapters** (data access) via the DI Container.
4. Returns a Pydantic response model.

### Stage 4: Response

The response traverses the middleware chain in reverse order. Security headers, correlation IDs, and audit entries are attached before the response leaves the server.

---

## 3. Service Architecture

### 3.1 Archon — Governance Engine

The governance brain. Controls *who can do what, and under what conditions*.

| Module | Purpose |
|--------|---------|
| `gates.py` | Policy enforcement: quorum thresholds, T3 admin gates, proposal rules. |
| `decision_integrity.py` | HMAC-SHA256 signing of governance decisions. Tamper detection. |
| `freeze_escalation.py` | NONE → PARTIAL → FULL → EMERGENCY freeze tiers. Multi-party unlock. |
| `secret_encryption.py` | AES-256-GCM secrets vault. HKDF key derivation. Version rotation. |
| `key_rotation.py` | Signing key rotation with historical verification. |
| `audit_chain.py` | Hash-chained audit entries. SHA-256 chain integrity. |
| `audit_store.py` | Append-only immutable audit log. SIEM export (CEF/JSON). Alert fatigue controls. |
| `audit_acl.py` | Role-based access to audit records. |
| `policy_fixtures.py` | Default governance policies and seed data. |

### 3.2 Praxis — Execution Engine

Handles code execution, sandboxing, and production staleness.

| Module | Purpose |
|--------|---------|
| `sandbox.py` | Hardened subprocess execution. Seccomp profile. Cgroup resource limits. Forbidden syscall blocking. |
| `execution_sandbox.py` | Higher-level execution orchestration. |
| `execution_profile.py` | Profiles for different execution environments (dev/staging/prod). |
| `dependency_graph.py` | Tracks dependency relationships between executed artifacts. |
| `snapshot_manager.py` | Graph snapshots for consistent read-during-write. |
| `staleness_detector.py` | Detects stale artifacts via file watchers, git hooks, CI/CD. |
| `production_staleness.py` | Production-grade staleness with anomaly detection and forecasting. |
| `seccomp_profile.json` | Linux seccomp syscall filter (allowlist). |
| `sandbox_network_policy.json` | Network rules for sandboxed execution. |

### 3.3 Noesis — Knowledge Graph

The shared knowledge graph powering all reasoning.

| Module | Purpose |
|--------|---------|
| `graph_service.py` | High-level graph operations: add/query/traverse nodes and edges. |
| `graph_algorithms.py` | PageRank, community detection, centrality measures. |
| `graph_provider.py` | Singleton graph instance. Feature flag (`GRAPH_BACKEND=memory|neo4j`). Auto-flush persistence (30s + shutdown). Crash-safe atomic writes. |
| `graph_lock.py` | `AsyncRWLock` with deadlock detection (5s timeout). Writer-preference. Snapshot reads. |

### 3.4 Other Core Services

| Service | Module | Purpose |
|---------|--------|---------|
| **Chronos** | `services/chronos/` | Immutable artifact timeline. Lineage tracking. History queries. |
| **Sentinel** | `services/sentinel/` | Drift detection. Risk alerts. Anomaly scoring. |
| **Council** | `services/council/` | Multi-agent AI deliberation. Diff review. Reasoning chains. |
| **Collaboration** | `services/collaboration/` | Presence, war rooms, multi-user editing. |
| **AI Safety** | `ai_safety_hardening.py` | Prompt injection detection (6 patterns). PII redaction. Cost circuit breaker ($1/req, $50/day). Output leakage defense. |
| **Audit Store** | `audit_store.py` | Hash-chained, append-only audit log. SIEM export. Alert deduplication. |
| **Leader Election** | `leader_election.py` | Redis-based `SET NX EX` leader lock. Heartbeat. Governance guard (only leader processes proposals). |
| **Data Protection** | `data_protection.py` | Core dump prevention. Log secret redaction. Stack trace sanitization. |
| **Chaos Testing** | `chaos_testing.py` | Framework for injecting failures (snapshot corruption, lock contention, rate limiter stress). |
| **Zero Trust** | `zero_trust_network.py` | SPIFFE identity, mTLS config generation, network allow-list, egress deny-by-default. |
| **Vault** | `vault.py` | Secret storage and retrieval. |
| **MCP Server** | `mcp_server.py` | Model Context Protocol server for IDE integration. |

---

## 4. Dependency Injection (Container)

The `Container` class (`app/container.py`) lazily loads adapters based on environment variables:

| Slot | Env Var | Options | Default | Current Status |
|------|---------|---------|---------|----------------|
| Database | `DATABASE_ADAPTER` | `firestore`, `postgres` | `firestore` | Firestore active. Postgres adapter exists but migration not yet run. |
| Auth | `AUTH_ADAPTER` | `firebase`, `keycloak` | `firebase` | Firebase active. Keycloak adapter stub present. |
| AI | `AI_ADAPTER` | `langgraph`, `custom` | `langgraph` | LangGraph active. Custom adapter stub present. |
| Events | `EVENT_ADAPTER` | `inprocess`, `pubsub`, `kafka` | `inprocess` | InProcess active. PubSub and Kafka adapters present. |
| Storage | `STORAGE_ADAPTER` | `gcs`, `local` | `gcs` | GCS active. Local adapter for dev. |
| Graph | `GRAPH_BACKEND` | `memory`, `neo4j` | `memory` | InMemory active. Neo4j falls back to memory with warning (adapter code pending). |

---

## 5. Security Layers

### 5.1 Request-Level Security

```
Request → NGINX TLS 1.3 → CorrelationID → SecurityHeaders
        → RequestSizeLimit → RateLimit → SessionGuard
        → WorkspaceIsolation → Route Handler
```

### 5.2 Governance Security

```
Proposal → Quorum Check → T3 Admin Gate → HMAC Signing
         → Freeze Level Check → Audit Chain Append
```

### 5.3 AI Safety Pipeline

```
User Prompt → Injection Detection (score > 0.7 = BLOCK)
            → PII Redaction (email, phone, SSN, API keys stripped)
            → Cost Circuit Breaker ($1/req, $50/day/workspace)
            → LLM Inference
            → Output Leakage Check (internal IDs blocked)
            → Response to User
```

### 5.4 Data-at-Rest Security

| Layer | Protection |
|-------|-----------|
| Secrets | AES-256-GCM (HKDF derived keys). Versioned rotation. |
| Graph Snapshots | Atomic writes (`tmp` + `os.replace`). Auto-flush every 30s. Signal handler crash safety. |
| Audit Log | Hash-chained (SHA-256). Tamper-evident. 7-year retention (governance). |
| Core Dumps | Prevented via `resource.setrlimit(RLIMIT_CORE, 0)`. |
| Logs | PII auto-redacted (bearer tokens, API keys, connection strings, AWS keys). |

---

## 6. Persistence & Data Flow

### 6.1 Write Path

```
API Handler → Service Logic → Mark Graph Dirty
                             → Adapter Write (Firestore/Postgres)
                             → Event Bus Publish (InProcess/PubSub/Kafka)
                             → Audit Store Append (hash-chained)

Background: Auto-flush loop (every 30s) →  graph_snapshot.json (atomic write)
```

### 6.2 Read Path

```
API Handler → Service Logic → Graph Lock (AsyncRWLock read lock)
                             → GraphService query
                             → Adapter Read (Firestore/Postgres)
                             → Return Pydantic model
```

### 6.3 Startup Sequence

```
1. FastAPI app created with lifespan hook (main.py)
2. Middleware chain attached (6 global + CORS)
3. API v1 router mounted at /api/v1
4. Lifespan startup:
   a. initialize_graph() called
   b. Load graph_snapshot.json if exists (rehydrate)
   c. Register shutdown handlers (atexit + SIGTERM/SIGINT)
   d. Start auto-flush background task (30s interval)
5. [On first request] Container lazy-loads adapters
6. System ready
```

On shutdown, `persist_graph()` is called by the lifespan hook.

---

## 7. Deployment Architecture

### 7.1 Current (Single Instance)

```
┌─────────────────────────────────┐
│  Docker Container               │
│  ┌───────────┐  ┌────────────┐  │
│  │  NGINX    │→ │  FastAPI   │  │
│  │  :443     │  │  :8000     │  │
│  └───────────┘  └────────────┘  │
│                  ↓               │
│  ┌──────────────────────────┐   │
│  │  InMemory Graph + JSON   │   │
│  │  data/graph_snapshot.json│   │
│  └──────────────────────────┘   │
└─────────────────────────────────┘
```

### 7.2 Target (Horizontal Scale — Terraform)

```
                    ┌─────────────────┐
                    │  ALB (Session   │
                    │  Stickiness)    │
                    └────────┬────────┘
               ┌─────────────┼─────────────┐
               ▼             ▼             ▼
         ┌──────────┐  ┌──────────┐  ┌──────────┐
         │ Instance │  │ Instance │  │ Instance │
         │ (ASG)    │  │ (ASG)    │  │ (ASG)    │
         └────┬─────┘  └────┬─────┘  └────┬─────┘
              │              │              │
    ┌─────────▼──────────────▼──────────────▼─────────┐
    │             Redis Cluster (ElastiCache)           │
    │    Leader Election · Session State · Graph Cache  │
    └──────────────────────┬───────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Neo4j      │
                    │  Cluster    │
                    │  (Future)   │
                    └─────────────┘
```

- **Auto-scaling**: CPU-based (target 60%), 2–10 instances.
- **Session affinity**: ALB cookie stickiness (86400s) for WebSocket connections.
- **Redis**: Multi-AZ ElastiCache cluster (leader election, shared state).
- **Neo4j**: Causal cluster with read replicas (planned, currently InMemory).

---

## 8. Key Configuration (Environment Variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENVIRONMENT` | `development` | Controls debug mode, log level, CORS origins. |
| `API_PREFIX` | `/api/v1` | API route prefix. |
| `DATABASE_ADAPTER` | `firestore` | Database backend selection. |
| `AUTH_ADAPTER` | `firebase` | Authentication provider. |
| `AI_ADAPTER` | `langgraph` | AI orchestration backend. |
| `EVENT_ADAPTER` | `inprocess` | Event bus implementation. |
| `STORAGE_ADAPTER` | `gcs` | File storage backend. |
| `GRAPH_BACKEND` | `memory` | Knowledge graph backend (`memory` or `neo4j`). |
| `REDIS_URL` | — | Redis connection for leader election and shared state. |
| `FREEZE_LEVEL` | `NONE` | System freeze tier (`NONE`, `PARTIAL`, `FULL`, `EMERGENCY`). |

---

## 9. API Module Index

44 route modules mounted under `/api/v1`:

| Category | Modules |
|----------|---------|
| **Core Governance** | `sessions`, `proposals`, `decisions`, `governance`, `delegation` |
| **AI & Reasoning** | `council`, `council_analytics`, `reasoning`, `ghost_text`, `ai_commands`, `models` |
| **Knowledge** | `evidence`, `analytics` (sentinel + noesis), `architecture`, `memory` |
| **Execution** | `praxis`, `tasks`, `checkpoints`, `terminal`, `browser`, `skill_invoke`, `agents` |
| **Timeline** | `chronos`, `diff_review` |
| **Collaboration** | `presence`, `warroom`, `chatops` |
| **Streaming** | `websocket`, `stream` |
| **Configuration** | `workspaces`, `rules`, `skills`, `modes`, `secrets`, `mcp` |
| **Audit & Admin** | `audit`, `admin`, `health` |
| **Data** | `drafts`, `recovery`, `rejections`, `pipelines` |
