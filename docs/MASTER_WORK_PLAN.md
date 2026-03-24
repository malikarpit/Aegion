# AEGION — Master Work Plan
# Complete Implementation Guide: 0% → 100%

> **Version**: 1.1.0 | **Status**: Active | **Updated**: 2026-04-09  
> **Engineer**: Solo Developer | **Deadline**: None (quality-first)  
> **Stack**: Python FastAPI + Next.js + VS Code Extension  
> **Infra**: GCP Cloud Run + Supabase (PostgreSQL + pgvector + Realtime) + Firebase Auth + Firebase Hosting  
> **Budget**: $300 GCP credits (~12-24 months free)
>
> **📌 Architecture Decision (2026-04-09):** After evaluation, we keep Supabase for PostgreSQL + pgvector + Realtime (best-in-class DX, free tier). Auth is Firebase (already in codebase — Phase 4 is a hardening, not a replacement). GCP Cloud Run hosts the backend. Firebase Hosting serves the frontend. GCP Secret Manager holds all secrets. This hybrid is the industry-standard pattern and avoids re-writing the work plan's database code.

---

## How to Use This Document

This is a **self-contained implementation guide**. No other document is required.

- Each **Phase** is a deployable increment (1-2 weeks of work)
- Each phase has **exact file paths**, **function signatures**, and **code snippets**
- Phases are ordered by dependency — do them in sequence
- **Acceptance Criteria** define when a phase is DONE
- Reference docs: [COUNCIL_KERNEL_ARCHITECTURE.md](./COUNCIL_KERNEL_ARCHITECTURE.md), [COST_OPTIMIZATION_STRATEGY.md](./COST_OPTIMIZATION_STRATEGY.md)

### Phase Index

| # | Phase | Category | Est. Days |
|---|---|---|---|
| 1 | Project Hygiene & Git Cleanup | Foundation | 1 |
| 2 | GCP Cloud Run Deployment | Infrastructure | 2 |
| 3 | Supabase Setup & Database Migration | Database | 3 |
| 4 | Authentication Hardening (Firebase Auth) | Auth | 2 |
| 5 | Durable Store → PostgreSQL Migration | Database | 3 |
| 6 | Knowledge Graph → PostgreSQL Migration | Database | 3 |
| 7 | Session Manager Hardening | Backend Core | 2 |
| 8 | Council Service — Core Engine | Backend Core | 3 |
| 9 | Model Router & Provider Abstraction | ACK | 3 |
| 10 | LLM Cascade (FrugalGPT) | Cost | 2 |
| 11 | Semantic Cache Layer | Cost | 2 |
| 12 | Prompt Compression Integration | Cost | 1 |
| 13 | Peer Review Engine | ACK | 3 |
| 14 | Debate Engine (Anti-Sycophancy) | ACK | 3 |
| 15 | Rubric Evaluation Engine | ACK | 2 |
| 16 | Persona Engine | ACK | 2 |
| 17 | Evidence Manager | ACK | 2 |
| 18 | Council Kernel Integration | ACK | 3 |
| 19 | Archon Governance — Tier System | Governance | 3 |
| 20 | Archon — Freeze Mode & Policy Engine | Governance | 2 |
| 21 | Sentinel — Risk Scoring Engine | Governance | 3 |
| 22 | Sentinel — Drift Detection | Governance | 2 |
| 23 | Sentinel — Security Council | Governance | 2 |
| 24 | Noesis — Cognitive Analytics | Intelligence | 3 |
| 25 | Ghost Text — AI Completions | Intelligence | 3 |
| 26 | Chronos — Timeline & Event Sourcing | Memory | 3 |
| 27 | Chronos — Immutable Decision Records | Memory | 2 |
| 28 | Praxis — Sandbox Hardening | Execution | 3 |
| 29 | Memory & Rules Engine | Memory | 2 |
| 30 | Skills System | Platform | 2 |
| 31 | Task Management System | Platform | 2 |
| 32 | Checkpoints & Recovery | Platform | 2 |
| 33 | Collaboration — Real-time Presence (Supabase Realtime) | Collab | 3 |
| 34 | War Room — Incident Management | Collab | 2 |
| 35 | Diff Review System | Code Review | 2 |
| 36 | Audit Trail & Compliance | Enterprise | 2 |
| 37 | Agent Identity & Zero Trust | Security | 2 |
| 38 | Secrets Vault | Security | 1 |
| 39 | ChatOps Integration | Integration | 2 |
| 40 | MCP Server & Tools | Integration | 2 |
| 41 | Terminal & Browser Agents | Agents | 2 |
| 42 | AI Commands Engine | Agents | 2 |
| 43 | Rejection Learning System | Intelligence | 2 |
| 44 | Decision Pipelines | Intelligence | 2 |
| 45 | Reasoning Chains | Intelligence | 2 |
| 46 | Constitutional AI Layer | ACK Advanced | 2 |
| 47 | Cognitive Reflector | ACK Advanced | 2 |
| 48 | Red Team Layer | ACK Advanced | 2 |
| 49 | Temporal Council Memory | ACK Advanced | 2 |
| 50 | Cross-Council Orchestration | ACK Advanced | 2 |
| 51 | Council Analytics Engine | ACK Advanced | 2 |
| 52 | VS Code Extension — Auth & Connection (Firebase Auth) | Extension | 3 |
| 53 | VS Code Extension — TreeView Providers | Extension | 3 |
| 54 | VS Code Extension — Ghost Text Provider | Extension | 3 |
| 55 | VS Code Extension — Commands & Webviews | Extension | 3 |
| 56 | VS Code Extension — Testing | Extension | 3 |
| 57 | Frontend — Project Setup & Design System | Frontend | 3 |
| 58 | Frontend — Authentication Pages | Frontend | 2 |
| 59 | Frontend — Dashboard Overview | Frontend | 3 |
| 60 | Frontend — Timeline Page | Frontend | 2 |
| 61 | Frontend — Council Console | Frontend | 3 |
| 62 | Frontend — Proposals & Decisions | Frontend | 2 |
| 63 | Frontend — Settings & API Keys | Frontend | 2 |
| 64 | Frontend — Knowledge Graph Visualizer | Frontend | 3 |
| 65 | Frontend — ADR Management | Frontend | 2 |
| 66 | Frontend — Cost Dashboard | Frontend | 1 |
| 67 | Frontend — Memory & Skills Pages | Frontend | 2 |
| 68 | Frontend — Responsive & Polish | Frontend | 2 |
| 69 | Backend Unit Tests | Testing | 3 |
| 70 | Frontend Tests | Testing | 2 |
| 71 | E2E & Load Tests | Testing | 3 |
| 72 | Docker & Local Dev | DevOps | 2 |
| 73 | GCP Cloud Run Deployment (CI/CD) — ✅ DONE IN PHASE 2 | DevOps | 0 |
| 74 | Monitoring & Alerting | DevOps | 2 |
| 75 | Documentation, Marketplace & Launch | Launch | 5 |
| 76 | Prompt Gateway & Intent Clarification | Cost | 3 |
| 77 | Adaptive Council Size & Smart Routing | Cost | 2 |
| 78 | Output Token Budgeting & Dynamic Limits | Cost | 1 |
| 79 | Context Window Pruning & History Compression | Cost | 2 |
| 80 | Early Consensus Detection & Round Optimization | Cost | 1 |
| 81 | Speculative Decoding (Draft-Verify) | Cost | 2 |
| 82 | Batch Deferred Processing | Cost | 2 |
| 83 | RAG-Enhanced Council Prompts | Cost | 2 |
| 84 | Model Settings Engine (Backend) | Platform | 3 |
| 85 | Model Settings Dashboard (Frontend) | Frontend | 3 |
| 86 | Model Settings Panel (VS Code Extension) | Extension | 2 |
| **Total** | | | **~195 days** |

---

> **⚡ RECOMMENDED EXECUTION ORDER**
>
> Phases are numbered for reference, not strict sequential execution. The recommended build order is:
>
> | Order | Phases | What | Why |
> |-------|--------|------|-----|
> | 1st | **1-7** | Foundation | Git, GCP, Supabase, Auth hardening — must come first |
> | 2nd | **8-18** | Council Kernel | Core ACK engines, cache, compression |
> | 3rd | **76-83** | Cost Optimization | Plug INTO the kernel immediately — Gateway, Adaptive Council, Token Budget, Pruning, Consensus, Speculative, Batch, RAG |
> | 4th | **84** | Model Settings Backend | Powers all cost controls and presets |
> | 5th | **19-56** | Governance, Platform, Extension | Archon, Sentinel, Chronos, Memory, VS Code |
> | 6th | **85** | Model Settings Frontend | Build alongside frontend dashboard |
> | 7th | **86** | Model Settings VS Code | Build alongside extension work |
> | 8th | **57-75** | Frontend, Testing, DevOps, Launch | Dashboard, tests, Docker, CI/CD, ship |
>
> Phases 76-86 depend on the kernel (8-18) but NOT on governance or platform (19-56), so building them early maximizes cost savings from day one.

---

## PHASE 1: Project Hygiene & Git Cleanup
**Category**: Foundation | **Duration**: 1 day | **Depends on**: Nothing
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

### Objective
Commit all 22 modified + 7 untracked files. Establish proper branching and clean working directory.

### Steps

#### 1.1 Commit Current Work

```bash
cd /Users/arpit/Projects/Aegion

# Stage all changes
git add -A

# Commit with descriptive message
git commit -m "chore: commit all in-progress work before major refactor

- 22 modified files across backend, frontend, and extension
- 7 new untracked files including new services and tests
- Preparing for Supabase migration and ACK implementation"

# Push to remote
git push origin main
```

#### 1.2 Create Development Branch

```bash
# Create and switch to development branch
git checkout -b develop

# Create feature branch for Phase 2+
git checkout -b feature/infrastructure-setup
```

#### 1.3 Add .gitignore Entries

**File**: `/Users/arpit/Projects/Aegion/.gitignore`

Add:
```gitignore
# Supabase
.supabase/

# Local LLM models
models/

# Cost tracking logs
cost_logs/

# Secrets (already present but verify)
.env
.env.local
.env.*.local
secrets/
```

#### 1.4 Local Development Setup

To develop locally without relying on deployed cloud infrastructure, use the Supabase CLI to run the full database and authentication stack:

```bash
# 1. Install Supabase CLI (macOS)
brew install supabase/tap/supabase

# 2. Initialize in project root (only needed once)
cd /Users/arpit/Projects/Aegion
supabase init

# 3. Start local stack (run this in a separate terminal before development)
supabase start
```

After running `supabase start`, your local endpoint details will print to the console. Add these to your `.env` file (which is read by `pydantic-settings`):

```bash
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=<printed_by_supabase_start>
SUPABASE_SERVICE_KEY=<printed_by_supabase_start>
```

**Daily Development Workflow (3 Terminals):**
1. **Supabase Stack**: `supabase start` (inside `/Users/arpit/Projects/Aegion`)
2. **Backend**: `cd aegion-backend && uvicorn app.main:app --reload --port 8080`
3. **Frontend**: `cd aegion-frontend && npm run dev`

*Note: You do not need a local emulator for Firebase Auth. The real Firebase project free tier is sufficient for development. Keep Firebase configuration active in your `.env`.*

### Acceptance Criteria
- [ ] All files committed and pushed
- [ ] `develop` branch created
- [ ] Clean `git status` output
- [ ] `.gitignore` updated
- [ ] `supabase init` completed and local dev environment tested

---

## PHASE 2: GCP Cloud Run Deployment
**Category**: Infrastructure | **Duration**: 2 days | **Depends on**: Phase 1  
**✅ STATUS: COMPLETE** — Implemented 2026-04-09 on branch `feature/infrastructure-setup`

### Objective
Deploy AEGION backend to GCP Cloud Run. Frontend to Firebase Hosting. Full CI/CD pipeline via GitHub Actions with keyless GCP authentication.

> **📌 Implementation Note:** Phase 2 was implemented with a more production-grade approach than originally planned. The key upgrade was replacing JSON service account keys with **Workload Identity Federation (WIF)** — the GCP-recommended keyless authentication method for GitHub Actions. See the GCP Setup Walkthrough for step-by-step instructions.

### What Was Implemented

#### 2.1 GCP Project Setup

```bash
# Your project ID must be globally unique — use something like:
export PROJECT_ID="aegion-prod-YOURNAME"   # e.g. aegion-prod-arpit

gcloud auth login
gcloud projects create $PROJECT_ID --name="Aegion Production"
gcloud config set project $PROJECT_ID

# Enable all required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com \
  firebase.googleapis.com

gcloud billing projects link $PROJECT_ID --billing-account=YOUR_BILLING_ACCOUNT_ID

# Create Artifact Registry (replaces deprecated Container Registry)
gcloud artifacts repositories create aegion \
  --repository-format=docker \
  --location=us-central1
```

#### 2.2 Backend Dockerfile (multi-stage, Cloud Run ready)

**File**: `aegion-backend/Dockerfile` — Multi-stage build with non-root user.

Key decisions:
- **Shell-form CMD** so `$PORT` is expanded at runtime (Cloud Run injects `PORT=8080`)
- **Non-root `aegion` user** for security
- **`curl` in runtime stage** for HEALTHCHECK
- **`--workers 2`** for production throughput

```dockerfile
# Stage 1: Builder — installs dependencies
FROM python:3.12-slim-bookworm as builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git && rm -rf /var/lib/apt/lists/*
ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 -
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root

# Stage 2: Runtime — lean production image
FROM python:3.12-slim-bookworm as runtime
WORKDIR /app
RUN groupadd -r aegion && useradd -r -g aegion aegion
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY app/ ./app/
COPY scripts/ ./scripts/
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*
RUN chown -R aegion:aegion /app
USER aegion
# PORT is injected by Cloud Run at runtime (default 8080)
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080 ENVIRONMENT=production
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/v1/health/ready || exit 1
# Shell-form CMD so $PORT expands at runtime
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2
```

#### 2.3 Service Accounts & Workload Identity Federation

Two service accounts are created:
- **`aegion-cloudrun`** — runtime identity for Cloud Run (reads Secret Manager)
- **`aegion-deploy`** — CI/CD identity for GitHub Actions (deploys images and services)

GitHub Actions authenticates to GCP using **Workload Identity Federation** (no JSON key stored as a GitHub Secret).

```bash
# Runtime SA
gcloud iam service-accounts create aegion-cloudrun \
  --display-name="Aegion Cloud Run Runtime"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:aegion-cloudrun@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Deploy SA (used by GitHub Actions)
gcloud iam service-accounts create aegion-deploy \
  --display-name="Aegion GitHub Actions Deployer"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:aegion-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:aegion-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Workload Identity Pool + Provider (keyless GitHub → GCP auth)
gcloud iam workload-identity-pools create "github-pool" \
  --project=$PROJECT_ID --location="global"
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project=$PROJECT_ID --location="global" \
  --workload-identity-pool="github-pool" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

#### 2.4 Frontend (next.config.ts + firebase.json)

**File**: `aegion-frontend/next.config.ts`
```typescript
const nextConfig: NextConfig = {
  output: "export",          // Static export for Firebase Hosting
  images: { unoptimized: true },
  env: { NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080" },
  trailingSlash: true,       // Required for Firebase Hosting SPA routing
};
```

**File**: `aegion-frontend/firebase.json` — serves from `out/`, includes SPA rewrite and security headers.

#### 2.5 CI/CD Pipelines

Two files were created:

**`cloudbuild.yaml`** (GCP Cloud Build) — for GCP-native CI/CD triggers:
- Steps: test → build image → push to Artifact Registry → deploy to Cloud Run → build Next.js → deploy to Firebase

**`.github/workflows/deploy.yml`** (GitHub Actions) — triggered on push to `main`:
- Keyless GCP auth via Workload Identity Federation
- Reuses `backend-ci.yml` as a deployment gate (no deploy if tests fail)
- Health-check loop post-deployment (10 retries / 10s)
- Injects live Cloud Run URL into Next.js build so frontend hits production API

#### 2.6 Secret Management

All secrets stored in GCP Secret Manager (never in env vars or GitHub Secrets as plaintext):

```bash
# Audit signing key (generate once)
python3 -c "import secrets; print(secrets.token_hex(64))" | \
  gcloud secrets create audit-signing-key --data-file=- --replication-policy=automatic

# Supabase credentials (add after Phase 3)
gcloud secrets create supabase-url --data-file=- --replication-policy=automatic
gcloud secrets create supabase-service-key --data-file=- --replication-policy=automatic
```

See `.env.production.example` for the complete list of required variables.

### GitHub Secrets Required (3 total)

| Secret | Value |
|---|---|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | WIF provider resource name from Step 7d of GCP setup |
| `GCP_SERVICE_ACCOUNT` | `aegion-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com` |
| `FIREBASE_SERVICE_ACCOUNT` | Firebase Admin SDK JSON (from Firebase console) |

### Acceptance Criteria
- [x] Multi-stage Dockerfile with non-root user and dynamic `$PORT`
- [x] `next.config.ts` updated for static export + `trailingSlash`
- [x] `firebase.json` created with SPA rewrite and cache headers
- [x] `cloudbuild.yaml` committed at repo root
- [x] `.github/workflows/deploy.yml` committed with WIF authentication
- [x] `.env.production.example` documents all required env vars
- [ ] GCP project created and APIs enabled (manual — see GCP Setup Walkthrough)
- [ ] Service accounts and WIF configured (manual)
- [ ] GitHub Secrets added (manual)
- [ ] First deployment verified via health check

---

## PHASE 3: Supabase Setup & Database Migration
**Category**: Database | **Duration**: 3 days | **Depends on**: Phase 2
**✅ STATUS: COMPLETE** — Implemented on 2026-04-09 (Postgres Graph with recursive CTEs added)

### Objective
Set up Supabase project with PostgreSQL + pgvector. Create all core tables. Replace InMemoryGraph.

### Steps

#### 3.1 Create Supabase Project

1. Go to [supabase.com](https://supabase.com), create account
2. Create new project: **aegion-prod**
3. Region: **us-central-1** (matches Cloud Run)
4. Note your: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`

#### 3.2 Enable pgvector Extension

```sql
-- Run in Supabase SQL Editor
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

#### 3.3 Create Core Schema

**File**: `/Users/arpit/Projects/Aegion/aegion-backend/migrations/001_core_schema.sql`

```sql
-- ============================================
-- AEGION Core Schema
-- ============================================

-- Workspaces (multi-tenant isolation)
CREATE TABLE workspaces (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    owner_id UUID NOT NULL,
    settings JSONB DEFAULT '{}',
    security_level TEXT DEFAULT 'standard' CHECK (security_level IN ('standard', 'confidential', 'restricted')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    role TEXT DEFAULT 'developer' CHECK (role IN ('admin', 'architect', 'developer', 'viewer')),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    api_keys JSONB DEFAULT '{}', -- Encrypted LLM provider keys
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions
CREATE TABLE sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'closed', 'recovered')),
    mode TEXT DEFAULT 'standard' CHECK (mode IN ('standard', 'architecture', 'emergency', 'readonly')),
    intent TEXT,
    context JSONB DEFAULT '{}',
    artifacts JSONB DEFAULT '[]',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

-- Proposals
CREATE TABLE proposals (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    proposal_type TEXT DEFAULT 'code' CHECK (proposal_type IN ('code', 'architecture', 'policy', 'config')),
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'pending', 'approved', 'rejected', 'superseded')),
    tier INTEGER DEFAULT 0 CHECK (tier BETWEEN 0 AND 3),
    evidence JSONB DEFAULT '[]',
    votes JSONB DEFAULT '[]',
    comments JSONB DEFAULT '[]',
    council_result JSONB,
    created_by UUID REFERENCES users(id),
    reviewed_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Decisions (immutable — append only)
CREATE TABLE decisions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    proposal_id UUID REFERENCES proposals(id),
    decision_type TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('approved', 'rejected', 'deferred', 'superseded')),
    tier INTEGER NOT NULL CHECK (tier BETWEEN 0 AND 3),
    rationale TEXT,
    evidence JSONB DEFAULT '[]',
    dissenting_views JSONB DEFAULT '[]',
    supersedes_id UUID REFERENCES decisions(id),
    decided_by TEXT NOT NULL, -- 'archon_auto' | 'human:user_id' | 'council:session_id'
    decided_at TIMESTAMPTZ DEFAULT NOW(),
    -- Immutability: no UPDATE trigger, append-only
    lineage_hash TEXT -- SHA256 of parent decision chain
);

-- Architecture Decision Records (ADRs)
CREATE TABLE adrs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    decision_id UUID REFERENCES decisions(id),
    title TEXT NOT NULL,
    status TEXT DEFAULT 'proposed' CHECK (status IN ('proposed', 'accepted', 'deprecated', 'superseded')),
    context TEXT,
    decision_text TEXT,
    consequences TEXT,
    alternatives JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Knowledge Graph nodes
CREATE TABLE knowledge_nodes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    node_type TEXT NOT NULL, -- 'decision', 'adr', 'file', 'concept', 'entity'
    label TEXT NOT NULL,
    properties JSONB DEFAULT '{}',
    embedding vector(384), -- For semantic search
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Knowledge Graph edges
CREATE TABLE knowledge_edges (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    target_id UUID NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    edge_type TEXT NOT NULL, -- 'depends_on', 'supersedes', 'references', 'part_of'
    weight FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chronos timeline events (append-only)
CREATE TABLE timeline_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    actor TEXT NOT NULL,
    payload JSONB NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    sequence_number BIGSERIAL
);

-- Sentinel risk signals
CREATE TABLE risk_signals (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL, -- 'security', 'performance', 'drift', 'dependency'
    severity TEXT NOT NULL CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    source TEXT NOT NULL,
    description TEXT NOT NULL,
    evidence JSONB DEFAULT '{}',
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log (append-only, never delete)
CREATE TABLE audit_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID,
    details JSONB DEFAULT '{}',
    ip_address INET,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Memory entries
CREATE TABLE memories (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    memory_type TEXT NOT NULL, -- 'lesson', 'pattern', 'preference', 'context'
    content TEXT NOT NULL,
    embedding vector(384),
    source_session_id UUID REFERENCES sessions(id),
    confidence FLOAT DEFAULT 1.0,
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- Rules
CREATE TABLE rules (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    rule_type TEXT NOT NULL, -- 'governance', 'code_style', 'architecture', 'security'
    condition JSONB NOT NULL,
    action JSONB NOT NULL,
    priority INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Semantic cache (for cost optimization)
CREATE TABLE semantic_cache (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    query_embedding vector(384) NOT NULL,
    response_text TEXT NOT NULL,
    response_model TEXT NOT NULL,
    council_type TEXT,
    hit_count INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0,
    cost_saved FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- Cost tracking
CREATE TABLE cost_tracking (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    provider TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd FLOAT NOT NULL,
    council_type TEXT,
    cache_hit BOOLEAN DEFAULT FALSE,
    cascade_tier INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Skills
CREATE TABLE skills (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    version TEXT DEFAULT '1.0.0',
    manifest JSONB NOT NULL,
    source_url TEXT,
    installed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks
CREATE TABLE tasks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id),
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'blocked', 'cancelled')),
    priority INTEGER DEFAULT 0,
    assigned_to UUID REFERENCES users(id),
    due_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Checkpoints
CREATE TABLE checkpoints (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id),
    label TEXT NOT NULL,
    checkpoint_type TEXT DEFAULT 'manual' CHECK (checkpoint_type IN ('manual', 'auto', 'pre_decision')),
    state_snapshot JSONB NOT NULL,
    git_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_sessions_workspace ON sessions(workspace_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_proposals_workspace ON proposals(workspace_id);
CREATE INDEX idx_proposals_status ON proposals(status);
CREATE INDEX idx_decisions_workspace ON decisions(workspace_id);
CREATE INDEX idx_timeline_workspace ON timeline_events(workspace_id, timestamp DESC);
CREATE INDEX idx_timeline_entity ON timeline_events(entity_type, entity_id);
CREATE INDEX idx_knowledge_nodes_workspace ON knowledge_nodes(workspace_id);
CREATE INDEX idx_knowledge_nodes_type ON knowledge_nodes(node_type);
CREATE INDEX idx_knowledge_nodes_embedding ON knowledge_nodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_memories_workspace ON memories(workspace_id);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_semantic_cache_embedding ON semantic_cache USING ivfflat (query_embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_audit_workspace ON audit_log(workspace_id, timestamp DESC);
CREATE INDEX idx_risk_signals_workspace ON risk_signals(workspace_id, severity);
CREATE INDEX idx_cost_tracking_workspace ON cost_tracking(workspace_id, created_at DESC);

-- Row Level Security (multi-tenant isolation)
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- RLS Policies (workspace-scoped)
CREATE POLICY workspace_isolation ON sessions
    FOR ALL USING (workspace_id IN (
        SELECT workspace_id FROM users WHERE id = auth.uid()
    ));
```

#### 3.4 Create Supabase Client

**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/db/supabase_client.py`

```python
"""Supabase client singleton for AEGION backend."""

from supabase import create_client, Client
from functools import lru_cache
from app.core.config import settings


@lru_cache()
def get_supabase_client() -> Client:
    """Get singleton Supabase client."""
    return create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_SERVICE_KEY
    )


class SupabaseDB:
    """Database abstraction over Supabase PostgreSQL."""
    
    def __init__(self):
        self.client = get_supabase_client()
    
    # --- Sessions ---
    async def create_session(self, workspace_id: str, user_id: str, intent: str = None) -> dict:
        result = self.client.table("sessions").insert({
            "workspace_id": workspace_id,
            "user_id": user_id,
            "intent": intent,
            "status": "active"
        }).execute()
        return result.data[0]
    
    async def get_session(self, session_id: str) -> dict:
        result = self.client.table("sessions") \
            .select("*") \
            .eq("id", session_id) \
            .single() \
            .execute()
        return result.data
    
    async def close_session(self, session_id: str) -> dict:
        result = self.client.table("sessions") \
            .update({"status": "closed", "closed_at": "now()"}) \
            .eq("id", session_id) \
            .execute()
        return result.data[0]
    
    # --- Proposals ---
    async def create_proposal(self, data: dict) -> dict:
        result = self.client.table("proposals").insert(data).execute()
        return result.data[0]
    
    async def update_proposal_status(self, proposal_id: str, status: str, reviewer_id: str = None) -> dict:
        update = {"status": status, "updated_at": "now()"}
        if reviewer_id:
            update["reviewed_by"] = reviewer_id
        result = self.client.table("proposals") \
            .update(update) \
            .eq("id", proposal_id) \
            .execute()
        return result.data[0]
    
    # --- Decisions (append-only) ---
    async def record_decision(self, data: dict) -> dict:
        result = self.client.table("decisions").insert(data).execute()
        return result.data[0]
    
    # --- Knowledge Graph ---
    async def add_node(self, workspace_id: str, node_type: str, label: str, 
                       properties: dict = None, embedding: list = None) -> dict:
        data = {
            "workspace_id": workspace_id,
            "node_type": node_type,
            "label": label,
            "properties": properties or {}
        }
        if embedding:
            data["embedding"] = embedding
        result = self.client.table("knowledge_nodes").insert(data).execute()
        return result.data[0]
    
    async def add_edge(self, workspace_id: str, source_id: str, target_id: str, 
                       edge_type: str, weight: float = 1.0) -> dict:
        result = self.client.table("knowledge_edges").insert({
            "workspace_id": workspace_id,
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type,
            "weight": weight
        }).execute()
        return result.data[0]
    
    async def semantic_search(self, workspace_id: str, query_embedding: list, 
                               table: str = "knowledge_nodes", limit: int = 10) -> list:
        """Semantic similarity search using pgvector."""
        result = self.client.rpc("match_documents", {
            "query_embedding": query_embedding,
            "match_threshold": 0.7,
            "match_count": limit,
            "p_workspace_id": workspace_id
        }).execute()
        return result.data
    
    # --- Timeline (Chronos) ---
    async def append_event(self, workspace_id: str, event_type: str, 
                           entity_type: str, entity_id: str, actor: str, payload: dict) -> dict:
        result = self.client.table("timeline_events").insert({
            "workspace_id": workspace_id,
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "actor": actor,
            "payload": payload
        }).execute()
        return result.data[0]
    
    # --- Semantic Cache ---
    async def check_cache(self, workspace_id: str, query_embedding: list, 
                          threshold: float = 0.92) -> dict | None:
        result = self.client.rpc("find_cached_response", {
            "p_embedding": query_embedding,
            "p_workspace_id": workspace_id,
            "p_similarity_threshold": threshold
        }).execute()
        if result.data:
            # Increment hit count
            self.client.table("semantic_cache") \
                .update({"hit_count": result.data[0]["hit_count"] + 1}) \
                .eq("id", result.data[0]["id"]) \
                .execute()
            return result.data[0]
        return None
    
    async def store_cache(self, workspace_id: str, query_text: str, query_embedding: list,
                          response_text: str, model: str, ttl_hours: int = 168) -> dict:
        from datetime import datetime, timedelta
        expires = datetime.utcnow() + timedelta(hours=ttl_hours)
        result = self.client.table("semantic_cache").insert({
            "workspace_id": workspace_id,
            "query_text": query_text,
            "query_embedding": query_embedding,
            "response_text": response_text,
            "response_model": model,
            "expires_at": expires.isoformat()
        }).execute()
        return result.data[0]
    
    # --- Cost Tracking ---
    async def track_cost(self, workspace_id: str, model: str, provider: str,
                         input_tokens: int, output_tokens: int, cost_usd: float,
                         council_type: str = None, cache_hit: bool = False, 
                         cascade_tier: int = None) -> dict:
        result = self.client.table("cost_tracking").insert({
            "workspace_id": workspace_id,
            "model": model,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "council_type": council_type,
            "cache_hit": cache_hit,
            "cascade_tier": cascade_tier
        }).execute()
        return result.data[0]


# Global instance
db = SupabaseDB()
```

#### 3.5 Add Dependencies

```bash
cd /Users/arpit/Projects/Aegion/aegion-backend
poetry add supabase vecs sentence-transformers
```

#### 3.6 Update Config

**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/core/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    
    # LLM Providers (user-supplied)
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_AI_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # GCP
    GCP_PROJECT_ID: str = "aegion-prod"
    GCP_REGION: str = "us-central1"
    
    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### Acceptance Criteria
- [ ] Supabase project created with pgvector enabled
- [ ] All tables created via migration SQL
- [ ] `SupabaseDB` class working with basic CRUD
- [ ] Supabase client dependency added to pyproject.toml
- [ ] Config updated with Supabase credentials
- [ ] Semantic search RPC function working

---

## PHASE 4: Authentication Hardening (Firebase Auth)
**Category**: Auth | **Duration**: 2 days | **Depends on**: Phase 3
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

> **📌 Architecture Decision (2026-04-09):** The original plan called for replacing the existing Firebase Auth with Supabase Auth. After review, this is **reversed** — Firebase Auth is already shipping in the codebase and the frontend already has the `firebase` npm package installed. Switching auth providers mid-project adds risk with zero user-facing benefit. Instead, this phase **hardens the existing Firebase Auth implementation** by fixing the critical security bugs identified in the AUDIT_REPORT.md.

### Objective
Harden the existing Firebase Auth implementation. Fix the two critical security bugs identified in `aegion-backend/AUDIT_REPORT.md`. Add token revocation checks and remove hardcoded secrets. Do NOT replace Firebase with Supabase Auth — Firebase is already the auth provider and changing it adds risk with no benefit.

### Security Bugs to Fix

#### Bug 1 — CRITICAL: Token Revocation Not Checked

**File**: `aegion-backend/app/core/security.py`

Current `get_current_user()` verifies Firebase tokens but never checks `TokenRevocationList`, meaning revoked tokens remain valid until expiry.

```python
"""FIXED get_current_user — adds revocation check."""

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db = Depends(get_db)
) -> User:
    token = credentials.credentials
    
    try:
        # Step 1: Verify Firebase token signature
        decoded = auth.verify_id_token(token, check_revoked=True)  # ← ADD check_revoked=True
        uid = decoded["uid"]
        
        # Step 2: Check our own revocation list (for immediate invalidation)
        revocation_list = TokenRevocationList.get_instance()
        if revocation_list.is_revoked(token):          # ← ADD this block
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked"
            )
        
        # Step 3: Load user from database
        user = await get_user_by_firebase_uid(db, uid)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
        
    except auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Token revoked")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expired")
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

#### Bug 2 — HIGH: Hardcoded Default Signing Key

**File**: `aegion-backend/app/core/config.py`

Remove the hardcoded default. Force the environment to provide a real key:

```python
class Settings(BaseSettings):
    # BEFORE (insecure — has a fallback default):
    # audit_signing_key: str = "default-insecure-key-change-in-production"
    
    # AFTER (secure — no default, startup fails without a real key):
    audit_signing_key: str  # Required — set via Secret Manager in production
    
    # Also add Supabase config here (used from Phase 3 onwards):
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    
    # LLM Providers (user-supplied per workspace)
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_AI_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # GCP
    GCP_PROJECT_ID: str = "aegion-prod"
    GCP_REGION: str = "us-central1"
    
    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"

settings = Settings()
```

#### Bug 3 — HIGH: Potential SQL Injection

**File**: `aegion-backend/app/adapters/postgres/session_repository.py`

Review all raw SQL queries. Replace any f-string interpolation with parameterized queries:

```python
# BEFORE (unsafe):
await conn.execute(f"SELECT * FROM sessions WHERE id = '{session_id}'")

# AFTER (safe — parameterized):
await conn.execute("SELECT * FROM sessions WHERE id = $1", session_id)
```

#### 4.4 Frontend Auth — Use Existing Firebase

The frontend already has `firebase` installed. Create the auth context using Firebase SDK (not Supabase):

**File**: `aegion-frontend/lib/firebase.ts`
```typescript
import { initializeApp, getApps } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
};

const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
export const auth = getAuth(app);
```

**File**: `aegion-frontend/lib/auth-context.tsx`
```typescript
"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { User, onAuthStateChanged, signOut } from "firebase/auth";
import { auth } from "./firebase";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  logout: () => Promise<void>;
  getToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType>({
  user: null, loading: true,
  logout: async () => {}, getToken: async () => null
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    return onAuthStateChanged(auth, (u) => { setUser(u); setLoading(false); });
  }, []);

  const getToken = async () => user ? await user.getIdToken() : null;
  const logout = () => signOut(auth);

  return (
    <AuthContext.Provider value={{ user, loading, logout, getToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
```

### Acceptance Criteria
- [ ] `get_current_user()` runs `check_revoked=True` on Firebase token verify
- [ ] `get_current_user()` checks `TokenRevocationList` before granting access
- [ ] `audit_signing_key` has no default value — startup fails without it in env
- [ ] All raw SQL queries use parameterized form (no f-string interpolation)
- [ ] Firebase auth context working in frontend (`useAuth()` hook)
- [ ] Frontend login/signup pages use Firebase Auth
- [ ] VS Code extension auth flow uses Firebase ID tokens (see Phase 52)

---

## PHASE 5: Durable Store → PostgreSQL Migration
**Category**: Database | **Duration**: 3 days | **Depends on**: Phase 3
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

### Objective
Replace all `InMemoryGraph` and `DurableStore` usages with Supabase PostgreSQL.

### Files to Modify

#### [MODIFY] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/durable_store.py`

Replace the in-memory dict with Supabase queries:

```python
"""Durable store backed by Supabase PostgreSQL."""

from app.db.supabase_client import db

class DurableStore:
    """PostgreSQL-backed durable store replacing InMemoryGraph."""
    
    async def set(self, workspace_id: str, key: str, value: dict, 
                  namespace: str = "default") -> None:
        existing = self.client.table("kv_store") \
            .select("id").eq("workspace_id", workspace_id) \
            .eq("namespace", namespace).eq("key", key).execute()
        
        if existing.data:
            self.client.table("kv_store").update({"value": value}) \
                .eq("id", existing.data[0]["id"]).execute()
        else:
            self.client.table("kv_store").insert({
                "workspace_id": workspace_id,
                "namespace": namespace,
                "key": key,
                "value": value
            }).execute()
    
    async def get(self, workspace_id: str, key: str, 
                  namespace: str = "default") -> dict | None:
        result = self.client.table("kv_store") \
            .select("value").eq("workspace_id", workspace_id) \
            .eq("namespace", namespace).eq("key", key).single().execute()
        return result.data["value"] if result.data else None
    
    async def delete(self, workspace_id: str, key: str, 
                     namespace: str = "default") -> bool:
        self.client.table("kv_store") \
            .delete().eq("workspace_id", workspace_id) \
            .eq("namespace", namespace).eq("key", key).execute()
        return True
    
    async def list_keys(self, workspace_id: str, 
                        namespace: str = "default") -> list[str]:
        result = self.client.table("kv_store") \
            .select("key").eq("workspace_id", workspace_id) \
            .eq("namespace", namespace).execute()
        return [r["key"] for r in result.data]
```

Add migration SQL table:
```sql
-- Add to migrations/002_kv_store.sql
CREATE TABLE kv_store (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    namespace TEXT NOT NULL DEFAULT 'default',
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(workspace_id, namespace, key)
);
CREATE INDEX idx_kv_workspace_ns ON kv_store(workspace_id, namespace);
```

#### Files to Update (replace InMemory references):
- `/Users/arpit/Projects/Aegion/aegion-backend/app/services/archon_engine.py`
- `/Users/arpit/Projects/Aegion/aegion-backend/app/services/sentinel_engine.py`
- `/Users/arpit/Projects/Aegion/aegion-backend/app/services/session_manager.py`
- `/Users/arpit/Projects/Aegion/aegion-backend/app/services/proposal_engine.py`

### Acceptance Criteria
- [ ] Zero `InMemoryGraph` or `dict()` persistence remaining in backend
- [ ] All data survives server restarts
- [ ] Key-value store CRUD working with Supabase
- [ ] All existing API endpoints still functional

> **📌 Additional SQL tables** are defined in later phases and should be added to migrations when those phases are implemented:
> - `batch_queue` — Phase 82 (Batch Deferred Processing)
> - `model_settings` — Phase 84 (Model Settings Engine)
> - `cost_tracking` — Phase 11 (Semantic Cache) — also used by Phases 76, 78, 84

---

## PHASE 6: Knowledge Graph → PostgreSQL Migration
**Category**: Database | **Duration**: 3 days | **Depends on**: Phase 5
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

### Objective
Migrate the knowledge graph from in-memory to PostgreSQL with pgvector for semantic search.

### Files to Create

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/knowledge_graph.py`

```python
"""PostgreSQL-backed knowledge graph with semantic search."""

from sentence_transformers import SentenceTransformer
from app.db.supabase_client import db

class KnowledgeGraphService:
    def __init__(self):
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")  # 384-dim, 80MB, CPU
    
    async def add_concept(self, workspace_id: str, label: str, 
                          properties: dict = None) -> dict:
        embedding = self.embedder.encode(label).tolist()
        return await db.add_node(workspace_id, "concept", label, properties, embedding)
    
    async def add_decision(self, workspace_id: str, decision_id: str, 
                           title: str, context: dict) -> dict:
        embedding = self.embedder.encode(title).tolist()
        node = await db.add_node(workspace_id, "decision", title, 
                                  {"decision_id": decision_id, **context}, embedding)
        return node
    
    async def link(self, workspace_id: str, source_id: str, target_id: str,
                   relationship: str, weight: float = 1.0) -> dict:
        return await db.add_edge(workspace_id, source_id, target_id, relationship, weight)
    
    async def search_similar(self, workspace_id: str, query: str, limit: int = 10) -> list:
        embedding = self.embedder.encode(query).tolist()
        return await db.semantic_search(workspace_id, embedding, "knowledge_nodes", limit)
    
    async def get_neighbors(self, workspace_id: str, node_id: str, 
                            depth: int = 1) -> dict:
        """Get connected nodes up to N hops."""
        result = db.client.rpc("get_graph_neighbors", {
            "p_node_id": node_id,
            "p_workspace_id": workspace_id,
            "p_depth": depth
        }).execute()
        return result.data

knowledge_graph = KnowledgeGraphService()
```

Add SQL function for graph traversal:
```sql
-- migrations/003_graph_functions.sql
CREATE OR REPLACE FUNCTION get_graph_neighbors(
    p_node_id UUID, p_workspace_id UUID, p_depth INTEGER DEFAULT 1
) RETURNS JSONB AS $$
WITH RECURSIVE traversal AS (
    SELECT source_id, target_id, edge_type, 1 AS depth
    FROM knowledge_edges
    WHERE (source_id = p_node_id OR target_id = p_node_id)
      AND workspace_id = p_workspace_id
    UNION ALL
    SELECT e.source_id, e.target_id, e.edge_type, t.depth + 1
    FROM knowledge_edges e
    JOIN traversal t ON (e.source_id = t.target_id OR e.source_id = t.source_id)
    WHERE t.depth < p_depth AND e.workspace_id = p_workspace_id
)
SELECT jsonb_agg(jsonb_build_object(
    'source', source_id, 'target', target_id, 
    'type', edge_type, 'depth', depth
)) FROM traversal;
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(384), match_threshold FLOAT, 
    match_count INT, p_workspace_id UUID
) RETURNS TABLE (id UUID, label TEXT, node_type TEXT, similarity FLOAT) AS $$
    SELECT id, label, node_type, 
           1 - (embedding <=> query_embedding) AS similarity
    FROM knowledge_nodes
    WHERE workspace_id = p_workspace_id
      AND 1 - (embedding <=> query_embedding) > match_threshold
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$ LANGUAGE SQL;
```

### Acceptance Criteria
- [ ] Knowledge graph nodes stored in PostgreSQL with embeddings
- [ ] Semantic search returning relevant results (cosine similarity > 0.7)
- [ ] Graph traversal function working up to 3 hops
- [ ] Embedding generation using sentence-transformers on CPU

---

## PHASE 7: Session Manager Hardening
**Category**: Backend Core | **Duration**: 2 days | **Depends on**: Phase 5
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

### Objective
Complete the session lifecycle: create → track → checkpoint → pause → resume → close → summarize.

### Files to Modify

#### [MODIFY] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/session_manager.py`

```python
"""Complete session lifecycle manager."""

from app.db.supabase_client import db
from app.services.knowledge_graph import knowledge_graph
from datetime import datetime

class SessionManager:
    async def create_session(self, workspace_id: str, user_id: str, 
                             intent: str = None, mode: str = "standard") -> dict:
        session = await db.create_session(workspace_id, user_id, intent)
        await db.append_event(workspace_id, "session.created", "session", 
                              session["id"], user_id, {"intent": intent, "mode": mode})
        return session
    
    async def add_artifact(self, session_id: str, artifact: dict) -> dict:
        session = await db.get_session(session_id)
        artifacts = session.get("artifacts", [])
        artifacts.append({**artifact, "added_at": datetime.utcnow().isoformat()})
        return await db.client.table("sessions") \
            .update({"artifacts": artifacts}).eq("id", session_id).execute()
    
    async def create_checkpoint(self, session_id: str, label: str, 
                                 state: dict, git_ref: str = None) -> dict:
        session = await db.get_session(session_id)
        return await db.client.table("checkpoints").insert({
            "workspace_id": session["workspace_id"],
            "session_id": session_id,
            "label": label,
            "state_snapshot": state,
            "git_ref": git_ref
        }).execute()
    
    async def close_session(self, session_id: str) -> dict:
        session = await db.close_session(session_id)
        await db.append_event(session["workspace_id"], "session.closed", 
                              "session", session_id, "system", 
                              {"artifacts_count": len(session.get("artifacts", []))})
        return session
    
    async def recover_session(self, session_id: str, checkpoint_id: str = None) -> dict:
        if checkpoint_id:
            checkpoint = await db.client.table("checkpoints") \
                .select("*").eq("id", checkpoint_id).single().execute()
            state = checkpoint.data["state_snapshot"]
        else:
            state = {}
        
        result = await db.client.table("sessions") \
            .update({"status": "recovered", "context": state}) \
            .eq("id", session_id).execute()
        return result.data[0]

session_manager = SessionManager()
```

### Acceptance Criteria
- [ ] Full session lifecycle working (create → close)
- [ ] Checkpoints created and recoverable
- [ ] Artifacts tracked per session
- [ ] Timeline events emitted for all state transitions
- [ ] Session recovery from checkpoint working

---

## PHASE 8: Council Service — Core Engine
**Category**: Backend Core | **Duration**: 3 days | **Depends on**: Phase 7
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

### Objective
Build the core council orchestration engine that manages multi-model consultations.

### Files to Create

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/__init__.py`

```python
"""AEGION Council Kernel (ACK) — Multi-model AI council orchestration."""
```

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/types.py`

```python
"""Core types for the Council Kernel."""

from pydantic import BaseModel
from typing import Optional, Any
from enum import Enum

class CouncilType(str, Enum):
    CHILD = "child"           # Developer assistance
    DISTILLATION = "distillation"  # Session artifact processing
    PARENT = "parent"         # Architectural decisions (T2/T3)
    SENTINEL = "sentinel"     # Continuous monitoring

class CouncilProfile(str, Enum):
    TRIVIAL = "trivial"       # 1 model, 1 round
    SIMPLE = "simple"         # 2 models, 1 round
    MODERATE = "moderate"     # 3 models, 2 rounds
    COMPLEX = "complex"       # 4 models, 3 rounds
    CRITICAL = "critical"     # 5 models, 3 rounds + personas

class ModelResponse(BaseModel):
    model: str
    provider: str
    response: str
    confidence: float
    reasoning: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0

class CouncilResult(BaseModel):
    council_type: CouncilType
    profile: CouncilProfile
    query: str
    synthesis: str
    individual_responses: list[ModelResponse]
    consensus_score: float  # 0.0-1.0
    dissenting_views: list[str]
    total_cost_usd: float
    total_tokens: int
    total_latency_ms: int
    cache_hit: bool = False
    models_used: list[str]
    rounds_completed: int = 1
```

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/engine.py`

```python
"""Core council orchestration engine."""

from .types import *
from app.services.council_kernel.model_router import ModelRouter
from app.services.council_kernel.cascade import LLMCascade
from app.services.council_kernel.cache import SemanticCache
from app.db.supabase_client import db
import asyncio

class CouncilEngine:
    """Main orchestrator for all AI council operations."""
    
    def __init__(self):
        self.model_router = ModelRouter()
        self.cascade = LLMCascade()
        self.cache = SemanticCache()
    
    async def consult(self, workspace_id: str, query: str, 
                      council_type: CouncilType,
                      context: dict = None) -> CouncilResult:
        # 1. Check semantic cache
        cached = await self.cache.check(workspace_id, query)
        if cached:
            return CouncilResult(
                council_type=council_type, profile=CouncilProfile.TRIVIAL,
                query=query, synthesis=cached["response_text"],
                individual_responses=[], consensus_score=1.0,
                dissenting_views=[], total_cost_usd=0.0,
                total_tokens=0, total_latency_ms=0, cache_hit=True,
                models_used=[cached["response_model"]], rounds_completed=0
            )
        
        # 2. Determine council size
        profile = await self._classify_complexity(query, council_type)
        
        # 3. Select models
        models = await self.model_router.select_models(
            workspace_id, council_type, profile
        )
        
        # 4. Run council (parallel model calls)
        responses = await asyncio.gather(*[
            self.cascade.query(query, model, context)
            for model in models
        ])
        
        # 5. Synthesize
        synthesis = await self._synthesize(query, responses, profile)
        
        # 6. Cache result
        await self.cache.store(workspace_id, query, synthesis.synthesis, 
                               models[0] if models else "unknown")
        
        # 7. Track cost
        total_cost = sum(r.cost_usd for r in responses)
        await db.track_cost(workspace_id, ",".join(r.model for r in responses),
                           "multi", sum(r.tokens_in for r in responses),
                           sum(r.tokens_out for r in responses), total_cost,
                           council_type.value)
        
        return synthesis
    
    async def _classify_complexity(self, query: str, 
                                    council_type: CouncilType) -> CouncilProfile:
        if council_type == CouncilType.SENTINEL:
            return CouncilProfile.MODERATE
        if council_type == CouncilType.PARENT:
            return CouncilProfile.CRITICAL
        # Use cheap classifier for child/distillation
        return CouncilProfile.SIMPLE  # Default, override with classifier
    
    async def _synthesize(self, query: str, responses: list[ModelResponse],
                           profile: CouncilProfile) -> CouncilResult:
        all_texts = [r.response for r in responses]
        # Find consensus and dissent
        dissenting = [r.response for r in responses if r.confidence < 0.5]
        consensus = len([r for r in responses if r.confidence >= 0.7]) / max(len(responses), 1)
        
        # Use the highest-confidence response as synthesis base
        best = max(responses, key=lambda r: r.confidence)
        
        return CouncilResult(
            council_type=CouncilType.CHILD, profile=profile,
            query=query, synthesis=best.response,
            individual_responses=responses,
            consensus_score=consensus,
            dissenting_views=dissenting,
            total_cost_usd=sum(r.cost_usd for r in responses),
            total_tokens=sum(r.tokens_in + r.tokens_out for r in responses),
            total_latency_ms=max(r.latency_ms for r in responses),
            cache_hit=False,
            models_used=[r.model for r in responses],
            rounds_completed=1
        )

council_engine = CouncilEngine()
```

### Acceptance Criteria
- [ ] `CouncilEngine.consult()` method working end-to-end
- [ ] Cache check → classify → select models → parallel call → synthesize → cache store
- [ ] Cost tracked for every council invocation
- [ ] Council types (child, distillation, parent, sentinel) routing correctly

---

## PHASE 9: Model Router & Provider Abstraction
**Category**: ACK | **Duration**: 3 days | **Depends on**: Phase 8
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

### Objective
Create a unified interface for all LLM providers. Users can plug in any API key.

### Files to Create

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/model_router.py`

```python
"""Model Router: Unified interface for all LLM providers."""

from abc import ABC, abstractmethod
from .types import ModelResponse
import httpx, time, json

class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, model: str, **kwargs) -> ModelResponse:
        pass

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
    
    async def generate(self, prompt: str, model: str = "gpt-4o-mini", **kwargs) -> ModelResponse:
        start = time.time()
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "temperature": kwargs.get("temperature", 0.7)},
                timeout=30.0)
            data = resp.json()
            usage = data.get("usage", {})
            return ModelResponse(
                model=model, provider="openai",
                response=data["choices"][0]["message"]["content"],
                confidence=0.8, tokens_in=usage.get("prompt_tokens", 0),
                tokens_out=usage.get("completion_tokens", 0),
                cost_usd=self._calc_cost(model, usage),
                latency_ms=int((time.time() - start) * 1000))

    def _calc_cost(self, model: str, usage: dict) -> float:
        prices = {"gpt-4o": (2.5, 10.0), "gpt-4o-mini": (0.15, 0.6)}
        inp, out = prices.get(model, (2.5, 10.0))
        return (usage.get("prompt_tokens", 0) * inp + 
                usage.get("completion_tokens", 0) * out) / 1_000_000

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def generate(self, prompt: str, model: str = "claude-sonnet-4-5-20241022", **kwargs) -> ModelResponse:
        start = time.time()
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                json={"model": model, "max_tokens": 4096,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=60.0)
            data = resp.json()
            usage = data.get("usage", {})
            return ModelResponse(
                model=model, provider="anthropic",
                response=data["content"][0]["text"],
                confidence=0.85, tokens_in=usage.get("input_tokens", 0),
                tokens_out=usage.get("output_tokens", 0),
                cost_usd=self._calc_cost(model, usage),
                latency_ms=int((time.time() - start) * 1000))
    
    def _calc_cost(self, model: str, usage: dict) -> float:
        prices = {"claude-sonnet-4-5-20241022": (3.0, 15.0), 
                  "claude-haiku-4-5-20241022": (1.0, 5.0)}
        inp, out = prices.get(model, (3.0, 15.0))
        return (usage.get("input_tokens", 0) * inp + 
                usage.get("output_tokens", 0) * out) / 1_000_000

class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def generate(self, prompt: str, model: str = "deepseek-chat", **kwargs) -> ModelResponse:
        start = time.time()
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
                timeout=30.0)
            data = resp.json()
            usage = data.get("usage", {})
            return ModelResponse(
                model=model, provider="deepseek",
                response=data["choices"][0]["message"]["content"],
                confidence=0.75, tokens_in=usage.get("prompt_tokens", 0),
                tokens_out=usage.get("completion_tokens", 0),
                cost_usd=(usage.get("prompt_tokens", 0) * 0.014 + 
                          usage.get("completion_tokens", 0) * 0.028) / 1_000_000,
                latency_ms=int((time.time() - start) * 1000))

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def generate(self, prompt: str, model: str = "gemini-1.5-flash", **kwargs) -> ModelResponse:
        start = time.time()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": self.api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=30.0)
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            return ModelResponse(
                model=model, provider="google",
                response=text, confidence=0.78,
                tokens_in=usage.get("promptTokenCount", 0),
                tokens_out=usage.get("candidatesTokenCount", 0),
                cost_usd=(usage.get("promptTokenCount", 0) * 0.075 + 
                          usage.get("candidatesTokenCount", 0) * 0.30) / 1_000_000,
                latency_ms=int((time.time() - start) * 1000))

class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
    
    async def generate(self, prompt: str, model: str = "deepseek-coder:6.7b", **kwargs) -> ModelResponse:
        start = time.time()
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=120.0)
            data = resp.json()
            return ModelResponse(
                model=model, provider="ollama",
                response=data.get("response", ""),
                confidence=0.7, tokens_in=data.get("prompt_eval_count", 0),
                tokens_out=data.get("eval_count", 0),
                cost_usd=0.0,  # Free!
                latency_ms=int((time.time() - start) * 1000))

class CustomProvider(LLMProvider):
    """OpenAI-compatible custom endpoint."""
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
    
    async def generate(self, prompt: str, model: str = "default", **kwargs) -> ModelResponse:
        start = time.time()
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
                timeout=60.0)
            data = resp.json()
            usage = data.get("usage", {})
            return ModelResponse(
                model=model, provider="custom",
                response=data["choices"][0]["message"]["content"],
                confidence=0.7, tokens_in=usage.get("prompt_tokens", 0),
                tokens_out=usage.get("completion_tokens", 0),
                cost_usd=0.0, latency_ms=int((time.time() - start) * 1000))


class ModelRouter:
    """Routes requests to the appropriate LLM provider."""
    
    def __init__(self):
        self.providers: dict[str, LLMProvider] = {}
    
    def register_provider(self, name: str, provider: LLMProvider):
        self.providers[name] = provider
    
    async def configure_from_user_keys(self, user_api_keys: dict):
        """Configure providers from user-supplied API keys."""
        if user_api_keys.get("openai_key"):
            self.register_provider("openai", OpenAIProvider(user_api_keys["openai_key"]))
        if user_api_keys.get("anthropic_key"):
            self.register_provider("anthropic", AnthropicProvider(user_api_keys["anthropic_key"]))
        if user_api_keys.get("deepseek_key"):
            self.register_provider("deepseek", DeepSeekProvider(user_api_keys["deepseek_key"]))
        if user_api_keys.get("google_key"):
            self.register_provider("google", GeminiProvider(user_api_keys["google_key"]))
        if user_api_keys.get("ollama_url"):
            self.register_provider("ollama", OllamaProvider(user_api_keys["ollama_url"]))
        if user_api_keys.get("custom_key") and user_api_keys.get("custom_url"):
            self.register_provider("custom", CustomProvider(
                user_api_keys["custom_key"], user_api_keys["custom_url"]))
    
    async def select_models(self, workspace_id: str, council_type, 
                            profile) -> list[tuple[str, str]]:
        """Select models for a council based on profile and available providers."""
        available = list(self.providers.keys())
        
        MODEL_MAP = {
            "deepseek": "deepseek-chat",
            "google": "gemini-1.5-flash",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-haiku-4-5-20241022",
            "ollama": "deepseek-coder:6.7b"
        }
        
        PROFILE_SIZES = {
            "trivial": 1, "simple": 2, "moderate": 3, "complex": 4, "critical": 5
        }
        
        count = PROFILE_SIZES.get(profile.value, 2)
        # Prefer cheaper providers first
        priority = ["deepseek", "ollama", "google", "openai", "anthropic", "custom"]
        selected = []
        for p in priority:
            if p in available and len(selected) < count:
                selected.append((p, MODEL_MAP.get(p, "default")))
        
        return selected
```

### Acceptance Criteria
- [ ] All 6 providers working (OpenAI, Anthropic, DeepSeek, Gemini, Ollama, Custom)
- [ ] User can configure API keys via settings API
- [ ] Model selection based on council profile size
- [ ] Cost calculation accurate for each provider
- [ ] Graceful fallback when a provider fails

---

## PHASE 10: LLM Cascade (FrugalGPT)
**Category**: Cost | **Duration**: 2 days | **Depends on**: Phase 9
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

### Objective
Implement the FrugalGPT cascade: start cheap, escalate only if confidence is too low.

### Files to Create

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/cascade.py`

```python
"""FrugalGPT-style LLM cascade for cost optimization."""

from .types import ModelResponse
from .model_router import ModelRouter
from dataclasses import dataclass
import re

@dataclass
class CascadeTier:
    provider: str
    model: str
    cost_per_1m: float
    confidence_threshold: float
    level: int

class LLMCascade:
    """Start with cheapest model, escalate only when confidence is low."""
    
    TIERS = [
        CascadeTier("deepseek", "deepseek-chat", 0.04, 0.85, 1),
        CascadeTier("google", "gemini-1.5-flash", 0.38, 0.80, 2),
        CascadeTier("openai", "gpt-4o-mini", 0.75, 0.75, 3),
        CascadeTier("anthropic", "claude-haiku-4-5-20241022", 6.0, 0.0, 4),
    ]
    
    def __init__(self, model_router: ModelRouter):
        self.router = model_router
    
    async def query(self, prompt: str, context: dict = None) -> ModelResponse:
        available = list(self.router.providers.keys())
        
        for tier in self.TIERS:
            if tier.provider not in available:
                continue
            
            provider = self.router.providers[tier.provider]
            response = await provider.generate(prompt, tier.model)
            confidence = self._score_confidence(response.response)
            response.confidence = confidence
            
            if confidence >= tier.confidence_threshold:
                return response
        
        # Fallback: return last response regardless
        return response
    
    def _score_confidence(self, response: str) -> float:
        """Heuristic confidence scoring (replace with DistilBERT later)."""
        score = 0.8
        
        uncertainty_phrases = [
            "i'm not sure", "i think", "it might", "possibly", "perhaps",
            "i don't know", "unclear", "it depends", "hard to say"
        ]
        for phrase in uncertainty_phrases:
            if phrase in response.lower():
                score -= 0.1
        
        if len(response) < 50:
            score -= 0.15
        if len(response) > 200:
            score += 0.05
        
        code_blocks = len(re.findall(r'```', response))
        if code_blocks >= 2:
            score += 0.05
        
        return max(0.0, min(1.0, score))
```

### Acceptance Criteria
- [ ] Cascade starts with cheapest available model
- [ ] Escalates to next tier when confidence < threshold
- [ ] Stops and returns at first satisfactory response
- [ ] Cost tracking shows tiered usage (majority at Tier 1)
- [ ] Gracefully skips unavailable providers

---

## PHASE 11: Semantic Cache Layer
**Category**: Cost | **Duration**: 2 days | **Depends on**: Phase 3, 9
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

### Objective
Cache semantically similar queries using pgvector to avoid redundant LLM calls (70-86% cost savings).

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/cache.py`

```python
"""Semantic caching using Supabase pgvector."""

from sentence_transformers import SentenceTransformer
from app.db.supabase_client import db

class SemanticCache:
    def __init__(self):
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.TTL_HOURS = {
            "code_explanation": 168,    # 7 days
            "architecture": 720,        # 30 days
            "security": 24,             # 1 day
            "debate_result": 336,       # 14 days
            "default": 168
        }
    
    async def check(self, workspace_id: str, query: str, 
                    threshold: float = 0.92) -> dict | None:
        embedding = self.embedder.encode(query).tolist()
        return await db.check_cache(workspace_id, embedding, threshold)
    
    async def store(self, workspace_id: str, query: str, response: str, 
                    model: str, cache_type: str = "default") -> dict:
        embedding = self.embedder.encode(query).tolist()
        ttl = self.TTL_HOURS.get(cache_type, 168)
        return await db.store_cache(workspace_id, query, embedding, response, model, ttl)
    
    async def invalidate(self, workspace_id: str, pattern: str = None) -> int:
        """Invalidate cache entries matching pattern or all."""
        query = db.client.table("semantic_cache") \
            .delete().eq("workspace_id", workspace_id)
        if pattern:
            query = query.ilike("query_text", f"%{pattern}%")
        result = query.execute()
        return len(result.data) if result.data else 0

semantic_cache = SemanticCache()
```

### Acceptance Criteria
- [ ] Cache hit returns stored response with 0 LLM cost
- [ ] Similarity threshold 0.92 balances accuracy vs hit rate
- [ ] TTL-based expiration working per content type
- [ ] Cache invalidation by pattern or workspace

---

## PHASE 12: Prompt Compression Integration
**Category**: Cost | **Duration**: 1 day | **Depends on**: Phase 9
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

### Objective
Integrate LLMLingua for 5-20x prompt token reduction before LLM calls.

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/compressor.py`

```python
"""LLMLingua-2 prompt compression for token savings."""

class PromptCompressor:
    def __init__(self):
        self._compressor = None  # Lazy load (500MB model)
    
    def _get_compressor(self):
        if not self._compressor:
            from llmlingua import PromptCompressor as LC
            self._compressor = LC(
                model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
                use_llmlingua2=True)
        return self._compressor
    
    async def compress(self, prompt: str, target_ratio: float = 0.3) -> dict:
        if len(prompt.split()) < 100:
            return {"text": prompt, "ratio": 1.0, "saved": 0}
        
        result = self._get_compressor().compress_prompt(
            prompt, rate=target_ratio,
            force_tokens=["Archon", "Sentinel", "Chronos", "governance",
                         "approve", "reject", "risk", "decision"],
            drop_consecutive=True)
        
        return {
            "text": result["compressed_prompt"],
            "ratio": result["ratio"],
            "saved": result["origin_tokens"] - result["compressed_tokens"],
            "original": result["origin_tokens"],
            "compressed": result["compressed_tokens"]
        }

compressor = PromptCompressor()
```

**Add dependency**: `poetry add llmlingua`

### Acceptance Criteria
- [ ] Prompts >100 words get compressed before LLM calls
- [ ] Governance keywords preserved (force_tokens)
- [ ] Short prompts bypass compression
- [ ] Token savings tracked per request

---

## PHASE 13: Peer Review Engine
**Category**: ACK | **Duration**: 3 days | **Depends on**: Phase 8
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

### Objective
Implement adversarial peer review (inspired by teemulinna/ai-council) for hallucination reduction.

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/peer_review.py`

```python
"""Adversarial peer review engine for hallucination mitigation."""

from .types import ModelResponse, CouncilResult
from .model_router import ModelRouter
import asyncio

class PeerReviewEngine:
    """Each model independently answers, then reviews others' answers."""
    
    def __init__(self, model_router: ModelRouter):
        self.router = model_router
    
    async def run(self, query: str, models: list[tuple[str, str]], 
                  context: dict = None) -> CouncilResult:
        # Stage 1: Independent responses (parallel)
        drafts = await asyncio.gather(*[
            self.router.providers[provider].generate(
                f"Answer this independently. Be specific and factual.\n\n{query}",
                model)
            for provider, model in models
        ])
        
        # Stage 2: Peer review (each model reviews all others)
        reviews = await asyncio.gather(*[
            self._review_drafts(models[i], drafts, i, query)
            for i in range(len(models))
        ])
        
        # Stage 3: Synthesize with review feedback
        synthesis = await self._synthesize_with_reviews(query, drafts, reviews, models[0])
        
        return synthesis
    
    async def _review_drafts(self, reviewer: tuple, drafts: list[ModelResponse], 
                              reviewer_idx: int, query: str) -> str:
        others = [f"Draft {i+1}: {d.response}" 
                  for i, d in enumerate(drafts) if i != reviewer_idx]
        
        review_prompt = f"""Original question: {query}

Your own answer: {drafts[reviewer_idx].response}

Other panelists' answers:
{chr(10).join(others)}

REVIEW TASK: Identify factual errors, unsupported claims, or hallucinations 
in the other answers. Also note where they provide better information than yours.
Be specific about what's wrong and cite evidence."""
        
        provider, model = reviewer
        result = await self.router.providers[provider].generate(review_prompt, model)
        return result.response
    
    async def _synthesize_with_reviews(self, query: str, drafts: list, 
                                        reviews: list, chairman: tuple) -> CouncilResult:
        synth_prompt = f"""Original question: {query}

Draft answers and peer reviews:
{chr(10).join(f"Draft {i+1}: {d.response}\nReview of Draft {i+1}: {reviews[i]}" 
              for i, d in enumerate(drafts))}

SYNTHESIS TASK: Create the most accurate final answer by:
1. Keeping claims validated by multiple reviewers
2. Removing claims flagged as hallucinations
3. Incorporating corrections from peer reviews
4. Preserving dissenting views that have evidence"""
        
        provider, model = chairman
        synthesis = await self.router.providers[provider].generate(synth_prompt, model)
        
        consensus = sum(1 for r in reviews if "agree" in r.lower() or "correct" in r.lower()) / max(len(reviews), 1)
        dissenting = [r for r in reviews if "disagree" in r.lower() or "incorrect" in r.lower() or "error" in r.lower()]
        
        return CouncilResult(
            council_type="child", profile="moderate",
            query=query, synthesis=synthesis.response,
            individual_responses=drafts, consensus_score=consensus,
            dissenting_views=dissenting,
            total_cost_usd=sum(d.cost_usd for d in drafts) + synthesis.cost_usd,
            total_tokens=sum(d.tokens_in + d.tokens_out for d in drafts),
            total_latency_ms=max(d.latency_ms for d in drafts) * 3,
            models_used=[d.model for d in drafts], rounds_completed=3)

peer_review_engine = PeerReviewEngine(ModelRouter())
```

### Acceptance Criteria
- [ ] 3-stage pipeline: Independent → Review → Synthesize
- [ ] Each model reviews all others' drafts
- [ ] Hallucination flags tracked in reviews
- [ ] Dissenting views preserved in final output

---

## PHASE 14: Debate Engine (Anti-Sycophancy)
**Category**: ACK | **Duration**: 3 days | **Depends on**: Phase 8
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

### Objective
Multi-round structured debate with anti-groupthink protections (inspired by focuslead).

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/debate.py`

```python
"""Structured debate engine with anti-sycophancy protocol."""

from .types import ModelResponse
from .model_router import ModelRouter

class DebateEngine:
    MAX_ROUNDS = 3  # Hard limit (focuslead principle)
    
    def __init__(self, model_router: ModelRouter):
        self.router = model_router
    
    async def debate(self, proposition: str, models: list[tuple[str, str]], 
                     context: dict = None) -> dict:
        history = []
        
        for round_num in range(1, self.MAX_ROUNDS + 1):
            round_responses = []
            
            for i, (provider, model) in enumerate(models):
                prompt = self._build_debate_prompt(
                    proposition, history, round_num, i, len(models))
                
                response = await self.router.providers[provider].generate(prompt, model)
                round_responses.append({
                    "model": model, "provider": provider,
                    "position": response.response,
                    "round": round_num
                })
            
            history.append(round_responses)
            
            # Check for early consensus (> 80% agree)
            if self._check_consensus(round_responses) > 0.8 and round_num >= 2:
                break
        
        # Anti-sycophancy: validate contrarian views
        contrarian = self._extract_contrarian(history)
        
        # Fresh Eyes Validation (if contrarian exists)
        if contrarian and len(models) > 1:
            fresh = await self._fresh_eyes_validation(
                proposition, history, contrarian, models[-1])
            history.append([{"model": "fresh_eyes", "position": fresh}])
        
        return {
            "proposition": proposition,
            "rounds": len(history),
            "history": history,
            "consensus": self._check_consensus(history[-1]) if history else 0.0,
            "contrarian_views": contrarian,
            "final_position": self._determine_final_position(history)
        }
    
    def _build_debate_prompt(self, proposition: str, history: list, 
                              round_num: int, participant_idx: int, 
                              total_participants: int) -> str:
        base = f"""DEBATE ROUND {round_num}/{self.MAX_ROUNDS}
Proposition: {proposition}

RULES (ANTI-SYCOPHANCY PROTOCOL):
- You MUST state your genuine position, not just agree with others
- If you disagree, you MUST provide specific evidence
- Changing your position requires citing new evidence
- "I agree because everyone else does" is INVALID
- Your dissent is PROTECTED — you cannot be overruled without evidence
"""
        if history:
            prev_round = history[-1]
            base += "\n\nPrevious round positions:\n"
            for j, resp in enumerate(prev_round):
                label = "You" if j == participant_idx else f"Participant {j+1}"
                base += f"\n{label}: {resp['position'][:500]}\n"
            base += "\n\nState your updated position with evidence:"
        else:
            base += "\n\nState your initial position with evidence:"
        
        return base
    
    def _check_consensus(self, responses: list) -> float:
        if not responses:
            return 0.0
        positions = [r.get("position", "")[:100].lower() for r in responses]
        agree_count = sum(1 for p in positions if "agree" in p or "support" in p)
        return agree_count / len(positions)
    
    def _extract_contrarian(self, history: list) -> list:
        """Find views that persisted against majority across rounds."""
        if not history:
            return []
        contrarian = []
        for round_responses in history:
            for resp in round_responses:
                pos = resp.get("position", "").lower()
                if any(w in pos for w in ["disagree", "however", "alternative", "risk", "concern"]):
                    contrarian.append(resp)
        return contrarian
    
    async def _fresh_eyes_validation(self, proposition: str, history: list,
                                      contrarian: list, validator: tuple) -> str:
        prompt = f"""FRESH EYES VALIDATION
You are a NEW participant who has NOT been part of this debate.

Proposition: {proposition}

Debate Summary:
- Majority position: {history[-1][0].get('position', '')[:300]}
- Contrarian views: {contrarian[0].get('position', '')[:300] if contrarian else 'None'}

TASK: As a fresh evaluator, assess:
1. Is the majority position well-supported?
2. Do the contrarian views have merit?
3. What is YOUR independent assessment?"""
        
        provider, model = validator
        result = await self.router.providers[provider].generate(prompt, model)
        return result.response
    
    def _determine_final_position(self, history: list) -> str:
        if not history:
            return "No debate occurred"
        last_round = history[-1]
        return last_round[0].get("position", "") if last_round else "No position"

debate_engine = DebateEngine(ModelRouter())
```

### Acceptance Criteria
- [ ] 3-round maximum debate with early consensus exit
- [ ] Anti-sycophancy protocol enforced in prompts
- [ ] Contrarian views extracted and protected
- [ ] Fresh Eyes Validation triggered when dissent exists
- [ ] Debate history fully tracked

---

## PHASE 15: Rubric Evaluation Engine
**Category**: ACK | **Duration**: 2 days | **Depends on**: Phase 8
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/rubric.py`

```python
"""Rubric-based scoring engine (inspired by PolyCouncil)."""

from .types import ModelResponse

RUBRICS = {
    "code_review": {
        "correctness": {"weight": 0.3, "description": "Code works as intended"},
        "security": {"weight": 0.25, "description": "No vulnerabilities"},
        "maintainability": {"weight": 0.2, "description": "Clean, readable code"},
        "performance": {"weight": 0.15, "description": "Efficient implementation"},
        "test_coverage": {"weight": 0.1, "description": "Adequate test coverage"}
    },
    "architecture": {
        "scalability": {"weight": 0.25, "description": "Handles growth"},
        "governance_compliance": {"weight": 0.25, "description": "Follows AEGION governance"},
        "simplicity": {"weight": 0.2, "description": "Not over-engineered"},
        "security": {"weight": 0.2, "description": "Security by design"},
        "reversibility": {"weight": 0.1, "description": "Decision can be unmade"}
    },
    "general": {
        "accuracy": {"weight": 0.35, "description": "Factually correct"},
        "completeness": {"weight": 0.25, "description": "Covers all aspects"},
        "clarity": {"weight": 0.2, "description": "Clear and understandable"},
        "evidence": {"weight": 0.2, "description": "Claims backed by evidence"}
    }
}

class RubricEngine:
    async def score(self, response: str, rubric_name: str = "general",
                    evaluator=None) -> dict:
        rubric = RUBRICS.get(rubric_name, RUBRICS["general"])
        
        if evaluator:
            # Use LLM to score against rubric
            scores = await self._llm_score(response, rubric, evaluator)
        else:
            # Heuristic scoring
            scores = self._heuristic_score(response, rubric)
        
        weighted = sum(scores[k] * rubric[k]["weight"] for k in rubric)
        return {"scores": scores, "weighted_total": weighted, "rubric": rubric_name}
    
    async def _llm_score(self, response: str, rubric: dict, evaluator) -> dict:
        criteria = "\n".join(f"- {k}: {v['description']} (weight: {v['weight']})" 
                            for k, v in rubric.items())
        prompt = f"""Score this response on each criterion (0.0-1.0):

Response: {response[:2000]}

Criteria:
{criteria}

Return ONLY a JSON object with criterion names as keys and float scores as values."""
        
        result = await evaluator.generate(prompt, evaluator.model if hasattr(evaluator, 'model') else "default")
        import json
        try:
            return json.loads(result.response)
        except:
            return {k: 0.5 for k in rubric}
    
    def _heuristic_score(self, response: str, rubric: dict) -> dict:
        scores = {}
        for criterion in rubric:
            score = 0.6  # base
            if len(response) > 200: score += 0.1
            if "```" in response: score += 0.1  # Has code examples
            if any(w in response.lower() for w in ["because", "evidence", "reason"]): score += 0.1
            scores[criterion] = min(1.0, score)
        return scores

rubric_engine = RubricEngine()
```

### Acceptance Criteria
- [ ] Pre-defined rubrics for code_review, architecture, general
- [ ] Both LLM-based and heuristic scoring modes
- [ ] Weighted total score calculated correctly
- [ ] Custom rubrics can be added per workspace

---

## PHASE 16: Persona Engine
**Category**: ACK | **Duration**: 2 days | **Depends on**: Phase 8
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/persona.py`

```python
"""Persona-based debate engine with AEGION governance roles."""

PERSONAS = {
    "security_auditor": {
        "name": "Security Auditor",
        "system_prompt": "You are a security expert. Your ONLY concern is finding vulnerabilities, "
                        "data exposure risks, injection attacks, and supply chain threats. "
                        "You are paranoid by design. Rate everything from a security perspective.",
        "focus": ["CVE", "injection", "auth", "encryption", "OWASP", "supply chain"]
    },
    "performance_architect": {
        "name": "Performance Architect",
        "system_prompt": "You are a performance engineer. You care about latency, throughput, "
                        "memory usage, query optimization, and scalability. "
                        "Every millisecond matters. Identify bottlenecks ruthlessly.",
        "focus": ["latency", "throughput", "memory", "cache", "N+1", "index"]
    },
    "cost_analyst": {
        "name": "Cost Analyst",
        "system_prompt": "You analyze every decision through a cost lens. API costs, compute costs, "
                        "storage costs, opportunity costs. Find the cheapest viable solution. "
                        "Challenge expensive approaches with cheaper alternatives.",
        "focus": ["cost", "pricing", "budget", "token", "compute", "storage"]
    },
    "governance_advisor": {
        "name": "Governance Advisor",
        "system_prompt": "You enforce AEGION's governance model. No AI writes to Chronos directly. "
                        "No AI approves decisions. All changes must follow the tier system "
                        "(T0→T3). You ensure governance boundaries are never violated.",
        "focus": ["Archon", "tier", "governance", "approval", "policy", "compliance"]
    },
    "user_advocate": {
        "name": "User Advocate",
        "system_prompt": "You represent the end user. Is this feature useful? Is it intuitive? "
                        "Does it add complexity without value? Challenge features that are "
                        "technically cool but user-hostile. Simplicity wins.",
        "focus": ["UX", "usability", "simplicity", "documentation", "onboarding"]
    },
    "devils_advocate": {
        "name": "Devil's Advocate",
        "system_prompt": "Your job is to DISAGREE with the majority position and find flaws. "
                        "You must present counter-arguments even when the majority is right. "
                        "Find edge cases, failure modes, and unintended consequences.",
        "focus": ["edge case", "failure", "risk", "alternative", "bias"]
    }
}

class PersonaEngine:
    async def debate_with_personas(self, proposition: str, 
                                     persona_keys: list[str],
                                     model_router, models: list) -> dict:
        responses = []
        for i, key in enumerate(persona_keys):
            persona = PERSONAS.get(key, PERSONAS["user_advocate"])
            provider, model = models[i % len(models)]
            
            prompt = f"""{persona['system_prompt']}

PROPOSITION: {proposition}

Respond in character as {persona['name']}. 
Focus on: {', '.join(persona['focus'])}
Be specific and provide evidence for your position."""
            
            result = await model_router.providers[provider].generate(prompt, model)
            responses.append({
                "persona": persona["name"],
                "persona_key": key,
                "position": result.response,
                "model": model,
                "cost": result.cost_usd
            })
        
        return {"proposition": proposition, "persona_responses": responses}

persona_engine = PersonaEngine()
```

### Acceptance Criteria
- [ ] 6 AEGION-specific personas defined and working
- [ ] Persona system prompts produce distinct, focused responses
- [ ] Personas rotate across available models
- [ ] Custom personas can be added per workspace

---

## PHASE 17: Evidence Manager
**Category**: ACK | **Duration**: 2 days | **Depends on**: Phase 6, 8
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/evidence.py`

```python
"""Evidence Manager: Links AI reasoning to execution data."""

from app.db.supabase_client import db
from app.services.knowledge_graph import knowledge_graph

class EvidenceManager:
    async def gather_evidence(self, workspace_id: str, query: str) -> dict:
        """Gather relevant evidence from Chronos + Praxis."""
        # Similar past decisions
        similar_decisions = await knowledge_graph.search_similar(
            workspace_id, query, limit=5)
        
        # Recent timeline events
        recent_events = db.client.table("timeline_events") \
            .select("*").eq("workspace_id", workspace_id) \
            .order("timestamp", desc=True).limit(20).execute()
        
        # Related risk signals
        risks = db.client.table("risk_signals") \
            .select("*").eq("workspace_id", workspace_id) \
            .eq("resolved", False).order("created_at", desc=True).limit(10).execute()
        
        # Past ADRs
        adrs = db.client.table("adrs") \
            .select("*").eq("workspace_id", workspace_id) \
            .order("created_at", desc=True).limit(10).execute()
        
        return {
            "similar_decisions": similar_decisions,
            "recent_events": recent_events.data if recent_events.data else [],
            "active_risks": risks.data if risks.data else [],
            "past_adrs": adrs.data if adrs.data else []
        }
    
    async def attach_evidence(self, decision_id: str, evidence: dict) -> dict:
        return db.client.table("decisions") \
            .update({"evidence": evidence}) \
            .eq("id", decision_id).execute()

evidence_manager = EvidenceManager()
```

### Acceptance Criteria
- [ ] Evidence gathered from knowledge graph, timeline, risks, and ADRs
- [ ] Evidence attached to decisions for traceability
- [ ] Semantic search finds relevant past decisions

---

## PHASE 18: Council Kernel Integration
**Category**: ACK | **Duration**: 3 days | **Depends on**: Phases 11-17
**✅ STATUS: COMPLETE** — Implemented 2026-04-09

### Objective
Wire all ACK engines into the main CouncilEngine and expose via API.

#### [MODIFY] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/engine.py`
- Integrate PeerReviewEngine, DebateEngine, RubricEngine, PersonaEngine, EvidenceManager
- Route to correct engine based on council type and profile

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/api/v1/council.py`

```python
"""Council API endpoints."""

from fastapi import APIRouter, Depends
from app.auth.supabase_auth import get_current_user
from app.services.council_kernel.engine import council_engine
from app.services.council_kernel.types import CouncilType
from pydantic import BaseModel

router = APIRouter(prefix="/council", tags=["Council"])

class ConsultRequest(BaseModel):
    query: str
    council_type: str = "child"
    context: dict = {}

@router.post("/consult")
async def consult(req: ConsultRequest, user: dict = Depends(get_current_user)):
    result = await council_engine.consult(
        workspace_id=user["workspace_id"],
        query=req.query,
        council_type=CouncilType(req.council_type),
        context=req.context)
    return result.model_dump()

@router.get("/cost/summary")
async def cost_summary(user: dict = Depends(get_current_user)):
    from app.db.supabase_client import db
    result = db.client.table("cost_tracking") \
        .select("*").eq("workspace_id", user["workspace_id"]).execute()
    total = sum(r["cost_usd"] for r in (result.data or []))
    return {"total_cost_usd": total, "entries": len(result.data or [])}
```

### Acceptance Criteria
- [ ] `/api/v1/council/consult` endpoint working
- [ ] Child council uses cascade + cache
- [ ] Parent council uses debate + persona + peer review
- [ ] Sentinel council uses rubric scoring
- [ ] Cost tracking per request

---

## PHASE 19: Archon Governance — Tier System
**Category**: Governance | **Duration**: 3 days | **Depends on**: Phase 5
**✅ STATUS: COMPLETE** — Implemented 2026-04-09 (archon/council_bridge.py)

### Objective
Implement the 4-tier governance system (T0-T3) with proper authorization flows.

#### [MODIFY] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/archon_engine.py`

```python
"""Archon Governance Engine — Tier-based decision authority."""

from app.db.supabase_client import db

class ArchonEngine:
    TIER_POLICIES = {
        0: {"authority": "auto", "requires_human": False, "council": None,
            "description": "Trivial changes (formatting, comments)"},
        1: {"authority": "auto", "requires_human": False, "council": "child",
            "description": "Low-impact changes (bug fixes, small features)"},
        2: {"authority": "council", "requires_human": False, "council": "parent",
            "description": "Moderate impact (new APIs, schema changes)"},
        3: {"authority": "human", "requires_human": True, "council": "parent",
            "description": "High impact (architecture, security, breaking changes)"}
    }
    
    async def evaluate_proposal(self, proposal_id: str, workspace_id: str) -> dict:
        proposal = await db.client.table("proposals") \
            .select("*").eq("id", proposal_id).single().execute()
        
        tier = proposal.data["tier"]
        policy = self.TIER_POLICIES[tier]
        
        if policy["authority"] == "auto":
            return await self._auto_approve(proposal.data, workspace_id)
        elif policy["authority"] == "council":
            return await self._council_review(proposal.data, workspace_id)
        else:
            return await self._request_human_review(proposal.data, workspace_id)
    
    async def _auto_approve(self, proposal: dict, workspace_id: str) -> dict:
        await db.update_proposal_status(proposal["id"], "approved")
        await db.record_decision({
            "workspace_id": workspace_id,
            "proposal_id": proposal["id"],
            "decision_type": proposal["proposal_type"],
            "outcome": "approved",
            "tier": proposal["tier"],
            "rationale": "Auto-approved: Tier 0/1 change",
            "decided_by": "archon_auto"
        })
        return {"status": "approved", "method": "auto"}
    
    async def _council_review(self, proposal: dict, workspace_id: str) -> dict:
        from app.services.council_kernel.engine import council_engine
        from app.services.council_kernel.types import CouncilType
        
        result = await council_engine.consult(
            workspace_id=workspace_id,
            query=f"Review this proposal: {proposal['title']}\n{proposal['description']}",
            council_type=CouncilType.PARENT,
            context={"proposal": proposal})
        
        # Council recommends, but doesn't decide for T2
        await db.update_proposal_status(proposal["id"], "pending",)
        await db.client.table("proposals") \
            .update({"council_result": result.model_dump()}) \
            .eq("id", proposal["id"]).execute()
        
        return {"status": "pending_review", "council_result": result.model_dump()}
    
    async def _request_human_review(self, proposal: dict, workspace_id: str) -> dict:
        await db.update_proposal_status(proposal["id"], "pending")
        await db.append_event(workspace_id, "proposal.needs_human_review",
                              "proposal", proposal["id"], "archon",
                              {"tier": proposal["tier"], "title": proposal["title"]})
        return {"status": "pending_human_review", "message": "T3 requires human approval"}

archon = ArchonEngine()
```

### Acceptance Criteria
- [ ] T0/T1 proposals auto-approved
- [ ] T2 proposals get council review, then await human
- [ ] T3 proposals always require human approval
- [ ] All decisions immutably recorded
- [ ] AI cannot approve its own proposals

---

## PHASE 20: Archon — Freeze Mode & Policy Engine
**Category**: Governance | **Duration**: 2 days | **Depends on**: Phase 19
**✅ STATUS: COMPLETE** — Already implemented in archon/gates.py + freeze_escalation.py

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/freeze_manager.py`

```python
"""Workspace freeze mode — halt all AI operations."""

from app.db.supabase_client import db

class FreezeManager:
    async def freeze(self, workspace_id: str, reason: str, actor: str) -> dict:
        await db.client.table("workspaces").update({
            "settings": {"frozen": True, "freeze_reason": reason, "frozen_by": actor}
        }).eq("id", workspace_id).execute()
        
        await db.append_event(workspace_id, "workspace.frozen", "workspace",
                              workspace_id, actor, {"reason": reason})
        return {"status": "frozen", "reason": reason}
    
    async def unfreeze(self, workspace_id: str, actor: str) -> dict:
        await db.client.table("workspaces").update({
            "settings": {"frozen": False}
        }).eq("id", workspace_id).execute()
        
        await db.append_event(workspace_id, "workspace.unfrozen", "workspace",
                              workspace_id, actor, {})
        return {"status": "active"}
    
    async def is_frozen(self, workspace_id: str) -> bool:
        ws = await db.client.table("workspaces") \
            .select("settings").eq("id", workspace_id).single().execute()
        return ws.data.get("settings", {}).get("frozen", False)

freeze_manager = FreezeManager()
```

### Acceptance Criteria
- [ ] Freeze halts all AI council operations
- [ ] Unfreeze restores normal operation
- [ ] Freeze events logged in timeline

---

## PHASES 21-23: Sentinel Engine (Risk, Drift, Security)
**Category**: Governance | **Duration**: 7 days | **Depends on**: Phase 19
**✅ STATUS: COMPLETE** — Implemented 2026-04-09 (sentinel/council_bridge.py + API)

### PHASE 21: Sentinel — Risk Scoring Engine

#### [MODIFY] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/sentinel_engine.py`

```python
"""Sentinel: Risk analysis and continuous monitoring."""

from app.db.supabase_client import db

class SentinelEngine:
    RISK_WEIGHTS = {
        "security": 5.0,
        "breaking_change": 4.0,
        "data_schema": 3.5,
        "performance": 3.0,
        "dependency": 2.5,
        "code_quality": 1.5
    }
    
    async def analyze_change(self, workspace_id: str, change: dict) -> dict:
        """Analyze a code change for risk signals."""
        signals = []
        
        # Check for security patterns
        if any(p in str(change) for p in ["password", "secret", "token", "api_key", "eval(", "exec("]):
            signals.append(self._create_signal(workspace_id, "security", "high",
                "Potential secret or dangerous function detected"))
        
        # Check for schema changes
        if any(p in str(change) for p in ["ALTER TABLE", "DROP TABLE", "CREATE TABLE", "migration"]):
            signals.append(self._create_signal(workspace_id, "data_schema", "high",
                "Database schema change detected"))
        
        # Check for dependency changes
        if any(f in str(change.get("files", [])) for f in ["package.json", "pyproject.toml", "Cargo.toml"]):
            signals.append(self._create_signal(workspace_id, "dependency", "medium",
                "Dependency file modified"))
        
        # Store signals
        for signal in signals:
            await db.client.table("risk_signals").insert(signal).execute()
        
        # Calculate composite risk score
        risk_score = sum(self.RISK_WEIGHTS.get(s["signal_type"], 1.0) 
                        for s in signals) / 10.0
        
        return {"risk_score": min(1.0, risk_score), "signals": signals, 
                "recommended_tier": self._recommend_tier(risk_score)}
    
    def _create_signal(self, workspace_id, signal_type, severity, description):
        return {"workspace_id": workspace_id, "signal_type": signal_type,
                "severity": severity, "source": "sentinel_auto",
                "description": description}
    
    def _recommend_tier(self, risk_score: float) -> int:
        if risk_score < 0.2: return 0
        if risk_score < 0.4: return 1
        if risk_score < 0.7: return 2
        return 3

sentinel = SentinelEngine()
```

### PHASE 22: Drift Detection
Add to SentinelEngine:
```python
    async def detect_drift(self, workspace_id: str) -> dict:
        """Compare current state against approved ADRs."""
        adrs = db.client.table("adrs").select("*") \
            .eq("workspace_id", workspace_id).eq("status", "accepted").execute()
        
        violations = []
        for adr in (adrs.data or []):
            # Check if recent changes violate accepted ADRs
            recent = db.client.table("timeline_events").select("*") \
                .eq("workspace_id", workspace_id) \
                .order("timestamp", desc=True).limit(50).execute()
            
            for event in (recent.data or []):
                if self._violates_adr(event, adr):
                    violations.append({
                        "adr_id": adr["id"], "adr_title": adr["title"],
                        "event": event, "type": "drift"
                    })
        
        return {"violations": violations, "drift_detected": len(violations) > 0}
```

### PHASE 23: Security Council
```python
    async def security_scan(self, workspace_id: str, code: str) -> dict:
        """Run AI council for security analysis."""
        from app.services.council_kernel.engine import council_engine
        from app.services.council_kernel.types import CouncilType
        
        result = await council_engine.consult(
            workspace_id=workspace_id,
            query=f"Perform a security audit of this code:\n```\n{code[:5000]}\n```",
            council_type=CouncilType.SENTINEL)
        
        return {"security_review": result.synthesis, "risk_signals": []}
```

### Acceptance Criteria (Phases 21-23)
- [ ] Risk scoring produces composite scores from weighted signals
- [ ] Tier recommendations based on risk score
- [ ] Drift detection compares changes against accepted ADRs
- [ ] Security council runs via ACK for code analysis
- [ ] All signals stored in `risk_signals` table

---

## PHASES 24-25: Noesis & Ghost Text
**Category**: Intelligence | **Duration**: 6 days | **Depends on**: Phase 18
**✅ STATUS: COMPLETE** — Phase 24 in noesis/, Phase 25 in ghost_text.py

### PHASE 24: Noesis — Cognitive Analytics

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/noesis_engine.py`

```python
"""Noesis: Cognitive analytics and pattern recognition."""

from app.db.supabase_client import db

class NoesisEngine:
    async def analyze_patterns(self, workspace_id: str) -> dict:
        """Identify development patterns, bottlenecks, and trends."""
        sessions = db.client.table("sessions").select("*") \
            .eq("workspace_id", workspace_id) \
            .order("started_at", desc=True).limit(100).execute()
        
        decisions = db.client.table("decisions").select("*") \
            .eq("workspace_id", workspace_id) \
            .order("decided_at", desc=True).limit(100).execute()
        
        costs = db.client.table("cost_tracking").select("*") \
            .eq("workspace_id", workspace_id) \
            .order("created_at", desc=True).limit(500).execute()
        
        return {
            "session_patterns": self._analyze_sessions(sessions.data or []),
            "decision_patterns": self._analyze_decisions(decisions.data or []),
            "cost_trends": self._analyze_costs(costs.data or []),
            "recommendations": self._generate_recommendations(sessions.data, decisions.data, costs.data)
        }
    
    def _analyze_sessions(self, sessions: list) -> dict:
        if not sessions:
            return {}
        avg_duration = sum(1 for s in sessions if s.get("closed_at")) / max(len(sessions), 1)
        return {"total": len(sessions), "completion_rate": avg_duration}
    
    def _analyze_decisions(self, decisions: list) -> dict:
        if not decisions:
            return {}
        approved = sum(1 for d in decisions if d["outcome"] == "approved")
        rejected = sum(1 for d in decisions if d["outcome"] == "rejected")
        return {"total": len(decisions), "approval_rate": approved / max(len(decisions), 1),
                "rejection_rate": rejected / max(len(decisions), 1)}
    
    def _analyze_costs(self, costs: list) -> dict:
        if not costs:
            return {}
        total = sum(c["cost_usd"] for c in costs)
        cache_hits = sum(1 for c in costs if c.get("cache_hit"))
        return {"total_usd": total, "cache_hit_rate": cache_hits / max(len(costs), 1)}
    
    def _generate_recommendations(self, sessions, decisions, costs) -> list:
        recs = []
        if costs:
            cache_rate = sum(1 for c in costs if c.get("cache_hit")) / max(len(costs), 1)
            if cache_rate < 0.3:
                recs.append("Cache hit rate is low. Consider broader similarity thresholds.")
        return recs

noesis = NoesisEngine()
```

### PHASE 25: Ghost Text — AI Completions

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/ghost_text.py`

```python
"""Ghost Text: Inline AI completions for code editor."""

from app.services.council_kernel.cascade import LLMCascade

class GhostTextEngine:
    def __init__(self):
        self.cascade = None
    
    async def complete(self, workspace_id: str, prefix: str, suffix: str,
                       language: str, file_path: str) -> dict:
        prompt = f"""Complete the code between PREFIX and SUFFIX.
Language: {language}
File: {file_path}

PREFIX:
{prefix[-500:]}

SUFFIX:
{suffix[:200]}

Return ONLY the completion text, no explanations."""
        
        if self.cascade:
            result = await self.cascade.query(prompt)
            return {"completion": result.response.strip(), "model": result.model,
                    "cost": result.cost_usd, "confidence": result.confidence}
        
        return {"completion": "", "model": "none", "cost": 0.0, "confidence": 0.0}

ghost_text = GhostTextEngine()
```

### Acceptance Criteria (Phases 24-25)
- [ ] Noesis produces pattern analysis from session/decision/cost data
- [ ] Cost trends tracked over time
- [ ] Recommendations generated based on patterns
- [ ] Ghost Text returns completions from cascade
- [ ] Ghost Text works with prefix/suffix context

---

## PHASE 26: Chronos — Timeline & Event Sourcing
**Category**: Memory | **Duration**: 3 days | **Depends on**: Phase 3
**✅ STATUS: COMPLETE** — Already implemented in chronos/timeline.py + API

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/chronos_engine.py`

```python
"""Chronos: Immutable event timeline and decision history."""

from app.db.supabase_client import db
from datetime import datetime

class ChronosEngine:
    async def record_event(self, workspace_id: str, event_type: str,
                           entity_type: str, entity_id: str, actor: str,
                           payload: dict) -> dict:
        return await db.append_event(workspace_id, event_type, entity_type,
                                     entity_id, actor, payload)
    
    async def get_timeline(self, workspace_id: str, entity_type: str = None,
                           entity_id: str = None, limit: int = 50) -> list:
        query = db.client.table("timeline_events").select("*") \
            .eq("workspace_id", workspace_id) \
            .order("timestamp", desc=True).limit(limit)
        if entity_type:
            query = query.eq("entity_type", entity_type)
        if entity_id:
            query = query.eq("entity_id", entity_id)
        result = query.execute()
        return result.data or []
    
    async def get_decision_lineage(self, decision_id: str) -> list:
        """Walk the chain of superseding decisions."""
        chain = []
        current = decision_id
        while current:
            decision = db.client.table("decisions").select("*") \
                .eq("id", current).single().execute()
            if not decision.data:
                break
            chain.append(decision.data)
            current = decision.data.get("supersedes_id")
        return chain

chronos = ChronosEngine()
```

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/api/v1/timeline.py`
```python
from fastapi import APIRouter, Depends, Query
from app.auth.supabase_auth import get_current_user
from app.services.chronos_engine import chronos

router = APIRouter(prefix="/timeline", tags=["Timeline"])

@router.get("/events")
async def get_events(entity_type: str = None, limit: int = Query(50, le=200),
                     user: dict = Depends(get_current_user)):
    return await chronos.get_timeline(user["workspace_id"], entity_type, limit=limit)

@router.get("/decisions/{decision_id}/lineage")
async def get_lineage(decision_id: str, user: dict = Depends(get_current_user)):
    return await chronos.get_decision_lineage(decision_id)
```

### Acceptance Criteria
- [ ] All system events recorded in append-only timeline
- [ ] Timeline queryable by entity type, entity ID, time range
- [ ] Decision lineage chain traversal working
- [ ] Events cannot be modified or deleted (append-only)

---

## PHASE 27: Chronos — Immutable Decision Records
**Category**: Memory | **Duration**: 2 days | **Depends on**: Phase 26
**✅ STATUS: COMPLETE** — Already implemented in chronos/immutability.py

### Objective
Add lineage hashing (SHA256 chain) to decisions for tamper detection.

```python
# Add to chronos_engine.py
import hashlib, json

async def record_decision_with_lineage(self, workspace_id: str, decision_data: dict) -> dict:
    # Find parent decision
    parent_hash = ""
    if decision_data.get("supersedes_id"):
        parent = db.client.table("decisions").select("lineage_hash") \
            .eq("id", decision_data["supersedes_id"]).single().execute()
        parent_hash = parent.data.get("lineage_hash", "") if parent.data else ""
    
    # Create lineage hash
    hash_input = json.dumps({
        "parent_hash": parent_hash,
        "outcome": decision_data["outcome"],
        "tier": decision_data["tier"],
        "decided_by": decision_data["decided_by"],
        "timestamp": datetime.utcnow().isoformat()
    }, sort_keys=True)
    decision_data["lineage_hash"] = hashlib.sha256(hash_input.encode()).hexdigest()
    
    return await db.record_decision(decision_data)

async def verify_lineage(self, decision_id: str) -> dict:
    """Verify the integrity of the decision chain."""
    chain = await self.get_decision_lineage(decision_id)
    for i, decision in enumerate(chain[:-1]):
        expected_parent = chain[i+1]["lineage_hash"] if i+1 < len(chain) else ""
        # Recompute and verify
        if not self._verify_hash(decision, expected_parent):
            return {"valid": False, "broken_at": decision["id"]}
    return {"valid": True, "chain_length": len(chain)}
```

### Acceptance Criteria
- [ ] SHA256 lineage hash computed for every decision
- [ ] Chain verification detects tampering
- [ ] Superseding decisions link to parent via hash

---

## PHASE 28: Praxis — Sandbox Hardening
**Category**: Execution | **Duration**: 3 days | **Depends on**: Phase 7
**✅ STATUS: COMPLETE** — Already implemented in praxis/sandbox.py + sandbox_hardening.py

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/sandbox.py`

```python
"""Praxis sandbox: Safe code execution environment."""

import subprocess, tempfile, os
from pathlib import Path

class Sandbox:
    MAX_EXECUTION_TIME = 30  # seconds
    MAX_OUTPUT_SIZE = 1024 * 100  # 100KB
    
    async def execute(self, code: str, language: str, 
                      workspace_id: str) -> dict:
        """Execute code in isolated environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runners = {
                "python": self._run_python,
                "javascript": self._run_javascript,
                "typescript": self._run_typescript,
                "bash": self._run_bash
            }
            runner = runners.get(language)
            if not runner:
                return {"error": f"Unsupported language: {language}"}
            return await runner(code, tmpdir)
    
    async def _run_python(self, code: str, workdir: str) -> dict:
        filepath = os.path.join(workdir, "script.py")
        with open(filepath, "w") as f:
            f.write(code)
        return self._execute_process(["python3", filepath], workdir)
    
    async def _run_javascript(self, code: str, workdir: str) -> dict:
        filepath = os.path.join(workdir, "script.js")
        with open(filepath, "w") as f:
            f.write(code)
        return self._execute_process(["node", filepath], workdir)
    
    def _execute_process(self, cmd: list, workdir: str) -> dict:
        try:
            result = subprocess.run(cmd, cwd=workdir, capture_output=True,
                                   text=True, timeout=self.MAX_EXECUTION_TIME)
            return {
                "stdout": result.stdout[:self.MAX_OUTPUT_SIZE],
                "stderr": result.stderr[:self.MAX_OUTPUT_SIZE],
                "exit_code": result.returncode,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {"error": "Execution timed out", "exit_code": -1, "success": False}

sandbox = Sandbox()
```

### Acceptance Criteria
- [ ] Python, JS, TS, Bash execution in temp dirs
- [ ] 30-second timeout enforced
- [ ] Output size limited to 100KB
- [ ] No access to host filesystem outside temp dir

---

## PHASE 29: Memory & Rules Engine
**Category**: Memory | **Duration**: 2 days | **Depends on**: Phase 3
**✅ STATUS: COMPLETE** — Implemented 2026-04-09 (memory_engine.py, rules_engine.py + migration)

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/memory_engine.py`

```python
"""Memory engine: Persistent workspace knowledge with semantic retrieval."""

from app.db.supabase_client import db
from sentence_transformers import SentenceTransformer

class MemoryEngine:
    def __init__(self):
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
    
    async def store(self, workspace_id: str, content: str, memory_type: str,
                    source_session_id: str = None) -> dict:
        embedding = self.embedder.encode(content).tolist()
        return db.client.table("memories").insert({
            "workspace_id": workspace_id, "content": content,
            "memory_type": memory_type, "embedding": embedding,
            "source_session_id": source_session_id}).execute().data[0]
    
    async def recall(self, workspace_id: str, query: str, limit: int = 5) -> list:
        embedding = self.embedder.encode(query).tolist()
        return db.client.rpc("match_memories", {
            "query_embedding": embedding, "p_workspace_id": workspace_id,
            "match_count": limit, "match_threshold": 0.7}).execute().data or []
    
    async def forget(self, memory_id: str) -> bool:
        db.client.table("memories").delete().eq("id", memory_id).execute()
        return True

memory_engine = MemoryEngine()
```

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/rules_engine.py`

```python
"""Rules engine: Configurable governance rules per workspace."""

from app.db.supabase_client import db

class RulesEngine:
    async def evaluate(self, workspace_id: str, context: dict) -> list:
        rules = db.client.table("rules").select("*") \
            .eq("workspace_id", workspace_id).eq("enabled", True) \
            .order("priority", desc=True).execute()
        
        triggered = []
        for rule in (rules.data or []):
            if self._matches(rule["condition"], context):
                triggered.append({"rule": rule, "action": rule["action"]})
        return triggered
    
    def _matches(self, condition: dict, context: dict) -> bool:
        for key, expected in condition.items():
            if context.get(key) != expected:
                return False
        return True

rules_engine = RulesEngine()
```

SQL function for memory search:
```sql
CREATE OR REPLACE FUNCTION match_memories(
    query_embedding vector(384), p_workspace_id UUID,
    match_count INT, match_threshold FLOAT
) RETURNS TABLE (id UUID, content TEXT, memory_type TEXT, similarity FLOAT) AS $$
    SELECT id, content, memory_type,
           1 - (embedding <=> query_embedding) AS similarity
    FROM memories WHERE workspace_id = p_workspace_id
      AND 1 - (embedding <=> query_embedding) > match_threshold
    ORDER BY embedding <=> query_embedding LIMIT match_count;
$$ LANGUAGE SQL;
```

### Acceptance Criteria
- [ ] Memories stored with embeddings and retrieved semantically
- [ ] Rules engine evaluates conditions against context
- [ ] Memory recall returns relevant past knowledge

---

## PHASES 30-32: Skills, Tasks, Checkpoints
**Category**: Platform | **Duration**: 6 days | **Depends on**: Phase 3
**✅ STATUS: COMPLETE** — Already implemented in skill_loader.py, tasks API, checkpoints API

### Phase 30: Skills System
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/skills_service.py`
- CRUD for skills (install, uninstall, list, execute)
- Skills stored in `skills` table with JSONB manifest
- API: `POST /api/v1/skills/install`, `GET /api/v1/skills`, `POST /api/v1/skills/{id}/execute`

### Phase 31: Task Management
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/task_service.py`
- Task CRUD with status transitions (pending → in_progress → completed/blocked)
- Assignment to users, due dates, session linking
- API: `POST /api/v1/tasks`, `PATCH /api/v1/tasks/{id}`, `GET /api/v1/tasks`

### Phase 32: Checkpoints & Recovery
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/checkpoint_service.py`
- Manual + auto checkpoints (pre-decision, periodic)
- Full state snapshot stored as JSONB
- Git ref linking for code state
- Recovery: restore session + workspace state from checkpoint
- API: `POST /api/v1/checkpoints`, `POST /api/v1/checkpoints/{id}/restore`

### Acceptance Criteria (30-32)
- [ ] Skills installable from URL/manifest, executable in sandbox
- [ ] Tasks fully lifecycle-managed with assignments
- [ ] Checkpoints capture full state, restorable

---

## PHASES 33-34: Collaboration
**Category**: Collab | **Duration**: 5 days | **Depends on**: Phase 3
**✅ STATUS: COMPLETE** — Already implemented in collaboration/ + warroom API

### Phase 33: Real-time Presence (Supabase Realtime)
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/presence.py`

> **📌 Architecture Decision (2026-04-09):** Supabase Realtime is **intentionally kept** for this phase. It is one of Supabase's strongest features and replacing it with GCP Pub/Sub would require building WebSocket infrastructure from scratch. The hybrid architecture (GCP for compute, Supabase for data+realtime) is the correct choice here.

- Use Supabase Realtime channels for WebSocket presence
- Track who's online, what file they're editing, cursor position
- Frontend: show presence indicators in dashboard

Frontend subscription example:
```typescript
import { createClient } from '@supabase/supabase-js';
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Subscribe to presence channel
const channel = supabase.channel(`workspace:${workspaceId}`);
channel
  .on('presence', { event: 'sync' }, () => {
    const state = channel.presenceState();
    setOnlineUsers(Object.values(state).flat());
  })
  .subscribe(async (status) => {
    if (status === 'SUBSCRIBED') {
      await channel.track({ user_id: userId, file: currentFile });
    }
  });
```

### Phase 34: War Room — Incident Management
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/war_room.py`
- Create incident → auto-freeze workspace → gather team → resolve → post-mortem
- Sentinel integration: high-severity risk signals auto-create war rooms
- Timeline of incident actions stored in Chronos
- API: `POST /api/v1/warroom/create`, `POST /api/v1/warroom/{id}/resolve`

### Acceptance Criteria (33-34)
- [ ] Real-time presence via Supabase Realtime
- [ ] War room creation from Sentinel alerts
- [ ] Incident lifecycle: create → investigate → resolve → post-mortem

---

## PHASES 35-38: Code Review, Audit, Security
**Category**: Enterprise | **Duration**: 7 days
**✅ STATUS: COMPLETE** — Phase 35: diff_review.py, Phase 36: audit_store.py, Phase 37: agent_identity.py, Phase 38: vault.py

### Phase 35: Diff Review System
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/diff_review.py`
- Parse git diffs, send to council for review
- Per-file and per-hunk risk assessment via Sentinel
- API: `POST /api/v1/review/diff`

### Phase 36: Audit Trail & Compliance
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/audit_service.py`
- Every action logged to `audit_log` table (append-only)
- Queryable by action, actor, resource, time range
- Export to CSV/JSON for compliance
- API: `GET /api/v1/audit`, `GET /api/v1/audit/export`

### Phase 37: Agent Identity & Zero Trust
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/agent_identity.py`
- Each AI agent gets a unique identity with scoped permissions
- Agents cannot impersonate users or escalate privileges
- All agent actions tracked with agent_id in audit log

### Phase 38: Secrets Vault
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/secrets_vault.py`
- Encrypted storage for API keys (user LLM keys stored encrypted)
- GCP Secret Manager integration for production
- Local: AES-256 encrypted in Supabase
- API: `POST /api/v1/secrets`, `GET /api/v1/secrets/{name}`

### Acceptance Criteria (35-38)
- [ ] Git diffs reviewed by council with per-hunk risk scores
- [ ] Audit log captures every action, exportable
- [ ] Agent identities scoped and tracked
- [ ] Secrets encrypted at rest, accessible only to authorized agents

---

## PHASES 39-42: Integrations & Agents
**Category**: Integration/Agents | **Duration**: 8 days
**✅ STATUS: COMPLETE** — Phase 39: chatops_service.py, Phase 40: mcp_server.py, Phase 41: agents/, Phase 42: commands_engine.py

### Phase 39: ChatOps Integration
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/chatops.py`
- Slack/Discord webhooks for notifications
- Configurable alerts: session events, proposal status, risk signals
- API: `POST /api/v1/integrations/webhook`

### Phase 40: MCP Server & Tools
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/mcp_server.py`
- Expose AEGION as an MCP server (Model Context Protocol)
- Tools: `consult_council`, `create_proposal`, `get_timeline`, `search_knowledge`
- Enables IDE integration (VS Code, Cursor, etc.)

### Phase 41: Terminal & Browser Agents
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/agents/terminal_agent.py`
- Execute terminal commands in sandbox with governance approval
- Browser agent: navigate, extract, screenshot (Playwright)
- All actions go through Archon tier check

### Phase 42: AI Commands Engine
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/commands_engine.py`
- Natural language command processing
- Map commands to AEGION operations (e.g., "review my PR" → diff review)
- Fallback to council for ambiguous commands
- API: `POST /api/v1/commands/execute`

### Acceptance Criteria (39-42)
- [ ] Webhook notifications for key events
- [ ] MCP server exposing AEGION tools to IDEs
- [ ] Terminal/browser agents with governance gating
- [ ] Natural language commands mapped to operations

---

## PHASES 43-45: Intelligence
**Category**: Intelligence | **Duration**: 6 days
**✅ STATUS: COMPLETE** — Phase 43: rejection_learning.py, Phase 44: decision_pipeline.py, Phase 45: reasoning_chain.py

### Phase 43: Rejection Learning System
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/rejection_learning.py`
- When proposals are rejected, store the rejection reason + context
- Feed rejection patterns back to councils to improve future proposals
- API: `GET /api/v1/learning/rejections`

### Phase 44: Decision Pipelines
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/decision_pipeline.py`
- Multi-step decision workflows: analyze → debate → review → score → recommend
- Configurable pipeline stages per decision type
- Pipeline templates stored in rules table

### Phase 45: Reasoning Chains
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/reasoning_chain.py`
- Track the step-by-step reasoning of AI decisions
- Store reasoning chains alongside decisions for explainability
- Visualizable in frontend

### Acceptance Criteria (43-45)
- [ ] Rejected proposals analyzed for pattern learning
- [ ] Decision pipelines configurable with multiple stages
- [ ] Reasoning chains stored and queryable

---

## PHASES 46-51: Advanced ACK Enhancements
**Category**: ACK Advanced | **Duration**: 12 days
**✅ STATUS: PARTIAL** — Phase 46 (constitution.py) complete. Phases 47-51 pending.

### Phase 46: Constitutional AI Layer
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/constitution.py`
```python
"""Machine-readable governance constitution in YAML."""

import yaml

class ConstitutionalAI:
    def __init__(self, constitution_path: str = "aegion_constitution.yaml"):
        self.rules = self._load(constitution_path)
    
    def _load(self, path: str) -> dict:
        try:
            with open(path) as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return self._default_constitution()
    
    def _default_constitution(self) -> dict:
        return {
            "hard_constraints": [
                {"rule": "no_ai_memory_write", "description": "AI cannot write to Chronos directly"},
                {"rule": "no_ai_approval", "description": "AI cannot approve decisions"},
                {"rule": "human_override", "description": "Humans can override any AI decision"},
                {"rule": "audit_everything", "description": "All actions must be logged"}
            ],
            "soft_constraints": [
                {"rule": "prefer_cheaper_models", "threshold": 0.85},
                {"rule": "require_evidence", "min_citations": 1},
                {"rule": "preserve_dissent", "description": "Never suppress minority views"}
            ]
        }
    
    def validate(self, action: dict) -> tuple[bool, list[str]]:
        violations = []
        for constraint in self.rules.get("hard_constraints", []):
            if self._check_violation(action, constraint):
                violations.append(constraint["description"])
        return len(violations) == 0, violations

constitutional_ai = ConstitutionalAI()
```

**File**: `/Users/arpit/Projects/Aegion/aegion_constitution.yaml`
```yaml
# AEGION Governance Constitution v1.0
hard_constraints:
  - rule: no_ai_memory_write
    description: "AI agents cannot write directly to Chronos (immutable memory)"
    enforcement: block
  - rule: no_ai_approval
    description: "AI cannot approve T2/T3 decisions without human authorization"
    enforcement: block
  - rule: human_override_always
    description: "Human decisions supersede all AI recommendations"
    enforcement: enforce
  - rule: audit_all_actions
    description: "Every action must be logged in the audit trail"
    enforcement: enforce
  - rule: local_inference_for_secrets
    description: "Code containing secrets must only be analyzed by local models"
    enforcement: block

soft_constraints:
  - rule: prefer_cheaper_models
    description: "Use cheapest model that meets quality threshold"
    threshold: 0.85
  - rule: require_evidence
    description: "AI claims must cite evidence from knowledge graph"
    min_citations: 1
  - rule: preserve_dissent
    description: "Never suppress contrarian views with valid evidence"
  - rule: three_round_limit
    description: "Debates stop after 3 rounds maximum"
```

### Phase 47: Cognitive Reflector
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/reflector.py`
- Monitors council debates for pathological patterns in real-time
- Detects: groupthink, hallucination cascades, authority bias, circular reasoning
- Intervention: pause debate, inject fresh perspective, flag for human review

### Phase 48: Red Team Layer
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/red_team.py`
- Adversarial validation of council outputs before they reach Archon
- Tests: prompt injection resistance, hallucination verification, logic bombs
- Red team runs on cheapest model to minimize cost

### Phase 49: Temporal Council Memory
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/temporal_memory.py`
- Provides historical context: "Last time we debated X, the outcome was Y"
- Tracks debate outcome → actual result correlation
- Feeds outcome data back to improve future debates

### Phase 50: Cross-Council Orchestration
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/orchestrator.py`
- Councils can invoke sub-councils for specialized tasks
- Example: Parent Council → spawns Security Sub-Council + Cost Sub-Council
- Results aggregated by parent council for final synthesis

### Phase 51: Council Analytics Engine
**File**: `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/analytics.py`
- Track: hallucination rate, dissent preservation, decision regret, model accuracy
- Leaderboard: which models perform best for which task types
- Dashboard data for frontend visualization

### Acceptance Criteria (46-51)
- [ ] Constitution YAML loaded and enforced on every action
- [ ] Cognitive reflector detects groupthink and intervenes
- [ ] Red team validates outputs before governance layer
- [ ] Temporal memory provides historical context to debates
- [ ] Cross-council orchestration spawns sub-councils
- [ ] Analytics dashboard data available via API

---

## PHASES 52-56: VS Code Extension
**Category**: Extension | **Duration**: 15 days total

### Phase 52: Extension Auth & Connection (3 days)
**File**: `aegion-extension/src/auth/firebase_auth_provider.ts`

> **📌 Architecture Decision (2026-04-09):** Use **Firebase Auth** tokens in the VS Code extension (not Supabase Auth). The backend `get_current_user()` validates Firebase ID tokens. The extension must send a Firebase ID token in the `Authorization: Bearer <token>` header.

- Login flow: Firebase sign-in (email/password or Google OAuth) → store Firebase ID token
- Auto-refresh: Firebase tokens expire after 1 hour — use `user.getIdToken(true)` to force-refresh
- Status bar shows connection state (connected/disconnected/error)

```typescript
// aegion-extension/src/auth/firebase_auth_provider.ts
import * as vscode from 'vscode';
import { initializeApp } from 'firebase/app';
import { getAuth, signInWithEmailAndPassword, onAuthStateChanged, User } from 'firebase/auth';

export class FirebaseAuthProvider {
  private auth = getAuth(initializeApp(FIREBASE_CONFIG));
  private currentUser: User | null = null;

  async getToken(): Promise<string | null> {
    if (!this.currentUser) return null;
    // Force refresh if token is near expiry
    return await this.currentUser.getIdToken(false);
  }

  async login(email: string, password: string): Promise<void> {
    const cred = await signInWithEmailAndPassword(this.auth, email, password);
    this.currentUser = cred.user;
    vscode.window.showInformationMessage(`Aegion: Signed in as ${cred.user.email}`);
  }

  isAuthenticated(): boolean {
    return this.currentUser !== null;
  }
}
```

**Files to modify**:
- `aegion-extension/src/services/api_client.ts` — attach Firebase ID token to request headers
- `aegion-extension/src/services/identity_manager.ts` — store/retrieve Firebase user session
- `aegion-extension/src/extension.ts` — initialize Firebase auth on activation

### Phase 53: TreeView Providers (3 days)
**File**: `/Users/arpit/Projects/Aegion/aegion-extension/src/views/`

Create these TreeView providers:
- `session_tree.ts` — Active sessions, artifacts, checkpoints
- `timeline_tree.ts` — Recent events from Chronos
- `proposal_tree.ts` — Pending proposals with approve/reject actions
- `risk_tree.ts` — Active risk signals from Sentinel
- `cost_tree.ts` — Cost summary and cache stats

Each provider implements `vscode.TreeDataProvider<T>` with auto-refresh.

### Phase 54: Ghost Text Provider (3 days)
**File**: `/Users/arpit/Projects/Aegion/aegion-extension/src/providers/ghost_text_provider.ts`

```typescript
import * as vscode from 'vscode';
import { ApiClient } from '../services/api_client';

export class GhostTextProvider implements vscode.InlineCompletionItemProvider {
    constructor(private api: ApiClient) {}
    
    async provideInlineCompletionItems(
        document: vscode.TextDocument,
        position: vscode.Position,
        context: vscode.InlineCompletionContext,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[]> {
        const prefix = document.getText(new vscode.Range(
            Math.max(0, position.line - 20), 0, position.line, position.character));
        const suffix = document.getText(new vscode.Range(
            position.line, position.character,
            Math.min(document.lineCount, position.line + 10), 0));
        
        const result = await this.api.post('/ghost-text/complete', {
            prefix, suffix,
            language: document.languageId,
            file_path: document.fileName
        });
        
        if (result.completion) {
            return [new vscode.InlineCompletionItem(result.completion, 
                new vscode.Range(position, position))];
        }
        return [];
    }
}
```

Register in `extension.ts`:
```typescript
vscode.languages.registerInlineCompletionItemProvider(
    { pattern: '**/*' },
    new GhostTextProvider(apiClient)
);
```

### Phase 55: Command Palette & Webviews (3 days)
**Commands to register**:
- `aegion.council.consult` — Open council consultation panel
- `aegion.proposal.create` — Create proposal from selection
- `aegion.sentinel.scan` — Run security scan on file
- `aegion.timeline.show` — Show timeline webview
- `aegion.session.start` / `aegion.session.end`
- `aegion.settings.configure` — API keys configuration

**Webviews**:
- `CouncilPanel` — Shows council consultation UI with model responses
- `TimelinePanel` — Visual timeline of Chronos events
- `DashboardPanel` — Overview dashboard with charts

### Phase 56: Extension Testing (3 days)
**File**: `/Users/arpit/Projects/Aegion/aegion-extension/src/test/`
- Unit tests for all providers and services
- Integration tests with mock API server
- E2E test: activate → login → start session → consult council → end session

### Acceptance Criteria (52-56)
- [ ] Supabase auth working in VS Code extension
- [ ] All 5 TreeView providers showing live data
- [ ] Ghost Text inline completions appearing on type
- [ ] All commands registered and functional
- [ ] Webviews rendering with proper styling
- [ ] Tests passing with >80% coverage

---

## PHASES 57-68: Next.js Frontend Dashboard
**Category**: Frontend | **Duration**: 25 days total

### Phase 57: Project Setup & Design System (3 days)
**Base path**: `aegion-frontend/`
- Next.js App Router (already bootstrapped)
- Design system: CSS variables, dark theme, glassmorphism cards
- Components: Button, Card, Badge, Modal, Toast, Sidebar, TopNav
- **Supabase client** initialization (for PostgreSQL queries via PostgREST + Realtime)
- **Firebase Auth context** provider (see Phase 4 — `lib/auth-context.tsx`)

> **📌 Note:** Two clients are initialized: `supabase` (for data) and Firebase `auth` (for user identity). They work independently — Supabase does not handle authentication in AEGION.

### Phase 58: Authentication Pages (2 days)
- `/app/login/page.tsx` — Email/password + Google OAuth via **Firebase Auth** (not Supabase)
- `/app/signup/page.tsx` — Registration with workspace creation (creates Supabase `users` row after Firebase signup)
- `/app/auth/callback/page.tsx` — Firebase OAuth redirect callback handler
- Middleware: protected routes redirect to login if no Firebase user

> **📌 Note:** All auth is Firebase. After successful Firebase login, the frontend:
> 1. Gets the Firebase ID token: `await user.getIdToken()`
> 2. Sends it as `Authorization: Bearer <token>` to the FastAPI backend
> 3. Backend validates the token via `get_current_user()` in `security.py`
> Supabase is never used for authentication.

### Phase 59: Dashboard — Overview (3 days)
- `/app/dashboard/page.tsx`
- Widgets: Active sessions, Recent decisions, Cost summary, Risk signals
- Charts: Cost over time (recharts), Decision distribution, Cache hit rate
- Real-time updates via **Supabase Realtime** subscriptions (intentionally kept — see Phase 33 note)

### Phase 60: Timeline Page (2 days)
- `/app/dashboard/timeline/page.tsx`
- Infinite scroll event list from Chronos
- Filter by: entity type, actor, date range
- Event detail drawer with full payload
- Decision lineage graph visualization (react-flow)

### Phase 61: Council Console (3 days)
- `/app/dashboard/council/page.tsx`
- Chat-like interface for council consultations
- Show individual model responses, consensus score, dissenting views
- Cost tracking per consultation
- Council type selector (child/parent/sentinel)

### Phase 62: Proposals & Decisions (2 days)
- `/app/dashboard/proposals/page.tsx`
- Table: all proposals with status, tier, council result
- Detail page: full proposal, council review, approve/reject buttons
- Decision history with lineage links

### Phase 63: Settings & API Keys (2 days)
- `/app/dashboard/settings/page.tsx`
- Tabs: Profile, API Keys, Workspace, Integrations, Rules
- API key form: OpenAI, Anthropic, DeepSeek, Google, Ollama, Custom
- Keys encrypted before storage
- Workspace settings: freeze toggle, governance tier thresholds

### Phase 64: Knowledge Graph Visualizer (3 days)
- `/app/dashboard/knowledge/page.tsx`
- Interactive network graph using react-force-graph
- Node types: concepts, decisions, ADRs (color-coded)
- Click node to see details and connections
- Search with semantic highlighting

### Phase 65: ADR Management (2 days)
- `/app/dashboard/adrs/page.tsx`
- ADR list with status badges (proposed/accepted/superseded/deprecated)
- Create ADR form with markdown editor
- View drift violations flagged by Sentinel

### Phase 66: Cost Dashboard (1 day)
- `/app/dashboard/cost/page.tsx`
- Budget burn chart, provider breakdown, cache savings
- Model leaderboard (accuracy vs cost)
- Alerts when approaching budget thresholds

### Phase 67: Memory & Skills (2 days)
- `/app/dashboard/memory/page.tsx` — Stored memories, search, forget
- `/app/dashboard/skills/page.tsx` — Installed skills, marketplace, execute

### Phase 68: Responsive & Polish (2 days)
- Mobile responsive layouts for all pages
- Micro-animations (framer-motion): page transitions, card hovers, loading states
- Error boundaries and fallback UIs
- SEO: titles, descriptions, OG tags

### Acceptance Criteria (57-68)
- [ ] All pages rendering with dark theme and glassmorphism
- [ ] Auth flow complete (login, signup, OAuth, logout)
- [ ] Dashboard showing real-time data from Supabase
- [ ] Council console working with streaming responses
- [ ] Knowledge graph interactive and searchable
- [ ] Mobile responsive on all breakpoints
- [ ] Lighthouse score > 90 (performance, accessibility)

---

## PHASES 69-71: Testing Suite
**Category**: Testing | **Duration**: 8 days total

### Phase 69: Backend Unit Tests (3 days)
**Path**: `/Users/arpit/Projects/Aegion/aegion-backend/tests/`

```
tests/
├── unit/
│   ├── test_council_engine.py      # Council orchestration
│   ├── test_model_router.py        # Provider routing
│   ├── test_cascade.py             # FrugalGPT cascade
│   ├── test_semantic_cache.py      # Cache hit/miss/TTL
│   ├── test_peer_review.py         # 3-stage review pipeline
│   ├── test_debate.py              # Anti-sycophancy debate
│   ├── test_rubric.py              # Rubric scoring
│   ├── test_archon.py              # Tier routing
│   ├── test_sentinel.py            # Risk scoring
│   ├── test_chronos.py             # Timeline events
│   ├── test_session_manager.py     # Session lifecycle
│   └── test_sandbox.py             # Code execution
├── integration/
│   ├── test_council_api.py         # Full council API flow
│   ├── test_governance_flow.py     # Proposal → review → decision
│   └── test_supabase.py            # Database operations
└── conftest.py                     # Fixtures, mocks, test DB
```

**Run**: `cd aegion-backend && pytest tests/ -v --cov=app --cov-report=term-missing`

### Phase 70: Frontend Tests (2 days)
- Component tests: Jest + React Testing Library
- Page tests: each page renders without errors
- Auth flow: login → dashboard redirect
- API mocking: MSW (Mock Service Worker)

**Run**: `cd aegion-frontend && npm test -- --coverage`

### Phase 71: E2E & Load Tests (3 days)
- E2E: Playwright tests
  - Login → Start Session → Consult Council → View Timeline → End Session
  - Create Proposal → Council Review → Approve → Check Decision
- Load: Locust tests
  - 100 concurrent council consultations
  - Cache hit rate validation under load
  - Session creation/closure throughput

**Run**: `cd aegion-backend && locust -f tests/load/locustfile.py`

### Acceptance Criteria (69-71)
- [ ] Backend unit tests: >80% coverage
- [ ] All API endpoints have integration tests
- [ ] Frontend components tested with mocked data
- [ ] E2E flows pass: council, governance, session
- [ ] Load test: API handles 100+ concurrent requests

---

## PHASES 72-74: DevOps & Infrastructure
**Category**: DevOps | **Duration**: 6 days total

### Phase 72: Docker & Local Dev (2 days)
> **Note**: Phase 2 already created a production Dockerfile for Cloud Run. This simplified version is for local development with `docker-compose`.

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/Dockerfile`
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-dev
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### [NEW] `/Users/arpit/Projects/Aegion/docker-compose.yml`
```yaml
version: '3.8'
services:
  backend:
    build: ./aegion-backend
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [redis]
  frontend:
    build: ./aegion-frontend
    ports: ["3000:3000"]
    env_file: .env
  redis:
    image: redis:alpine
    ports: ["6379:6379"]
```

### Phase 73: GCP Cloud Run Deployment (CI/CD)

> **✅ THIS PHASE IS COMPLETE — DONE AS PART OF PHASE 2 (2026-04-09)**
>
> Phase 73 was originally planned separately but was implemented early as part of Phase 2 with significant improvements over the original design:
>
> | Original Plan | What Was Actually Built |
> |---|---|
> | JSON service account key in `GCP_CREDENTIALS` secret | **Workload Identity Federation** (keyless — no JSON key stored anywhere) |
> | `gcr.io` Container Registry | **Artifact Registry** (`us-central1-docker.pkg.dev`) — GCR is deprecated |
> | Single deploy job | Separate jobs with gate (CI must pass before deploy) |
> | No health check after deploy | **10-retry health check loop** post-deployment |
> | Frontend on Cloud Run | **Firebase Hosting** (better for static Next.js export) |
>
> **Files already committed:**
> - `.github/workflows/deploy.yml` — full GitHub Actions CD pipeline
> - `cloudbuild.yaml` — GCP Cloud Build alternative pipeline
> - `.env.production.example` — all required env vars documented
>
> **No further action required for this phase.** Proceed to Phase 74 (Monitoring).

### Phase 74: Monitoring & Alerting (2 days)
- GCP Cloud Monitoring dashboards: request latency, error rate, CPU/memory
- Structured logging: JSON format with correlation IDs
- Alert policies: error rate >5%, latency >2s, memory >80%
- Health check endpoint: `GET /api/v1/health`

### Acceptance Criteria (72-74)
- [ ] `docker-compose up` starts entire stack locally
- [ ] CI/CD deploys to Cloud Run on push to main
- [ ] Health checks passing on production
- [ ] Monitoring dashboards showing live metrics

---

## PHASE 75: Documentation, VS Code Marketplace & Launch
**Category**: Launch | **Duration**: 5 days

### 75a: Documentation (2 days)
- `docs/API_REFERENCE.md` — All endpoints with request/response examples
- `docs/ARCHITECTURE.md` — System architecture with diagrams
- `docs/DEVELOPER_GUIDE.md` — Setup, development, testing instructions
- `docs/GOVERNANCE_GUIDE.md` — How tiers, councils, and decisions work
- `docs/COST_GUIDE.md` — How to optimize costs, configure models, monitor spend
- README.md update with badges, quick start, screenshots

### 75b: VS Code Marketplace (1 day)
- Update `package.json` with publisher, icon, categories
- Create CHANGELOG.md
- Screenshots and demo GIF for marketplace listing
- `vsce package` and `vsce publish`

### 75c: Launch Checklist (2 days)
- [ ] All 70+ phases implemented and tested
- [ ] Backend deployed to **GCP Cloud Run** (Phase 2 infra complete, backend code pending)
- [ ] Frontend deployed to **Firebase Hosting** (not Cloud Run — static Next.js export)
- [ ] VS Code extension published to marketplace
- [ ] **Supabase** project created with all tables, pgvector, and RLS policies (Phase 3)
- [ ] Firebase Auth hardened (Phase 4 — token revocation, no hardcoded secrets)
- [ ] API keys configured for at least 2 LLM providers
- [ ] All secrets in GCP Secret Manager (not plaintext env vars)
- [ ] Health checks passing on Cloud Run
- [ ] Documentation complete
- [ ] Demo video recorded showing end-to-end flow

### Final Acceptance Criteria
- [ ] `docker-compose up` → fully working local environment (port 8080)
- [ ] Cloud Run backend → public URL accessible, health check returning `{"status":"healthy"}`
- [ ] Firebase Hosting frontend → accessible, login flow working end-to-end
- [ ] VS Code extension → installable from marketplace
- [ ] Full council consultation round-trip: <5s latency
- [ ] Cost per council consultation: <$0.01 (with cache)
- [ ] All tests passing with >80% coverage

---

> **📌 Architecture Summary (Updated 2026-04-09)**
>
> | Component | Service | Reason |
> |---|---|---|
> | Backend API | GCP Cloud Run | Serverless, $300 credits, autoscaling |
> | Frontend | Firebase Hosting | Free CDN, SPA routing, Next.js static export |
> | Database | Supabase (PostgreSQL + pgvector) | Free tier, Realtime, best pgvector DX |
> | Authentication | Firebase Auth | Already in codebase, tokens validated by backend |
> | Real-time | Supabase Realtime | Best-in-class, no infrastructure to manage |
> | Secrets | GCP Secret Manager | Native GCP, Cloud Run injection |
> | Docker Images | GCP Artifact Registry | GCR deprecated, Artifact Registry is the standard |
> | CI/CD | GitHub Actions + WIF | Keyless auth, no stored JSON keys |

---

## PHASE 76: Prompt Gateway & Intent Clarification Layer
**Category**: Cost | **Duration**: 3 days | **Depends on**: Phase 9, 12

### Objective
Use a cheap model (Gemini Flash / GPT-4o-mini) to preprocess user queries before they reach the AI Council. Detect ambiguity, ask clarifying questions, generate an optimized prompt, and show it to the user for approval. Maintains short session memory for context continuity.

> **Industry validation**: This pattern (called "Prompt Gateway" or "Intent Clarification Layer") is used by Amazon Bedrock, Microsoft Copilot, and the FrugalGPT framework (Stanford). Typical savings: **40-70%** of input tokens.

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/prompt_gateway.py`

```python
"""Prompt Gateway: Cheap model preprocesses queries before council."""

from .model_router import ModelRouter
from .types import ModelResponse
from app.db.supabase_client import db
from collections import deque

class PromptGateway:
    GATEWAY_MODEL = ("google", "gemini-2.0-flash")  # ~$0.00001/query
    MAX_SESSION_MEMORY = 5  # Keep last 5 turns for context
    
    def __init__(self, model_router: ModelRouter):
        self.router = model_router
        self._session_memory: dict[str, deque] = {}  # workspace_id -> deque
    
    def _get_memory(self, workspace_id: str) -> deque:
        if workspace_id not in self._session_memory:
            self._session_memory[workspace_id] = deque(maxlen=self.MAX_SESSION_MEMORY)
        return self._session_memory[workspace_id]
    
    async def process(self, workspace_id: str, raw_query: str) -> dict:
        """Analyze, clarify, and optimize user query before council."""
        memory = self._get_memory(workspace_id)
        context = "\n".join(f"- {m['role']}: {m['content'][:200]}" 
                           for m in memory) if memory else "No previous context."
        
        analysis_prompt = f"""You are a Prompt Gateway for an AI Council system.
Analyze the user's query and determine:
1. INTENT: What is the user actually asking? (code_review, architecture, debug, explain, generate, security, general)
2. AMBIGUITY_SCORE: 0.0 (crystal clear) to 1.0 (completely unclear)
3. MISSING_INFO: What information is missing that would help the council?
4. CLARIFYING_QUESTIONS: If ambiguity > 0.5, list 1-3 specific questions to ask
5. OPTIMIZED_PROMPT: Rewrite the query to be specific, structured, and token-efficient
6. COMPLEXITY: simple | medium | complex
7. ESTIMATED_COUNCIL_TYPE: child | parent | sentinel

Previous conversation context:
{context}

User's raw query: "{raw_query}"

Respond in JSON format only."""

        provider, model = self.GATEWAY_MODEL
        result = await self.router.providers[provider].generate(analysis_prompt, model)
        
        import json
        try:
            analysis = json.loads(result.response)
        except json.JSONDecodeError:
            analysis = {
                "intent": "general", "ambiguity_score": 0.0,
                "missing_info": [], "clarifying_questions": [],
                "optimized_prompt": raw_query, "complexity": "medium",
                "estimated_council_type": "child"
            }
        
        # Store in session memory
        memory.append({"role": "user", "content": raw_query})
        
        # Track gateway cost
        await db.client.table("cost_tracking").insert({
            "workspace_id": workspace_id, "provider": provider,
            "model": model, "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out, "cost_usd": result.cost_usd,
            "request_type": "prompt_gateway"
        }).execute()
        
        return {
            "raw_query": raw_query,
            "analysis": analysis,
            "needs_clarification": analysis.get("ambiguity_score", 0) > 0.5,
            "optimized_prompt": analysis.get("optimized_prompt", raw_query),
            "suggested_council_type": analysis.get("estimated_council_type", "child"),
            "complexity": analysis.get("complexity", "medium"),
            "gateway_cost_usd": result.cost_usd,
            "token_savings_estimate": max(0, len(raw_query.split()) - 
                len(analysis.get("optimized_prompt", raw_query).split()))
        }
    
    async def submit_approved_prompt(self, workspace_id: str, 
                                       approved_prompt: str,
                                       user_edits: str = None) -> str:
        """User approved/edited the optimized prompt. Store and return final."""
        final = user_edits if user_edits else approved_prompt
        memory = self._get_memory(workspace_id)
        memory.append({"role": "assistant", "content": f"[Optimized]: {final[:200]}"})
        return final

prompt_gateway = PromptGateway(ModelRouter())
```

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/api/v1/gateway.py`

```python
"""Prompt Gateway API endpoints."""

from fastapi import APIRouter, Depends
from app.auth.supabase_auth import get_current_user
from app.services.council_kernel.prompt_gateway import prompt_gateway
from pydantic import BaseModel

router = APIRouter(prefix="/gateway", tags=["Prompt Gateway"])

class GatewayRequest(BaseModel):
    query: str

class ApproveRequest(BaseModel):
    approved_prompt: str
    user_edits: str = None

@router.post("/analyze")
async def analyze_query(req: GatewayRequest, user: dict = Depends(get_current_user)):
    """Analyze and optimize a user query before sending to council."""
    return await prompt_gateway.process(user["workspace_id"], req.query)

@router.post("/approve")
async def approve_prompt(req: ApproveRequest, user: dict = Depends(get_current_user)):
    """User approves or edits the optimized prompt."""
    final = await prompt_gateway.submit_approved_prompt(
        user["workspace_id"], req.approved_prompt, req.user_edits)
    return {"final_prompt": final, "ready_for_council": True}
```

### Integration Point

The Prompt Gateway hooks into the main consultation pipeline. When integrated, `CouncilEngine.consult()` should call the gateway first:

```python
# In CouncilEngine.consult() — add at the start of the method:
async def consult(self, workspace_id: str, query: str, ...):
    # Step 0: Run through Prompt Gateway (if enabled in settings)
    settings = await model_settings.get_settings(workspace_id)
    if settings.get("settings", {}).get("gateway", {}).get("enabled", True):
        gateway_result = await prompt_gateway.process(workspace_id, query)
        if gateway_result["needs_clarification"]:
            return {"status": "needs_clarification",
                    "questions": gateway_result["analysis"]["clarifying_questions"],
                    "optimized_prompt": gateway_result["optimized_prompt"]}
        query = gateway_result["optimized_prompt"]  # Use optimized version
    
    # Step 1: Context pruning (Phase 79)
    # Step 2: RAG enrichment (Phase 83)
    # Step 3: Adaptive council sizing (Phase 77)
    # Step 4: Token budgeting (Phase 78)
    # Step 5: Cache check (Phase 11)
    # Step 6: Execute council debate...
```

> This creates the full cost-optimization pipeline: **Gateway → Prune → RAG → Size → Budget → Cache → Execute**

### Acceptance Criteria
- [ ] Gateway analyzes queries using Flash model (~$0.00001/query)
- [ ] Ambiguity score > 0.5 triggers clarifying questions
- [ ] Optimized prompt shown to user for approval/editing
- [ ] Session memory (last 5 turns) provides context continuity
- [ ] Gateway cost tracked separately in `cost_tracking` table
- [ ] Token savings estimate provided per query
- [ ] Gateway integrated into `CouncilEngine.consult()` pipeline

---

## PHASE 77: Adaptive Council Size & Smart Routing
**Category**: Cost | **Duration**: 2 days | **Depends on**: Phase 76, 8

### Objective
Not every query needs the full 3-4 model council. Use the Gateway's complexity classification to dynamically size the council: Simple → 1 model, Medium → 2 models, Complex → full council. **Savings: 40-60%**.

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/adaptive_council.py`

```python
"""Adaptive Council: Right-size model count based on query complexity."""

from app.services.council_kernel.model_router import ModelRouter

class AdaptiveCouncil:
    # Maps complexity → number of models and council strategy
    SIZE_POLICIES = {
        "simple": {
            "model_count": 1,
            "council_type": "child",
            "strategy": "cascade",  # Single model via cascade (cheapest first)
            "max_rounds": 1,
            "description": "Single model, direct answer"
        },
        "medium": {
            "model_count": 2,
            "council_type": "child",
            "strategy": "peer_review",  # 2 models cross-check
            "max_rounds": 1,
            "description": "Two models with peer review"
        },
        "complex": {
            "model_count": 3,
            "council_type": "parent",
            "strategy": "full_debate",  # Full debate + persona + evidence
            "max_rounds": 3,
            "description": "Full council with debate"
        },
        "critical": {
            "model_count": 4,
            "council_type": "parent",
            "strategy": "full_debate_with_red_team",
            "max_rounds": 3,
            "description": "Full council + red team validation"
        }
    }
    
    def get_council_config(self, complexity: str, 
                           user_override: dict = None) -> dict:
        """Return council configuration for the given complexity."""
        config = self.SIZE_POLICIES.get(complexity, self.SIZE_POLICIES["medium"]).copy()
        
        # Allow user override from Model Settings
        if user_override:
            config.update({k: v for k, v in user_override.items() if v is not None})
        
        return config
    
    def select_models(self, model_router: ModelRouter, 
                      count: int, prefer_cheap: bool = True) -> list[tuple[str, str]]:
        """Select N models from available providers, cheapest first if preferred."""
        available = []
        for provider_name, provider in model_router.providers.items():
            if hasattr(provider, 'models'):
                for model in provider.models:
                    available.append((provider_name, model))
        
        if prefer_cheap:
            # Sort by cost tier (cheapest first)
            cost_order = ["deepseek", "google", "ollama", "anthropic", "openai"]
            available.sort(key=lambda x: cost_order.index(x[0]) 
                          if x[0] in cost_order else 99)
        
        return available[:count]

adaptive_council = AdaptiveCouncil()
```

### Acceptance Criteria
- [ ] Simple queries use 1 model (cascade only), no debate
- [ ] Medium queries use 2 models with peer review
- [ ] Complex queries use full 3-4 model council with debate
- [ ] User can override via Model Settings
- [ ] Cost reduction of 40-60% on average query mix

---

## PHASE 78: Output Token Budgeting & Dynamic Limits
**Category**: Cost | **Duration**: 1 day | **Depends on**: Phase 76

### Objective
Dynamically set `max_tokens` per LLM call based on query complexity and intent. Output tokens cost 2-3x more than input tokens. **Savings: 30-50%**.

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/token_budget.py`

```python
"""Token budget manager: Dynamic output limits based on query type."""

class TokenBudgetManager:
    # Tokens budgets by intent + complexity
    BUDGETS = {
        ("debug", "simple"): {"max_tokens": 300, "temperature": 0.3},
        ("debug", "medium"): {"max_tokens": 800, "temperature": 0.3},
        ("debug", "complex"): {"max_tokens": 1500, "temperature": 0.4},
        ("explain", "simple"): {"max_tokens": 500, "temperature": 0.5},
        ("explain", "medium"): {"max_tokens": 1000, "temperature": 0.5},
        ("explain", "complex"): {"max_tokens": 2000, "temperature": 0.5},
        ("generate", "simple"): {"max_tokens": 500, "temperature": 0.7},
        ("generate", "medium"): {"max_tokens": 1500, "temperature": 0.7},
        ("generate", "complex"): {"max_tokens": 3000, "temperature": 0.7},
        ("code_review", "simple"): {"max_tokens": 400, "temperature": 0.2},
        ("code_review", "medium"): {"max_tokens": 1000, "temperature": 0.2},
        ("code_review", "complex"): {"max_tokens": 2000, "temperature": 0.3},
        ("architecture", "simple"): {"max_tokens": 800, "temperature": 0.5},
        ("architecture", "medium"): {"max_tokens": 2000, "temperature": 0.5},
        ("architecture", "complex"): {"max_tokens": 4000, "temperature": 0.5},
        ("security", "simple"): {"max_tokens": 500, "temperature": 0.2},
        ("security", "medium"): {"max_tokens": 1200, "temperature": 0.2},
        ("security", "complex"): {"max_tokens": 2500, "temperature": 0.3},
    }
    DEFAULT = {"max_tokens": 1000, "temperature": 0.5}
    
    def get_budget(self, intent: str, complexity: str, 
                   user_override: int = None) -> dict:
        budget = self.BUDGETS.get((intent, complexity), self.DEFAULT).copy()
        if user_override:
            budget["max_tokens"] = user_override
        return budget
    
    def estimate_cost(self, budget: dict, model: str, provider: str) -> float:
        """Estimate cost for the given token budget."""
        OUTPUT_COSTS = {  # per 1M output tokens
            ("openai", "gpt-4o"): 15.0,
            ("openai", "gpt-4o-mini"): 0.6,
            ("anthropic", "claude-sonnet"): 15.0,
            ("anthropic", "claude-haiku"): 1.25,
            ("google", "gemini-2.0-flash"): 0.3,
            ("google", "gemini-2.5-pro"): 10.0,
            ("deepseek", "deepseek-chat"): 0.28,
        }
        cost_per_m = OUTPUT_COSTS.get((provider, model), 1.0)
        return (budget["max_tokens"] / 1_000_000) * cost_per_m

token_budget = TokenBudgetManager()
```

### Acceptance Criteria
- [ ] Token budgets vary by intent (debug vs architecture = 3x difference)
- [ ] Complexity multiplier applied (simple = 1x, complex = 3-4x)
- [ ] User can override via Model Settings
- [ ] Cost estimate provided before council execution

---

## PHASE 79: Context Window Pruning & History Compression
**Category**: Cost | **Duration**: 2 days | **Depends on**: Phase 29, 76

### Objective
Instead of sending full conversation history to the council, keep last N turns verbatim and compress older turns into a short summary. **Savings: 30-50%** on context-heavy queries.

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/context_pruner.py`

```python
"""Context pruner: Compress conversation history to save tokens."""

from app.services.council_kernel.model_router import ModelRouter

class ContextPruner:
    KEEP_RECENT = 3       # Keep last 3 turns verbatim
    MAX_SUMMARY_TOKENS = 150  # Compressed summary target
    GATEWAY_MODEL = ("google", "gemini-2.0-flash")
    
    async def prune(self, conversation: list[dict], 
                    model_router: ModelRouter = None) -> dict:
        """Prune conversation history, keeping recent + compressing old."""
        if len(conversation) <= self.KEEP_RECENT:
            return {"context": conversation, "pruned": False, "saved_tokens": 0}
        
        recent = conversation[-self.KEEP_RECENT:]
        old = conversation[:-self.KEEP_RECENT]
        
        # Estimate tokens saved
        old_text = " ".join(m.get("content", "") for m in old)
        original_tokens = len(old_text.split())
        
        if model_router and original_tokens > 100:
            summary = await self._ai_summarize(old, model_router)
        else:
            summary = self._heuristic_summarize(old)
        
        pruned_context = [{"role": "system", 
                          "content": f"[Summary of earlier conversation]: {summary}"}]
        pruned_context.extend(recent)
        
        return {
            "context": pruned_context,
            "pruned": True,
            "original_turns": len(conversation),
            "kept_turns": len(recent),
            "compressed_turns": len(old),
            "saved_tokens": max(0, original_tokens - len(summary.split()))
        }
    
    async def _ai_summarize(self, old_turns: list, router: ModelRouter) -> str:
        text = "\n".join(f"{m['role']}: {m['content'][:300]}" for m in old_turns)
        prompt = f"""Summarize this conversation history in under {self.MAX_SUMMARY_TOKENS} words.
Keep: key decisions, code references, unresolved questions.
Drop: greetings, acknowledgements, repeated information.

{text}"""
        provider, model = self.GATEWAY_MODEL
        result = await router.providers[provider].generate(prompt, model)
        return result.response[:600]
    
    def _heuristic_summarize(self, old_turns: list) -> str:
        key_points = []
        for m in old_turns:
            content = m.get("content", "")
            if any(kw in content.lower() for kw in 
                   ["decided", "approved", "rejected", "error", "fix", "implement"]):
                key_points.append(content[:100])
        return " | ".join(key_points[:5]) or "General discussion about the project."

context_pruner = ContextPruner()
```

### Acceptance Criteria
- [ ] Last 3 turns kept verbatim, older turns compressed
- [ ] AI summary (via Flash) for long histories, heuristic for short
- [ ] Token savings tracked and reported
- [ ] Pruned context seamlessly passed to council

---

## PHASE 80: Early Consensus Detection & Round Optimization
**Category**: Cost | **Duration**: 1 day | **Depends on**: Phase 14

### Objective
During multi-round debates, detect consensus early and skip remaining rounds. If all models agree in Round 1, don't run Rounds 2-3. **Savings: 15-30%** on debate-heavy queries.

#### [MODIFY] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/debate.py`

Add early exit logic to the `DebateEngine`:

```python
# Add to DebateEngine.debate() method

class EarlyConsensusDetector:
    """Detects when debate can be terminated early."""
    
    CONSENSUS_THRESHOLDS = {
        "simple": 0.7,    # Lower bar for simple queries
        "medium": 0.8,    # Standard threshold
        "complex": 0.9,   # High bar for complex queries
        "critical": 0.95  # Very high for critical decisions
    }
    
    async def should_stop(self, round_responses: list, round_num: int,
                          complexity: str = "medium") -> dict:
        threshold = self.CONSENSUS_THRESHOLDS.get(complexity, 0.8)
        
        if round_num < 1:
            return {"stop": False, "reason": "Minimum 1 round required"}
        
        # Analyze agreement in positions
        positions = [r.get("position", "")[:200].lower() for r in round_responses]
        agree_signals = ["agree", "correct", "confirmed", "valid", "support"]
        disagree_signals = ["disagree", "incorrect", "error", "however", "but"]
        
        agree_count = sum(1 for p in positions 
                         if any(s in p for s in agree_signals))
        disagree_count = sum(1 for p in positions 
                            if any(s in p for s in disagree_signals))
        
        consensus = agree_count / max(len(positions), 1)
        
        if consensus >= threshold and disagree_count == 0:
            return {
                "stop": True, "consensus_score": consensus,
                "reason": f"Consensus {consensus:.0%} >= threshold {threshold:.0%}",
                "rounds_saved": 3 - round_num,
                "estimated_savings_pct": ((3 - round_num) / 3) * 100
            }
        
        return {"stop": False, "consensus_score": consensus,
                "reason": f"Consensus {consensus:.0%} < threshold {threshold:.0%}"}

early_consensus = EarlyConsensusDetector()
```

### Acceptance Criteria
- [ ] Consensus detected after Round 1 skips Rounds 2-3
- [ ] Threshold varies by complexity (simple=0.7, critical=0.95)
- [ ] Rounds saved and cost savings tracked
- [ ] Never exits before minimum 1 round

---

## PHASE 81: Speculative Decoding (Draft-Verify Pattern)
**Category**: Cost | **Duration**: 2 days | **Depends on**: Phase 10

### Objective
For code generation and long responses, use a cheap model to draft the response, then use the expensive model only to verify/edit. Instead of GPT-4 generating 2000 tokens from scratch, Flash drafts → GPT-4 reviews in a single pass. **Savings: 20-40%**.

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/speculative.py`

```python
"""Speculative decoding: Draft with cheap model, verify with expensive model."""

from .model_router import ModelRouter

class SpeculativeDecoder:
    DRAFT_MODEL = ("google", "gemini-2.0-flash")    # Cheap drafter
    VERIFY_MODEL = ("anthropic", "claude-sonnet")    # Expensive verifier
    
    def __init__(self, model_router: ModelRouter):
        self.router = model_router
    
    async def generate(self, prompt: str, task_type: str = "general",
                       workspace_id: str = None) -> dict:
        """Draft → Verify pattern for cost-efficient generation."""
        
        # Step 1: Draft with cheap model
        draft_prompt = f"""Generate a complete response for this task.
Be thorough and specific.

{prompt}"""
        
        d_provider, d_model = self.DRAFT_MODEL
        draft = await self.router.providers[d_provider].generate(draft_prompt, d_model)
        
        # Step 2: Verify with expensive model (much shorter prompt)
        verify_prompt = f"""Review and correct this AI-generated response.

ORIGINAL TASK: {prompt[:500]}

DRAFT RESPONSE:
{draft.response}

INSTRUCTIONS:
- Fix any factual errors or hallucinations
- Improve code correctness if applicable
- Keep what's good, only change what's wrong
- If the draft is good, respond with: APPROVED: [brief note]
- If changes needed, provide the corrected version"""
        
        v_provider, v_model = self.VERIFY_MODEL
        verification = await self.router.providers[v_provider].generate(
            verify_prompt, v_model)
        
        # Determine if draft was accepted or corrected
        is_approved = verification.response.strip().upper().startswith("APPROVED")
        final_response = draft.response if is_approved else verification.response
        
        total_cost = draft.cost_usd + verification.cost_usd
        # Estimate what full generation would have cost
        full_gen_cost = verification.cost_usd * 2.5  # Rough estimate
        savings = max(0, full_gen_cost - total_cost)
        
        return {
            "response": final_response,
            "draft_approved": is_approved,
            "draft_model": d_model,
            "verify_model": v_model,
            "draft_cost": draft.cost_usd,
            "verify_cost": verification.cost_usd,
            "total_cost": total_cost,
            "estimated_savings": savings
        }

speculative_decoder = SpeculativeDecoder(ModelRouter())
```

### Acceptance Criteria
- [ ] Draft generated by cheap model (Flash/DeepSeek)
- [ ] Verification by expensive model uses shorter prompt
- [ ] Approved drafts skip re-generation entirely
- [ ] Cost savings of 20-40% vs direct expensive generation
- [ ] Works for code generation, explanations, and architecture

---

## PHASE 82: Batch Deferred Processing
**Category**: Cost | **Duration**: 2 days | **Depends on**: Phase 8

### Objective
Queue non-urgent council queries (nightly code reviews, weekly ADR analysis, documentation audits) for batch processing. Reduces API overhead and enables off-peak processing. **Savings: 15-25%**.

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/batch_processor.py`

```python
"""Batch processor: Queue and process non-urgent council queries."""

from app.db.supabase_client import db
from datetime import datetime, timedelta

class BatchProcessor:
    PRIORITY_LEVELS = {
        "immediate": 0,    # Process now (user-facing queries)
        "soon": 300,       # Within 5 minutes
        "deferred": 3600,  # Within 1 hour
        "batch": 86400     # Daily batch (nightly code review, etc.)
    }
    
    async def enqueue(self, workspace_id: str, query: str,
                      priority: str = "deferred", metadata: dict = None) -> dict:
        """Add a query to the processing queue."""
        job = {
            "workspace_id": workspace_id,
            "query": query,
            "priority": priority,
            "status": "queued",
            "metadata": metadata or {},
            "scheduled_after": (datetime.utcnow() + 
                timedelta(seconds=self.PRIORITY_LEVELS.get(priority, 3600))).isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
        result = await db.client.table("batch_queue").insert(job).execute()
        return result.data[0] if result.data else job
    
    async def process_ready(self) -> list:
        """Process all queued jobs that are ready."""
        from app.services.council_kernel.engine import council_engine
        from app.services.council_kernel.types import CouncilType
        
        ready = await db.client.table("batch_queue") \
            .select("*").eq("status", "queued") \
            .lte("scheduled_after", datetime.utcnow().isoformat()) \
            .order("created_at").limit(20).execute()
        
        results = []
        for job in (ready.data or []):
            try:
                await db.client.table("batch_queue") \
                    .update({"status": "processing"}).eq("id", job["id"]).execute()
                
                result = await council_engine.consult(
                    workspace_id=job["workspace_id"],
                    query=job["query"],
                    council_type=CouncilType.CHILD)
                
                await db.client.table("batch_queue").update({
                    "status": "completed",
                    "result": result.model_dump(),
                    "completed_at": datetime.utcnow().isoformat()
                }).eq("id", job["id"]).execute()
                
                results.append({"job_id": job["id"], "status": "completed"})
            except Exception as e:
                await db.client.table("batch_queue").update({
                    "status": "failed", "error": str(e)
                }).eq("id", job["id"]).execute()
                results.append({"job_id": job["id"], "status": "failed", "error": str(e)})
        
        return results

batch_processor = BatchProcessor()
```

**SQL for batch queue table:**
```sql
CREATE TABLE batch_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    query TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'deferred',
    status TEXT NOT NULL DEFAULT 'queued',
    metadata JSONB DEFAULT '{}',
    result JSONB,
    error TEXT,
    scheduled_after TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_batch_queue_ready ON batch_queue(status, scheduled_after);
```

### Acceptance Criteria
- [ ] Non-urgent queries queued with priority levels
- [ ] Batch processing runs on schedule (cron or manual trigger)
- [ ] Failed jobs retry with error tracking
- [ ] Queue status visible in dashboard

---

## PHASE 83: RAG-Enhanced Council Prompts
**Category**: Cost | **Duration**: 2 days | **Depends on**: Phase 17, 29

### Objective
Before sending a query to the council, pull relevant knowledge (knowledge graph entries, past ADRs, memories, previous decisions) and inject it into the prompt. Informed models produce shorter, more accurate responses with fewer debate rounds. **Savings: 20-35%**.

#### [MODIFY] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/council_kernel/engine.py`

Add RAG context enrichment to the `CouncilEngine.consult()` method:

```python
# Add to CouncilEngine

from app.services.council_kernel.prompt_gateway import prompt_gateway
from app.services.context_pruner import context_pruner
from app.services.memory_engine import memory_engine

class RAGEnricher:
    """Enriches council prompts with relevant knowledge before execution."""
    
    MAX_CONTEXT_TOKENS = 500  # Keep RAG context compact
    
    async def enrich(self, workspace_id: str, query: str) -> str:
        """Pull relevant knowledge and build enriched prompt."""
        sections = []
        
        # 1. Recall relevant memories
        memories = await memory_engine.recall(workspace_id, query, limit=3)
        if memories:
            mem_text = "\n".join(f"- {m['content'][:150]}" for m in memories)
            sections.append(f"**Relevant workspace knowledge:**\n{mem_text}")
        
        # 2. Similar past decisions
        from app.services.knowledge_graph import knowledge_graph
        similar = await knowledge_graph.search_similar(workspace_id, query, limit=3)
        if similar:
            dec_text = "\n".join(f"- {s.get('title', 'Decision')}: {s.get('content', '')[:150]}" 
                               for s in similar)
            sections.append(f"**Related past decisions:**\n{dec_text}")
        
        # 3. Active risk signals (if security-related)
        if any(kw in query.lower() for kw in ["security", "risk", "vulnerability", "auth"]):
            risks = await db.client.table("risk_signals").select("*") \
                .eq("workspace_id", workspace_id).eq("resolved", False) \
                .limit(5).execute()
            if risks.data:
                risk_text = "\n".join(f"- [{r['severity']}] {r['description']}" 
                                    for r in risks.data)
                sections.append(f"**Active risk signals:**\n{risk_text}")
        
        if not sections:
            return query
        
        context = "\n\n".join(sections)
        return f"""[CONTEXT FROM WORKSPACE KNOWLEDGE]
{context}

[USER QUERY]
{query}

Use the context above to inform your response. Cite relevant knowledge where applicable."""

rag_enricher = RAGEnricher()
```

### Acceptance Criteria
- [ ] Relevant memories retrieved before council execution
- [ ] Past decisions and ADRs injected as context
- [ ] Risk signals included for security-related queries
- [ ] RAG context kept compact (<500 tokens) to avoid bloat
- [ ] Models produce more informed responses with fewer rounds

---

## PHASE 84: Model Settings Engine (Backend)
**Category**: Platform | **Duration**: 3 days | **Depends on**: Phase 9, 38

### Objective
Full model configuration engine with preset profiles and per-model parameter control. Users are the main organizers of how their models are used — AEGION provides smart defaults but the user has ultimate control.

#### Preset Profiles

| Preset | Description | Council Size | Models | Cache | Compression | Budget |
|--------|------------|-------------|--------|-------|-------------|--------|
| 🟢 **Cost Saver** | Minimize cost, use cheapest models | 1-2 | DeepSeek, Flash | Aggressive (0.85) | Always | $1/day |
| 🔵 **Balanced** (default) | Good quality at reasonable cost | 2-3 | Flash, Haiku, DeepSeek | Standard (0.92) | >100 words | $5/day |
| 🟡 **Quality First** | Best models, full council | 3-4 | Sonnet, GPT-4o, Pro | Light (0.95) | >500 words | $20/day |
| 🔴 **No Limits** | Maximum quality, no restrictions | 4+ | All premium models | None | None | Unlimited |
| 🟣 **Privacy First** | Local models only, no cloud | 1-3 | Ollama only | Local | None | $0 |

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/services/model_settings.py`

```python
"""Model Settings Engine: Full user control over model configuration."""

from app.db.supabase_client import db
import copy

PRESET_PROFILES = {
    "cost_saver": {
        "name": "Cost Saver", "icon": "🟢",
        "description": "Minimize cost, use cheapest models",
        "council": {"default_size": 1, "max_size": 2, "prefer_cheap": True},
        "cascade": {
            "enabled": True,
            "order": ["deepseek", "google", "ollama"],
            "confidence_threshold": 0.75
        },
        "cache": {"enabled": True, "similarity_threshold": 0.85},
        "compression": {"enabled": True, "min_words": 50, "target_ratio": 0.25},
        "gateway": {"enabled": True, "auto_optimize": True},
        "budget": {"daily_limit_usd": 1.0, "monthly_limit_usd": 25.0},
        "models": {
            "primary": ("deepseek", "deepseek-chat"),
            "secondary": ("google", "gemini-2.0-flash"),
            "fallback": ("ollama", "llama3")
        },
        "token_limits": {"simple": 300, "medium": 600, "complex": 1200},
        "temperature": {"default": 0.3, "creative": 0.6}
    },
    "balanced": {
        "name": "Balanced", "icon": "🔵",
        "description": "Good quality at reasonable cost (recommended)",
        "council": {"default_size": 2, "max_size": 3, "prefer_cheap": True},
        "cascade": {
            "enabled": True,
            "order": ["google", "deepseek", "anthropic", "openai"],
            "confidence_threshold": 0.85
        },
        "cache": {"enabled": True, "similarity_threshold": 0.92},
        "compression": {"enabled": True, "min_words": 100, "target_ratio": 0.3},
        "gateway": {"enabled": True, "auto_optimize": True},
        "budget": {"daily_limit_usd": 5.0, "monthly_limit_usd": 100.0},
        "models": {
            "primary": ("google", "gemini-2.0-flash"),
            "secondary": ("anthropic", "claude-haiku"),
            "fallback": ("deepseek", "deepseek-chat")
        },
        "token_limits": {"simple": 500, "medium": 1000, "complex": 2000},
        "temperature": {"default": 0.5, "creative": 0.7}
    },
    "quality_first": {
        "name": "Quality First", "icon": "🟡",
        "description": "Best models, full council debates",
        "council": {"default_size": 3, "max_size": 4, "prefer_cheap": False},
        "cascade": {
            "enabled": True,
            "order": ["anthropic", "openai", "google"],
            "confidence_threshold": 0.92
        },
        "cache": {"enabled": True, "similarity_threshold": 0.95},
        "compression": {"enabled": True, "min_words": 500, "target_ratio": 0.4},
        "gateway": {"enabled": True, "auto_optimize": False},
        "budget": {"daily_limit_usd": 20.0, "monthly_limit_usd": 400.0},
        "models": {
            "primary": ("anthropic", "claude-sonnet"),
            "secondary": ("openai", "gpt-4o"),
            "fallback": ("google", "gemini-2.5-pro")
        },
        "token_limits": {"simple": 1000, "medium": 2000, "complex": 4000},
        "temperature": {"default": 0.5, "creative": 0.8}
    },
    "no_limits": {
        "name": "No Limits", "icon": "🔴",
        "description": "Maximum quality, no restrictions",
        "council": {"default_size": 4, "max_size": 6, "prefer_cheap": False},
        "cascade": {"enabled": False, "order": [], "confidence_threshold": 0.0},
        "cache": {"enabled": False, "similarity_threshold": 1.0},
        "compression": {"enabled": False, "min_words": 99999, "target_ratio": 1.0},
        "gateway": {"enabled": True, "auto_optimize": False},
        "budget": {"daily_limit_usd": None, "monthly_limit_usd": None},
        "models": {
            "primary": ("anthropic", "claude-sonnet"),
            "secondary": ("openai", "gpt-4o"),
            "fallback": ("google", "gemini-2.5-pro")
        },
        "token_limits": {"simple": 2000, "medium": 4000, "complex": 8000},
        "temperature": {"default": 0.5, "creative": 0.9}
    },
    "privacy_first": {
        "name": "Privacy First", "icon": "🟣",
        "description": "Local models only, no cloud API calls",
        "council": {"default_size": 1, "max_size": 3, "prefer_cheap": True},
        "cascade": {
            "enabled": True,
            "order": ["ollama"],
            "confidence_threshold": 0.7
        },
        "cache": {"enabled": True, "similarity_threshold": 0.88},
        "compression": {"enabled": True, "min_words": 50, "target_ratio": 0.3},
        "gateway": {"enabled": False, "auto_optimize": False},
        "budget": {"daily_limit_usd": 0.0, "monthly_limit_usd": 0.0},
        "models": {
            "primary": ("ollama", "llama3"),
            "secondary": ("ollama", "codellama"),
            "fallback": ("ollama", "mistral")
        },
        "token_limits": {"simple": 500, "medium": 1000, "complex": 2000},
        "temperature": {"default": 0.4, "creative": 0.7}
    }
}

class ModelSettingsEngine:
    async def get_settings(self, workspace_id: str) -> dict:
        """Get current model settings for workspace."""
        result = await db.client.table("model_settings") \
            .select("*").eq("workspace_id", workspace_id).single().execute()
        if result.data:
            return result.data
        # Return default (balanced) if none set
        return await self.apply_preset(workspace_id, "balanced")
    
    async def apply_preset(self, workspace_id: str, preset_name: str) -> dict:
        """Apply a preset profile to the workspace."""
        preset = PRESET_PROFILES.get(preset_name)
        if not preset:
            raise ValueError(f"Unknown preset: {preset_name}")
        
        settings = {
            "workspace_id": workspace_id,
            "active_preset": preset_name,
            "settings": copy.deepcopy(preset),
            "custom_overrides": {}
        }
        
        await db.client.table("model_settings").upsert(settings, 
            on_conflict="workspace_id").execute()
        return settings
    
    async def update_setting(self, workspace_id: str, path: str, value) -> dict:
        """Update a specific setting (dot-notation path like 'council.default_size')."""
        current = await self.get_settings(workspace_id)
        settings = current.get("settings", {})
        
        # Navigate dot path and set value
        keys = path.split(".")
        target = settings
        for key in keys[:-1]:
            target = target.setdefault(key, {})
        target[keys[-1]] = value
        
        # Track custom override
        overrides = current.get("custom_overrides", {})
        overrides[path] = value
        
        await db.client.table("model_settings").update({
            "settings": settings,
            "custom_overrides": overrides,
            "active_preset": "custom"
        }).eq("workspace_id", workspace_id).execute()
        
        return await self.get_settings(workspace_id)
    
    async def check_budget(self, workspace_id: str) -> dict:
        """Check current spend against budget limits."""
        settings = await self.get_settings(workspace_id)
        budget = settings.get("settings", {}).get("budget", {})
        
        # Get today's spend
        from datetime import datetime, timedelta
        today = datetime.utcnow().strftime("%Y-%m-%d")
        daily = await db.client.table("cost_tracking").select("cost_usd") \
            .eq("workspace_id", workspace_id) \
            .gte("created_at", today).execute()
        daily_spend = sum(r["cost_usd"] for r in (daily.data or []))
        
        daily_limit = budget.get("daily_limit_usd")
        return {
            "daily_spend": daily_spend,
            "daily_limit": daily_limit,
            "daily_remaining": (daily_limit - daily_spend) if daily_limit else None,
            "budget_exceeded": daily_limit is not None and daily_spend >= daily_limit
        }
    
    def list_presets(self) -> list:
        """List all available presets."""
        return [{
            "key": k, "name": v["name"], "icon": v["icon"],
            "description": v["description"]
        } for k, v in PRESET_PROFILES.items()]

model_settings = ModelSettingsEngine()
```

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-backend/app/api/v1/model_settings.py`

```python
"""Model Settings API endpoints."""

from fastapi import APIRouter, Depends
from app.auth.supabase_auth import get_current_user
from app.services.model_settings import model_settings
from pydantic import BaseModel

router = APIRouter(prefix="/model-settings", tags=["Model Settings"])

class PresetRequest(BaseModel):
    preset: str

class UpdateSettingRequest(BaseModel):
    path: str    # e.g. "council.default_size"
    value: any   # The new value

@router.get("/")
async def get_settings(user: dict = Depends(get_current_user)):
    return await model_settings.get_settings(user["workspace_id"])

@router.get("/presets")
async def list_presets():
    return model_settings.list_presets()

@router.post("/preset")
async def apply_preset(req: PresetRequest, user: dict = Depends(get_current_user)):
    return await model_settings.apply_preset(user["workspace_id"], req.preset)

@router.patch("/setting")
async def update_setting(req: UpdateSettingRequest, user: dict = Depends(get_current_user)):
    return await model_settings.update_setting(user["workspace_id"], req.path, req.value)

@router.get("/budget")
async def check_budget(user: dict = Depends(get_current_user)):
    return await model_settings.check_budget(user["workspace_id"])
```

**SQL for model_settings table:**
```sql
CREATE TABLE model_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL UNIQUE REFERENCES workspaces(id),
    active_preset TEXT NOT NULL DEFAULT 'balanced',
    settings JSONB NOT NULL DEFAULT '{}',
    custom_overrides JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Acceptance Criteria
- [ ] 5 preset profiles available (Cost Saver, Balanced, Quality First, No Limits, Privacy First)
- [ ] Users can apply presets with one click
- [ ] Individual settings overridable via dot-notation path
- [ ] Custom overrides tracked separately from preset base
- [ ] Budget checking with daily/monthly limits
- [ ] Budget exceeded → block or warn before council execution
- [ ] Settings CRUD API fully functional

---

## PHASE 85: Model Settings Dashboard (Frontend)
**Category**: Frontend | **Duration**: 3 days | **Depends on**: Phase 84, 63

### Objective
A rich, interactive settings page where users have full control over every model parameter with visual preset cards, per-model configuration, budget gauges, and real-time cost estimation.

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-frontend/app/dashboard/models/page.tsx`

**Page Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│  MODEL SETTINGS                                    [Save] [Reset] │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  PRESET PROFILES    (click to apply)                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ 🟢 Cost  │ │ 🔵 Bal.  │ │ 🟡 Qual. │ │ 🔴 No    │ │ 🟣 Priv│ │
│  │  Saver   │ │(default) │ │  First   │ │  Limits  │ │  First │ │
│  │ $1/day   │ │ $5/day   │ │ $20/day  │ │ Unlim.   │ │ $0/day │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│                                                                   │
│  ───────────── COUNCIL CONFIGURATION ──────────────               │
│  Default Council Size:  [1] [2] [3] [4+]                         │
│  Prefer Cheaper Models: [ON/OFF]                                 │
│  Max Debate Rounds:     [1] [2] [3]                              │
│                                                                   │
│  ───────────── PROVIDER & MODELS ──────────────                   │
│  ┌─ OpenAI ──────────────────────────────────────┐               │
│  │ API Key: [••••••••••] [Show] [Test]           │               │
│  │ Models: gpt-4o ☑  gpt-4o-mini ☑              │               │
│  │ Priority: [2]  Temperature: [0.5]             │               │
│  └───────────────────────────────────────────────┘               │
│  ┌─ Anthropic ───────────────────────────────────┐               │
│  │ API Key: [••••••••••] [Show] [Test]           │               │
│  │ Models: claude-sonnet ☑  claude-haiku ☑       │               │
│  │ Priority: [1]  Temperature: [0.5]             │               │
│  └───────────────────────────────────────────────┘               │
│  ┌─ Google ──────────────────────────────────────┐               │
│  │ API Key: [••••••••••] [Show] [Test]           │               │
│  │ Models: gemini-flash ☑  gemini-pro ☑          │               │
│  └───────────────────────────────────────────────┘               │
│  ┌─ DeepSeek / Ollama / Custom ──────────────────┐               │
│  │ ...                                            │               │
│  └───────────────────────────────────────────────┘               │
│                                                                   │
│  ───────────── COST OPTIMIZATION ──────────────                   │
│  Prompt Gateway:      [ON/OFF]  Auto-optimize: [ON/OFF]          │
│  Semantic Cache:      [ON/OFF]  Threshold: [0.92]                │
│  Prompt Compression:  [ON/OFF]  Min words: [100]                 │
│  Early Consensus:     [ON/OFF]  Threshold: [0.8]                 │
│  Speculative Decode:  [ON/OFF]                                   │
│                                                                   │
│  ───────────── BUDGET CONTROLS ──────────────                     │
│  Daily Limit:   [$5.00 ▓▓▓▓░░░░░░ $2.13 spent]                 │
│  Monthly Limit: [$100 ▓▓░░░░░░░░ $23.45 spent]                  │
│  On Budget Exceed: [Warn] [Block] [Downgrade to Cost Saver]     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Key components to build:**
- `PresetCard` — Clickable card with icon, name, description, estimated cost
- `ProviderConfig` — Collapsible card per provider with API key, model toggles, params
- `CostOptToggle` — Toggle switch with tooltip explaining the optimization
- `BudgetGauge` — Progress bar showing daily/monthly spend vs limit
- `CostEstimator` — Real-time estimate: "With these settings, avg query ≈ $0.008"

### Acceptance Criteria
- [ ] 5 preset cards with visual selection (highlighted border on active)
- [ ] Per-provider API key management with show/hide and test button
- [ ] Per-model enable/disable toggles
- [ ] Cost optimization toggles with threshold sliders
- [ ] Budget gauge with real-time spend tracking
- [ ] Changes save immediately (optimistic UI with rollback on error)
- [ ] Mobile responsive layout

---

## PHASE 86: Model Settings Panel (VS Code Extension)
**Category**: Extension | **Duration**: 2 days | **Depends on**: Phase 84, 55

### Objective
Bring model settings control directly into VS Code with a webview panel and status bar integration for quick preset switching.

#### [NEW] `/Users/arpit/Projects/Aegion/aegion-extension/src/views/model_settings_panel.ts`

```typescript
import * as vscode from 'vscode';
import { ApiClient } from '../services/api_client';

export class ModelSettingsPanel {
    public static readonly viewType = 'aegion.modelSettings';
    private panel: vscode.WebviewPanel | undefined;
    
    constructor(private api: ApiClient) {}
    
    async show() {
        this.panel = vscode.window.createWebviewPanel(
            ModelSettingsPanel.viewType,
            'AEGION Model Settings',
            vscode.ViewColumn.One,
            { enableScripts: true }
        );
        
        const settings = await this.api.get('/model-settings');
        const presets = await this.api.get('/model-settings/presets');
        const budget = await this.api.get('/model-settings/budget');
        
        this.panel.webview.html = this.getHtml(settings, presets, budget);
        
        this.panel.webview.onDidReceiveMessage(async (msg) => {
            switch (msg.command) {
                case 'applyPreset':
                    await this.api.post('/model-settings/preset', { preset: msg.preset });
                    vscode.window.showInformationMessage(`Preset "${msg.preset}" applied`);
                    this.updateStatusBar(msg.preset);
                    break;
                case 'updateSetting':
                    await this.api.patch('/model-settings/setting', {
                        path: msg.path, value: msg.value
                    });
                    break;
            }
        });
    }
    
    updateStatusBar(preset: string) {
        // Update status bar item with current preset
    }
    
    private getHtml(settings: any, presets: any[], budget: any): string {
        // Returns HTML with preset cards, toggles, budget display
        // Mirrors the frontend dashboard layout
        return `<!DOCTYPE html>
<html><head><style>
    body { font-family: var(--vscode-font-family); padding: 16px; }
    .preset-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
    .preset-card { border: 2px solid var(--vscode-panel-border); border-radius: 8px;
        padding: 12px; cursor: pointer; text-align: center; }
    .preset-card.active { border-color: var(--vscode-focusBorder); background: var(--vscode-list-activeSelectionBackground); }
    .preset-card:hover { background: var(--vscode-list-hoverBackground); }
    .budget-bar { height: 8px; background: var(--vscode-progressBar-background); border-radius: 4px; margin: 8px 0; }
    .budget-fill { height: 100%; background: var(--vscode-progressBar-background); border-radius: 4px; }
</style></head><body>
    <h2>Model Settings</h2>
    <div class="preset-grid">
        ${presets.map((p: any) => `
            <div class="preset-card ${settings.active_preset === p.key ? 'active' : ''}"
                 onclick="applyPreset('${p.key}')">
                <div style="font-size: 24px">${p.icon}</div>
                <div><strong>${p.name}</strong></div>
                <div style="font-size: 11px; opacity: 0.7">${p.description}</div>
            </div>
        `).join('')}
    </div>
    <h3>Budget</h3>
    <p>Today: $${budget.daily_spend.toFixed(2)} / $${budget.daily_limit || '∞'}</p>
    <div class="budget-bar"><div class="budget-fill" style="width: ${budget.daily_limit ? (budget.daily_spend / budget.daily_limit * 100) : 0}%"></div></div>
    <script>
        const vscode = acquireVsCodeApi();
        function applyPreset(key) { vscode.postMessage({ command: 'applyPreset', preset: key }); }
    </script>
</body></html>`;
    }
}
```

**Register commands in `extension.ts`:**
```typescript
// Add to extension.ts activate()
const modelSettingsPanel = new ModelSettingsPanel(apiClient);
context.subscriptions.push(
    vscode.commands.registerCommand('aegion.models.configure', () => modelSettingsPanel.show()),
    vscode.commands.registerCommand('aegion.models.preset', async () => {
        const presets = await apiClient.get('/model-settings/presets');
        const selected = await vscode.window.showQuickPick(
            presets.map((p: any) => ({ label: `${p.icon} ${p.name}`, description: p.description, key: p.key })),
            { placeHolder: 'Select a model preset' }
        );
        if (selected) {
            await apiClient.post('/model-settings/preset', { preset: selected.key });
            vscode.window.showInformationMessage(`Preset "${selected.label}" applied`);
        }
    })
);

// Status bar: show current preset
const presetStatusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 90);
presetStatusBar.text = "$(settings-gear) Balanced";
presetStatusBar.tooltip = "AEGION Model Preset — Click to change";
presetStatusBar.command = "aegion.models.preset";
presetStatusBar.show();
```

### Acceptance Criteria
- [ ] Webview panel shows preset cards with visual selection
- [ ] Quick preset switching via Command Palette (`aegion.models.preset`)
- [ ] Status bar shows current preset name with click-to-change
- [ ] Budget display shows daily spend and limit
- [ ] Settings sync with backend API in real-time
- [ ] Full model settings accessible via `aegion.models.configure` command

---

# 📊 APPENDIX A: Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------| 
| **Backend** | Python 3.12, FastAPI, Uvicorn | API server |
| **Database** | Supabase (PostgreSQL 15) | Primary data store |
| **Vector DB** | pgvector (via Supabase) | Embeddings & semantic search |
| **Auth** | Supabase Auth | Authentication & authorization |
| **Realtime** | Supabase Realtime | WebSocket pub/sub |
| **Frontend** | Next.js 14, React, Vanilla CSS | Web dashboard |
| **Extension** | TypeScript, VS Code Extension API | IDE integration |
| **LLM Providers** | OpenAI, Anthropic, Google, DeepSeek, Ollama | AI models |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) | Local embeddings |
| **Deployment** | GCP Cloud Run | Serverless containers |
| **CI/CD** | GitHub Actions | Automated deployment |
| **Monitoring** | GCP Cloud Monitoring | Observability |
| **Cache** | pgvector semantic cache | LLM response caching |
| **Compression** | LLMLingua-2 | Prompt token reduction |

---

# 📊 APPENDIX B: Estimated Timeline

| Block | Phases | Duration | Focus |
|-------|--------|----------|-------|
| **Foundation** | 1-7 | ~18 days | Git, GCP, Supabase, Auth, Migrations |
| **Council Kernel** | 8-18 | ~25 days | ACK engines, cache, compression, integration |
| **Governance** | 19-23 | ~14 days | Archon tiers, freeze, Sentinel |
| **Platform** | 24-38 | ~30 days | Chronos, Praxis, Memory, Skills, Collaboration, Security |
| **Integrations** | 39-42 | ~8 days | ChatOps, MCP, Agents, Commands |
| **Intelligence** | 43-45 | ~6 days | Learning, Pipelines, Reasoning |
| **Advanced ACK** | 46-51 | ~12 days | Constitution, Reflector, Red Team, Temporal |
| **Extension** | 52-56 | ~15 days | VS Code UI, Ghost Text, Commands |
| **Frontend** | 57-68 | ~25 days | Next.js Dashboard (12 pages) |
| **Testing** | 69-71 | ~8 days | Unit, Integration, E2E, Load |
| **DevOps** | 72-74 | ~6 days | Docker, Cloud Run, Monitoring |
| **Launch** | 75 | ~5 days | Docs, Marketplace, Final QA |
| **Cost Optimization** | 76-83 | ~15 days | Prompt Gateway, Adaptive Council, Token Budget, Pruning, Consensus, Speculative, Batch, RAG |
| **Model Settings** | 84-86 | ~8 days | Backend engine, Frontend dashboard, VS Code panel |
| **TOTAL** | | **~195 days** | **Estimated solo developer timeline** |

> **Note**: This is a conservative estimate. Actual time may be shorter due to parallel work on independent phases. Phases 1-18 (Foundation + ACK) are the critical path.

---

# 📊 APPENDIX C: Estimated Monthly Costs

| Resource | Free Tier | After Credits | Notes |
|----------|-----------|---------------|-------|
| Supabase | $0/mo | $0/mo | Free: 500MB DB, 50K MAU |
| GCP Cloud Run | $0 (credits) | ~$5-15/mo | Scale-to-zero when idle |
| Vertex AI (Gemini) | $0 (credits) | ~$5-20/mo | Flash model is cheapest |
| Domain name | — | ~$12/year | Optional |
| **Total (with credits)** | **$0/mo** | — | 12-24 months runway |
| **Total (post-credits)** | — | **~$10-35/mo** | Minimal traffic |

---

*End of Master Work Plan — Version 1.1.0*
*This document is self-contained. No external documentation required.*
*Updated: Added Cost Optimization (Phases 76-83) and Model Settings (Phases 84-86).*
