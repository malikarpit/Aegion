# Aegion — Complete Runtime Flow Reference

> **Last updated**: 2026-02-13
> This document traces **every user-facing flow** from the VS Code extension through the backend API.
> It is the single source of truth for understanding what Aegion can do at runtime.

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Extension Activation](#2-extension-activation)
3. [Session Lifecycle](#3-session-lifecycle)
4. [Proposal & Governance Pipeline](#4-proposal--governance-pipeline)
5. [AI Council](#5-ai-council)
6. [Evidence Graph](#6-evidence-graph)
7. [Decision Management](#7-decision-management)
8. [Architecture & ADRs](#8-architecture--adrs)
9. [Governance Controls](#9-governance-controls)
10. [Sentinel — Drift & Risk Monitoring](#10-sentinel--drift--risk-monitoring)
11. [Noesis — Cognitive Analytics](#11-noesis--cognitive-analytics)
12. [Ghost Text — Inline Completions](#12-ghost-text--inline-completions)
13. [Praxis — Code Sandbox](#13-praxis--code-sandbox)
14. [Chronos — Time Travel & Snapshots](#14-chronos--time-travel--snapshots)
15. [Memory & Context](#15-memory--context)
16. [Rules Engine](#16-rules-engine)
17. [Skills Marketplace](#17-skills-marketplace)
18. [Task Inbox](#18-task-inbox)
19. [Checkpoints — Git Safety](#19-checkpoints--git-safety)
20. [Collaboration & Presence](#20-collaboration--presence)
21. [War Room — Incident Response](#21-war-room--incident-response)
22. [Cloud Delegation](#22-cloud-delegation)
23. [Diff Review & Proposals](#23-diff-review--proposals)
24. [Audit Trail](#24-audit-trail)
25. [ChatOps Integration](#25-chatops-integration)
26. [MCP Tool Server](#26-mcp-tool-server)
27. [Terminal & Browser Tools](#27-terminal--browser-tools)
28. [AI Commands](#28-ai-commands)
29. [Model Routing](#29-model-routing)
30. [Agent Identity & Verification](#30-agent-identity--verification)
31. [Secrets Vault](#31-secrets-vault)
32. [Rejection Learning](#32-rejection-learning)
33. [Decision Pipelines](#33-decision-pipelines)
34. [Reasoning Chains](#34-reasoning-chains)
35. [Admin Dashboard](#35-admin-dashboard)
36. [Event Streaming (SSE)](#36-event-streaming-sse)
37. [WebSocket Real-Time](#37-websocket-real-time)
38. [Health & Readiness](#38-health--readiness)
39. [Configuration & Networking](#39-configuration--networking)
40. [Middleware & Guards](#40-middleware--guards)
41. [Authentication & Authorization](#41-authentication--authorization)
42. [Knowledge Graph Infrastructure](#42-knowledge-graph-infrastructure)
43. [Durable Storage & Crash Safety](#43-durable-storage--crash-safety)
44. [Observability & Tracing](#44-observability--tracing)
45. [Data Governance & Isolation](#45-data-governance--isolation)

---

## 1. System Architecture Overview

```mermaid
graph TB
    subgraph "VS Code Extension"
        EXT[extension.ts] --> SM[SessionManager]
        EXT --> API[AegionClient]
        EXT --> SIDEBAR[Sidebar WebView]
        EXT --> PANELS["Panels (Dashboard, WarRoom, etc.)"]
        EXT --> GHOST[GhostTextProvider]
        EXT --> CONCEPT[ConceptNavigator]
    end

    subgraph "Backend (FastAPI)"
        MAIN[main.py] -->|/api/v1| ROUTER[api_v1_router]
        ROUTER --> SESSIONS[sessions]
        ROUTER --> PROPOSALS[proposals]
        ROUTER --> COUNCIL[council]
        ROUTER --> EVIDENCE[evidence]
        ROUTER --> SENTINEL[sentinel]
        ROUTER --> NOESIS[noesis]
        ROUTER --> GOVERNANCE[governance]
        ROUTER --> DELEGATION[delegation]
        ROUTER --> MANY["... 30+ more routers"]
    end

    subgraph Services
        ARCHON["Archon (Governance Engine)"]
        CHRONOS_SVC["Chronos (Timeline)"]
        NEXUS["Nexus (Event Bus)"]
        PRAXIS_SVC["Praxis (Sandbox)"]
        SENTINEL_SVC["Sentinel (Drift)"]
        NOESIS_SVC["Noesis (Analytics)"]
    end

    subgraph "Infrastructure (Sprint 12-21)"
        GRAPH_PROV["Graph Provider (Singleton)"]
        DURABLE["Durable Store (Crash-Safe)"]
        AUTH_CFG["Auth Config (Multi-Provider)"]
        TRACING["OpenTelemetry Tracing"]
        METRICS["Prometheus Metrics"]
    end

    API -->|HTTP / SSE| MAIN
    SESSIONS --> ARCHON
    PROPOSALS --> ARCHON
    GOVERNANCE --> ARCHON
    EVIDENCE --> CHRONOS_SVC
    PROPOSALS --> GRAPH_PROV
    EVIDENCE --> GRAPH_PROV
    NOESIS --> GRAPH_PROV
```

### URL Construction

```
Full URL = baseUrl + endpoint
         = "http://localhost:8000" + "/api/v1/sessions/start"
         = "http://localhost:8000/api/v1/sessions/start"

baseUrl comes from:  VS Code setting "aegion.backendUrl"
endpoint comes from: Endpoints object in client.ts (all embed /api/v1)
```

---

## 2. Extension Activation

**Trigger**: VS Code loads the Aegion extension.

```mermaid
sequenceDiagram
    participant VSCode
    participant Extension as extension.ts
    participant SM as SessionManager
    participant API as AegionClient

    VSCode->>Extension: activate(context)
    Extension->>SM: new SessionManager(context)
    Extension->>Extension: Register 25+ commands
    Extension->>Extension: Register sidebar, status bar
    Extension->>Extension: Register GhostText provider
    Extension->>Extension: Register ConceptNavigator
    Extension->>API: checkBackendHealth()
    API-->>Extension: { status: "healthy" }
    Extension->>Extension: Register onWillSave SCM boundary
```

**Components initialized on activation:**

| Component | Purpose |
|-----------|---------|
| `SessionManager` | Tracks active session state, decision/evidence counts |
| `IdentityManager` | Manages user role and permissions |
| `GovernanceStatusBar` | Shows session/governance state in status bar |
| `GhostTextProvider` | Inline code completions via backend |
| `ConceptNavigator` | Navigate evidence graph via quick-pick |
| `AegionSidebarProvider` | Main sidebar webview |
| `DiffManager` | Show AI-generated code diffs |
| `RecoveryViewProvider` | TreeView for draft/orphan session recovery |

---

## 3. Session Lifecycle

A **session** is the core collaboration unit. All proposals, evidence, and decisions are scoped to a session.

### 3.1 Start Session

```
User: Command Palette → "Aegion: Start Session"
```

```mermaid
sequenceDiagram
    participant User
    participant Ext as Extension
    participant SM as SessionManager
    participant API as AegionClient
    participant BE as Backend

    User->>Ext: aegion.startSession
    Ext->>SM: startSession()
    SM->>API: startSession({ workspace_id, user_id })
    API->>BE: POST /api/v1/sessions/start
    Note over BE: Validates X-Aegion-Session header<br/>Creates session with UUID
    BE-->>API: { session_id, workspace_id, status: "active" }
    API-->>SM: SessionResponse
    SM->>SM: Update state (sessionId, status)
    SM->>Ext: Emit stateChange event
    Ext->>Ext: Update GovernanceStatusBar
```

**Backend endpoint**: `POST /api/v1/sessions/start`
**Router**: `sessions.py` → `APIRouter(prefix="/sessions")`

### 3.2 Close Session

```
User: Command Palette → "Aegion: Close Session"
      → Quick pick: "Yes, distill artifacts" or "No, discard"
```

```mermaid
sequenceDiagram
    participant User
    participant SM as SessionManager
    participant API as AegionClient
    participant BE as Backend

    User->>SM: closeSession(distill=true)
    SM->>API: closeSession(sessionId)
    API->>BE: POST /api/v1/sessions/{id}/close
    Note over BE: If distill=true:<br/>Extracts memories, creates summary<br/>Stores artifacts for future context
    BE-->>API: { status: "closed", artifacts: [...] }
    SM->>SM: Clear state
```

**Backend endpoint**: `POST /api/v1/sessions/{session_id}/close`

### 3.3 Session Recovery

```
Sidebar → Recovery View → TreeView shows Drafts + Orphaned Sessions
```

| Action | Endpoint |
|--------|----------|
| List drafts | `GET /api/v1/sessions/drafts/` |
| List orphans | `GET /api/v1/sessions/orphaned?threshold_minutes=60` |
| Restore draft | `POST /api/v1/sessions/drafts/{id}/restore` |
| Recover session | `POST /api/v1/sessions/{id}/recover` |
| Delete draft | `DELETE /api/v1/sessions/drafts/{id}` |

### 3.4 Session Modes

Sessions support different operational modes:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/sessions/{id}/mode` | Set session mode |
| `GET /api/v1/sessions/{id}/mode` | Get current mode |

### 3.5 SCM Boundary Warning

When a user saves a file **without an active session**, the extension shows a warning:

```
⚠️ Saving ungoverned change in 'filename.ts'. Start a session to track?
    [Start Session] [Ignore]
```

This is registered via `vscode.workspace.onWillSaveTextDocument`.

---

## 4. Proposal & Governance Pipeline

The **proposal** is the central governance unit. Every code change must go through the proposal pipeline.

### 4.1 Create Proposal

```
User: Command Palette → "Aegion: Create Proposal"
```

```mermaid
sequenceDiagram
    participant User
    participant Ext as Extension
    participant API as AegionClient
    participant BE as Backend
    participant Archon as Archon (Governance)

    User->>Ext: aegion.createProposal
    Note over Ext: Prompts for:<br/>1. Title<br/>2. Description<br/>3. Impact Level<br/>4. Reversibility<br/>5. Assumptions<br/>6. Constraints<br/>7. Alternatives
    Ext->>API: createProposal(sessionId, { claim, reasoning, impact, reversibility })
    API->>BE: POST /api/v1/proposals
    BE->>Archon: classify_tier(impact, reversibility, affected_modules)
    Note over Archon: T0 = trivial + trivial<br/>T1 = local impact<br/>T2 = cross-module<br/>T3 = system-wide / irreversible
    Archon-->>BE: tier = "T2"
    Note over BE: Creates proposal node in graph<br/>Links to session via PROPOSED_IN edge
    BE-->>API: ProposalResponse { proposal_id, tier, status: "draft" }
    API-->>Ext: Show "Proposal created: abc123... (Tier: T2)"
    Ext->>Ext: setExplorationStage("proposed")
```

**Backend endpoint**: `POST /api/v1/proposals`

### 4.2 Tier Classification

```
Impact Level    × Reversibility → Tier
─────────────────────────────────────
trivial           trivial        → T0 (auto-approve)
local             easy           → T1 (single approval)
cross_module      moderate       → T2 (architect review)
system_wide       difficult      → T3 (admin-only)
external          irreversible   → T3
```

### 4.3 Approve Proposal

```
User: Command Palette → "Aegion: Approve Proposal"
      → Enter proposal ID
      → See tier label + warning for T2+
      → Enter justification
```

```mermaid
sequenceDiagram
    participant User
    participant API as AegionClient
    participant BE as Backend
    participant Archon as Archon
    participant Graph as Knowledge Graph

    User->>API: approveProposal(sessionId, proposalId, { decision: "approve", reason })
    API->>BE: POST /api/v1/proposals/{id}/approve

    BE->>BE: Re-approval Guard (409 if already approved)
    BE->>Archon: validate_approval(proposalId, approver, tier)
    Note over Archon: Checks:<br/>1. Freeze mode (guard_writable)<br/>2. Approver has tier authority<br/>3. Evidence requirements met (T2+)<br/>4. Cooling period respected

    Archon-->>BE: Approved

    BE->>Graph: Fetch evidence_nodes linked to proposal
    Note over BE: Security: Uses graph-validated<br/>evidence IDs ONLY (never client input)

    BE->>Graph: Create DECISION node
    Note over BE: evidence_ids = [n.node_id for n in evidence_nodes]<br/>client_evidence_ids stored in metadata only

    BE-->>API: ProposalResponse { status: "approved", decision_id }
```

**Security hardening (Sprint 21)**:
- **Evidence ID validation**: Decision records use only graph-validated evidence IDs, never client-provided `request.evidence_ids`
- **Re-approval guard**: Returns `409 Conflict` if proposal already approved (lines 257-264)
- **Client evidence preserved**: `request.evidence_ids` stored in `metadata.client_evidence_ids` for audit trail only

**Backend endpoint**: `POST /api/v1/proposals/{proposal_id}/approve`

### 4.4 Reject Proposal

```
User: Command Palette → "Aegion: Reject Decision"
      → Enter proposal ID → Enter reason
```

**Backend endpoint**: `POST /api/v1/proposals/{proposal_id}/reject`

### 4.5 Review & Vote

Reviews are now **persistently stored** in the knowledge graph (Sprint 21):

```mermaid
sequenceDiagram
    participant User
    participant BE as Backend
    participant Graph as Knowledge Graph

    User->>BE: POST /proposals/{id}/review
    BE->>Graph: add_node(type=REVIEW, { reviewer, verdict, comment })
    BE->>Graph: add_edge(review → proposal, REVIEWED_BY)
    BE->>BE: Audit log: REVIEW_SUBMITTED
    BE-->>User: ReviewResponse { review_id, verdict }
```

| Endpoint | Purpose |
|----------|---------|
| `POST /proposals/{id}/review` | Submit structured review (persisted as REVIEW node) |
| `POST /proposals/{id}/vote` | Cast governance vote |
| `GET /proposals/{id}` | Get proposal details |
| `GET /proposals/session/{session_id}` | List proposals in session |

---

## 5. AI Council

The AI Council is the primary AI reasoning engine — it provides governed code generation and architectural advice.

### 5.1 Invoke Council (Streaming)

```
User: Command Palette → "Aegion: Invoke AI Council"
      → Enter prompt
```

```mermaid
sequenceDiagram
    participant User
    participant Ext as Extension
    participant API as AegionClient
    participant BE as Backend
    participant Council as Council Service

    User->>Ext: aegion.invokeCouncil
    Note over Ext: Shows input box for prompt
    Ext->>API: invokeCouncilStream(sessionId, { prompt, context })
    API->>BE: POST /api/v1/council/stream (SSE)
    BE->>Council: invoke(prompt, context, stream=true)
    Note over Council: Multi-agent reasoning:<br/>1. Problem decomposition<br/>2. Code generation<br/>3. Risk assessment<br/>4. Consensus building
    loop SSE chunks
        Council-->>BE: chunk
        BE-->>API: data: chunk
        API-->>Ext: yield chunk
        Ext->>Ext: Update progress notification
    end
    Note over Ext: If response contains ```code```:<br/>Shows "Show Diff" button<br/>Opens DiffManager side-by-side
```

**Backend endpoints**:
- `POST /api/v1/council/invoke` — synchronous response
- `POST /api/v1/council/stream` — SSE streaming response

### 5.2 Council Analytics

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/council/analytics/analyze` | Analyze council performance metrics |

---

## 6. Evidence Graph

Evidence nodes are **append-only** — once created, they cannot be modified or deleted. This enforces the governance doctrine that evidence is immutable.

### 6.1 Submit Evidence

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/evidence/submit` | Submit evidence for a proposal |
| `POST /api/v1/evidence/{id}/snapshots` | Capture evidence snapshots |
| `GET /api/v1/evidence/{proposal_id}` | Get evidence for a proposal |

```mermaid
sequenceDiagram
    participant API as Client
    participant BE as Backend
    participant Graph as Knowledge Graph

    API->>BE: POST /api/v1/evidence/submit
    Note over BE: guard_writable() — blocks if frozen
    BE->>Graph: add_node(type=EVIDENCE, properties)
    Note over Graph: Append-only:<br/>update_node(EVIDENCE) → ValueError<br/>delete_node(EVIDENCE) → ValueError
    BE->>Graph: add_edge(evidence → proposal, SUPPORTS)
    BE-->>API: { evidence_id, status: "recorded" }
```

### 6.2 Evidence Decision Graph (EDG)

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/edg/traverse` | Traverse the evidence-decision graph |
| `GET /api/v1/edg/query` | Query the graph structure |

### 6.3 Append-Only Enforcement

```python
# In memory_graph.py — evidence and decision nodes are immutable
async def update_node(self, node_id, properties):
    if old_node.node_type in (GraphNodeType.EVIDENCE, GraphNodeType.DECISION):
        raise ValueError("Node is append-only and cannot be modified")

async def delete_node(self, node_id):
    if node.node_type in (GraphNodeType.EVIDENCE, GraphNodeType.DECISION):
        raise ValueError("Node is append-only and cannot be deleted")
```

### 6.4 Node ID Uniqueness

```python
# In memory_graph.py — duplicate IDs are rejected
async def add_node(self, node_type, node_id, properties):
    if node_id in self._nodes:
        raise ValueError(f"Node {node_id} already exists")
```

---

## 7. Decision Management

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/decisions` | List all decisions |
| `POST /api/v1/decisions/{id}/supersede` | Supersede a decision |
| `GET /api/v1/decisions/{id}/lineage` | Get decision lineage/provenance |
| `GET /api/v1/decisions/graph` | Get full decision graph |

```
User: Command Palette → "Aegion: Supersede Decision"
      → Enter decision ID → Enter reason → Creates new proposal
```

---

## 8. Architecture & ADRs

Architecture Decision Records (ADRs) document significant architectural decisions.

### 8.1 Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/architecture/adrs` | Create an ADR |
| `GET /api/v1/architecture/adrs` | List all ADRs |
| `GET /api/v1/architecture/adrs/{id}` | Get ADR by ID |
| `POST /api/v1/architecture/adrs/{id}/accept` | Accept an ADR |
| `POST /api/v1/architecture/adrs/{id}/deprecate` | Deprecate an ADR |
| `GET /api/v1/architecture/adrs/{id}/chain` | Get ADR supersession chain |
| `GET /api/v1/architecture/timeline/{workspace_id}` | Get architecture timeline |
| `POST /api/v1/architecture/snapshots` | Capture state snapshot |
| `GET /api/v1/architecture/snapshots` | List snapshots |
| `GET /api/v1/architecture/state-at/{timestamp}` | View state at a point in time |
| `POST /api/v1/architecture/diff` | Compare two states |
| `POST /api/v1/architecture/adrs/extract` | Auto-extract ADR drafts from decisions |

### 8.2 Generate ADR Flow

```
User: Command Palette → "Aegion: Generate ADR"
      → Enter decision ID
      → ADR generated and opened in editor
```

### 8.3 ADR Graph View

```
User: Command Palette → "Aegion: Show ADR Graph"
      → Opens ADRGraph webview (TreeView: shows ADR hierarchy)
```

---

## 9. Governance Controls

The **Archon** service is the backend governance engine.

### 9.1 Freeze Mode

When freeze mode is active, **all mutating endpoints return 403 Forbidden**.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/governance/freeze` | Activate freeze mode |
| `POST /api/v1/governance/unfreeze` | Deactivate freeze mode |
| `GET /api/v1/governance/status` | Check freeze status |
| `GET /api/v1/governance/policy` | Get governance policy |

### 9.2 Freeze Guard Coverage

Every mutating endpoint calls `guard_writable()`:

```python
from app.services.archon import get_archon, GovernanceError
archon = get_archon()
try:
    archon.guard_writable()  # Raises if frozen
except GovernanceError as e:
    raise HTTPException(status_code=403, detail=str(e))
```

**Protected endpoints** (12 across 5 files):
- `evidence.py`: submit, capture_snapshots
- `architecture.py`: create_adr, accept_adr, deprecate_adr, capture_snapshot, extract_adrs
- `pipelines.py`: create_pipeline, execute_step
- `rejections.py`: record_rejection
- `diff_review.py`: add_comment, resolve_comment, apply_proposal

### 9.3 AI Toggle

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/governance/workspaces/{id}/ai-toggle` | Enable/disable AI for workspace |
| `GET /api/v1/governance/workspaces/{id}/ai-status` | Check AI status |

### 9.4 Governance Panel

```
User: Command Palette → "Aegion: Open Governance Center"
      → Opens ArchonUIPanel webview
```

---

## 10. Sentinel — Drift & Risk Monitoring

Sentinel monitors for architectural drift and calculates risk scores.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/sentinel/risk-score` | Calculate risk score for workspace |
| `POST /api/v1/sentinel/heatmap` | Generate risk heatmap |
| `POST /api/v1/sentinel/drift` | Run drift detection |
| `GET /api/v1/sentinel/drift/{workspace_id}/status` | Get drift status |
| `GET /api/v1/sentinel/alerts` | List active alerts |

```
User: Command Palette → "Aegion: Open Risk Observatory"
      → Opens ObservabilityPanel webview
```

---

## 11. Noesis — Cognitive Analytics

Noesis provides cognitive load assessment and impact analysis.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/noesis/cognitive-load` | Assess developer cognitive load |
| `GET /api/v1/noesis/cognitive-load/{user_id}/should-break` | Should the user take a break? |
| `POST /api/v1/noesis/cognitive-load/{user_id}/break` | Record break taken |
| `POST /api/v1/noesis/uncertainty` | Visualize uncertainty |
| `POST /api/v1/noesis/impact-analysis` | Analyze impact of changes |
| `POST /api/v1/noesis/decisions/record` | Record a decision event |
| `GET /api/v1/noesis/decisions/{id}/provenance` | Get decision provenance graph |
| `GET /api/v1/noesis/workspace/{id}/topology` | Get workspace decision topology |

---

## 12. Ghost Text — Inline Completions

Ghost text provides **inline code completions** in the editor, similar to Copilot but governance-aware.

```mermaid
sequenceDiagram
    participant Editor
    participant GT as GhostTextProvider
    participant API as AegionClient
    participant BE as Backend

    Editor->>GT: provideInlineCompletionItems(document, position)
    GT->>API: getGhostText({ file, position, context })
    API->>BE: POST /api/v1/ghost-text/complete
    Note over BE: Noesis ghost service processes:<br/>1. File context<br/>2. Session context<br/>3. Governance constraints
    BE-->>API: { completion: "suggested code..." }
    API-->>GT: GhostTextResponse
    GT-->>Editor: InlineCompletionItem (ghost text shown inline)
```

**Backend endpoint**: `POST /api/v1/ghost-text/complete`

---

## 13. Praxis — Code Sandbox

Praxis provides sandboxed code execution with safety controls.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/praxis/execute` | Execute code in sandbox |
| `POST /api/v1/praxis/validate` | Validate code before execution |
| `GET /api/v1/praxis/environments` | List available environments |

**Execution flow**:
1. If Docker is available → isolated container execution
2. If Docker unavailable → **hardened subprocess** (restricted, logged)
3. High-risk actions blocked when Docker unavailable

---

## 14. Chronos — Time Travel & Snapshots

Chronos provides temporal navigation through the project's decision history.

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/chronos/timeline` | Get full timeline |
| `GET /api/v1/chronos/events` | List chronological events |
| `POST /api/v1/chronos/snapshot` | Take a point-in-time snapshot |

```
User: Command Palette → "Aegion: Open Architecture Timeline"
      → Opens TimelinePanel webview
      → Chronos Explorer sidebar (TreeView with refresh: aegion.chronos.refresh)
```

---

## 15. Memory & Context

Memory provides durable storage of context, learnings, and artifacts across sessions.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/memory` | Store a memory item |
| `GET /api/v1/memory` | List all memories |
| `GET /api/v1/memory/{id}` | Get memory by ID |
| `DELETE /api/v1/memory/{id}` | Delete memory |
| `POST /api/v1/memory/query` | Semantic search across memories |

```
User: Command Palette → "Aegion: Query Memory"
      → Enter search query
      → Results shown in quick-pick
      → Select to view full JSON
```

```
User: Command Palette → "Aegion: Open Memory & Rules"
      → Opens MemoryRulesPanel webview
```

---

## 16. Rules Engine

Rules are governance constraints that can be evaluated programmatically.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/rules` | Create a rule |
| `GET /api/v1/rules` | List all rules |
| `GET /api/v1/rules/{id}` | Get rule by ID |
| `PUT /api/v1/rules/{id}` | Update a rule |
| `DELETE /api/v1/rules/{id}` | Delete a rule |
| `POST /api/v1/rules/evaluate` | Evaluate rules against context |

---

## 17. Skills Marketplace

Skills are reusable extensions that add new capabilities to Aegion.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/skills` | Register a skill |
| `GET /api/v1/skills` | List available skills |
| `GET /api/v1/skills/{id}` | Get skill details |
| `POST /api/v1/skills/{id}/install` | Install a skill |
| `POST /api/v1/skills/{id}/validate` | Validate a skill |
| `DELETE /api/v1/skills/{id}` | Remove a skill |
| `POST /api/v1/skills/{id}/invoke` | Invoke a skill |
| `POST /api/v1/skills/{id}/invoke-link` | Create invocation link (URL-based) |
| `GET /api/v1/skills/invoke/{token}` | Redeem invocation link |
| `GET /api/v1/skills/{id}/invocations` | List skill invocations |

```
User: Command Palette → "Aegion: Open Skill Catalog"
      → Opens SkillCatalogPanel webview
```

---

## 18. Task Inbox

Tasks represent work items that need attention.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/tasks` | Create a task |
| `GET /api/v1/tasks` | List tasks |
| `GET /api/v1/tasks/{id}` | Get task by ID |
| `PUT /api/v1/tasks/{id}` | Update a task |

```
User: Command Palette → "Aegion: Open Task Inbox"
      → Opens TaskInboxPanel webview
```

---

## 19. Checkpoints — Git Safety

Checkpoints provide git-based safety net for code changes.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/checkpoints` | Create a checkpoint |
| `GET /api/v1/checkpoints` | List checkpoints |
| `GET /api/v1/checkpoints/{id}` | Get checkpoint details |
| `DELETE /api/v1/checkpoints/{id}` | Delete a checkpoint |

```
User: Command Palette → "Aegion: Open Checkpoints"
      → Opens CheckpointPanel webview
```

---

## 20. Collaboration & Presence

Real-time collaboration features for team development.

### 20.1 Presence

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/presence/heartbeat` | Send heartbeat (I'm here) |
| `GET /api/v1/presence` | List who's online |
| `GET /api/v1/presence/{user_id}` | Get user presence |
| `POST /api/v1/presence/leave` | Leave (go offline) |

### 20.2 Collaboration Panel

```
User: Command Palette → "Aegion: Open Collaboration"
      → Opens CollaborationPanel webview
```

---

## 21. War Room — Incident Response

War Room provides a command center for handling production incidents.

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/warroom/overview` | Get war room overview |
| `POST /api/v1/warroom/incidents` | Create an incident |
| `GET /api/v1/warroom/incidents` | List incidents |
| `GET /api/v1/warroom/incidents/{id}` | Get incident details |
| `PUT /api/v1/warroom/incidents/{id}` | Update incident |

**Incident model** includes `workspace_id` for workspace-scoped isolation (Sprint 21).

```
User: Command Palette → "Aegion: Open War Room"
      → Opens WarRoomPanel webview
```

---

## 22. Cloud Delegation

Cloud delegation enables running tasks on remote infrastructure.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/delegation/deploy` | Deploy to cloud |
| `GET /api/v1/delegation/deployments/{id}` | Get deployment status |
| `GET /api/v1/delegation/resources` | List cloud resources |
| `GET /api/v1/delegation/resources/{id}/logs` | Get resource logs |
| `GET /api/v1/delegation/health` | Cloud health check |
| `POST /api/v1/delegation/runs` | Trigger remote run |
| `GET /api/v1/delegation/runs` | List remote runs |
| `GET /api/v1/delegation/runs/{id}` | Get run status |

```
User: Command Palette → "Aegion: Open Cloud Delegate"
      → Opens DelegatePanel webview
```

---

## 23. Diff Review & Proposals

Inline diff review for code change proposals.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/proposals/{id}/comments` | Add inline diff comment |
| `PATCH /api/v1/proposals/{id}/comments/{cid}/resolve` | Resolve a comment |
| `GET /api/v1/proposals/{id}/comments` | List comments |
| `POST /api/v1/proposals/{id}/apply` | Apply proposed changes |

```
User: Command Palette → "Aegion: Open Multi-File Review"
      → Opens MultiFileReviewPanel webview
```

---

## 24. Audit Trail

Complete audit log of all governance actions.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/audit/grants` | Create audit grant |
| `DELETE /api/v1/audit/grants/{id}` | Revoke audit grant |
| `GET /api/v1/audit/grants/me` | List my audit grants |
| `POST /api/v1/audit/check` | Check audit permissions |
| `POST /api/v1/audit/events` | Record audit event |
| `GET /api/v1/audit/events` | List audit events |
| `GET /api/v1/audit/replay/{task_id}` | Replay audit for task |
| `GET /api/v1/audit/stats` | Get audit statistics |

```
User: Command Palette → "Aegion: Open Audit Log"
      → Opens AuditLogPanel webview
```

---

## 25. ChatOps Integration

Slack and webhook-based notifications.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/chatops/slack/webhook` | Receive Slack webhook |
| `POST /api/v1/chatops/slack/events` | Handle Slack events |
| `GET /api/v1/chatops/slack/install` | Start Slack OAuth install |
| `POST /api/v1/chatops/webhooks/configure` | Configure webhooks |
| `GET /api/v1/chatops/webhooks` | List all webhooks |
| `GET /api/v1/chatops/webhooks/{workspace_id}` | Get workspace webhook |
| `DELETE /api/v1/chatops/webhooks/{workspace_id}` | Remove webhook |
| `POST /api/v1/chatops/notify` | Send notification |
| `GET /api/v1/chatops/notifications/log` | View notification log |

---

## 26. MCP Tool Server

Model Context Protocol tools for AI agent integration.

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/tools` | List available tools |
| `GET /api/v1/tools/{name}` | Get tool details + schema |
| `POST /api/v1/tools/{name}` | Execute a tool |
| `PUT /api/v1/tools/{name}` | Register/update a tool |
| `DELETE /api/v1/tools/{name}` | Unregister a tool |

---

## 27. Terminal & Browser Tools

### 27.1 Terminal

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/terminal/execute` | Execute terminal command |
| `GET /api/v1/terminal/profiles` | List terminal profiles |
| `GET /api/v1/terminal/history` | Get command history |

### 27.2 Browser

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/tools/browser/fetch` | Fetch URL content |
| `POST /api/v1/tools/browser/browse` | Browse and interact |
| `POST /api/v1/tools/browser/extract` | Extract data from page |
| `POST /api/v1/tools/browser/screenshot` | Take screenshot |

---

## 28. AI Commands

Quick AI actions on selected code.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/ai/transform` | Transform/refactor code |
| `POST /api/v1/ai/explain` | Explain code |
| `POST /api/v1/ai/debug` | Debug code issues |

---

## 29. Model Routing

Manage and switch between AI model providers.

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/models` | List available models |
| `GET /api/v1/models/active` | Get active model |
| `PUT /api/v1/models/active` | Switch active model |
| `POST /api/v1/models/register` | Register new model |

---

## 30. Agent Identity & Verification

Cryptographic identity for AI agents operating within governance.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/agents` | Register an agent |
| `GET /api/v1/agents` | List agents |
| `GET /api/v1/agents/{id}` | Get agent details |
| `POST /api/v1/agents/{id}/verify` | Start verification challenge |
| `POST /api/v1/agents/{id}/verify/complete` | Complete verification |
| `POST /api/v1/agents/{id}/claims` | Submit a claim |
| `GET /api/v1/agents/{id}/claims` | List claims |
| `POST /api/v1/agents/{id}/claims/{cid}/verify` | Verify a claim |
| `DELETE /api/v1/agents/{id}` | Remove an agent |

---

## 31. Secrets Vault

Secure secret storage with time-bound access tokens.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/secrets` | Store a secret |
| `GET /api/v1/secrets/{key}/token` | Get time-limited access token |
| `POST /api/v1/secrets/redeem` | Redeem token to retrieve secret |
| `DELETE /api/v1/secrets/{key}` | Delete a secret |

---

## 32. Rejection Learning

When proposals are rejected, the system captures learnings for future reference.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/rejections` | Record rejection artifact |
| `GET /api/v1/rejections/{id}` | Get rejection details |
| `POST /api/v1/rejections/query` | Search rejections |
| `GET /api/v1/rejections/stats/{workspace_id}` | Workspace rejection stats |
| `GET /api/v1/rejections/stats` | Global rejection stats |

---

## 33. Decision Pipelines

Structured, step-by-step decision workflows. **Pipeline state is durably persisted** via `JsonFileStore` (Sprint 21).

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/pipelines` | Create a pipeline |
| `GET /api/v1/pipelines/{id}` | Get pipeline |
| `POST /api/v1/pipelines/{id}/step` | Execute next step |
| `GET /api/v1/pipelines` | List pipelines |
| `GET /api/v1/pipelines/templates/all` | List pipeline templates |

### Pipeline Templates

| Template | Tiers | Steps |
|----------|-------|-------|
| T1 Simple Review | T0, T1 | AI review → auto test |
| T2 Full Review | T2 | AI review → parent escalation → integration test → peer review |
| T3 War Room | T3 | AI council → war room → security audit → perf test → architect sign-off |

---

## 34. Reasoning Chains

Structured reasoning traces for AI transparency.

| Endpoint | Purpose |
|----------|---------|
| Router prefix `/reasoning` | Reasoning chain endpoints |

---

## 35. Admin Dashboard

System administration and monitoring.

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/admin/usage` | Usage statistics |
| `GET /api/v1/admin/policy-dashboard` | Policy compliance stats |
| `GET /api/v1/admin/env` | Get environment config |
| `POST /api/v1/admin/env` | Update environment config |

```
User: Command Palette → "Aegion: Open Admin Dashboard"
      → Opens AdminDashboardPanel webview
```

---

## 36. Event Streaming (SSE)

Server-Sent Events for real-time updates.

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/events/stream/{workspace_id}` | Subscribe to workspace events |
| `POST /api/v1/events/broadcast/{workspace_id}` | Broadcast event to workspace |

---

## 37. WebSocket Real-Time

WebSocket connections for bi-directional real-time communication. **Authentication is now token-based** (Sprint 21).

```mermaid
sequenceDiagram
    participant Client
    participant WS as WebSocket Endpoint
    participant Auth as Auth Config

    Client->>WS: ws://host/ws/{workspace_id}?token=<jwt>
    WS->>Auth: verify_token(token)
    Auth-->>WS: { uid, role }
    alt Token valid
        WS->>WS: Extract user_id from claims
        WS->>WS: Extract role from claims
        WS-->>Client: Connection established
        WS-->>Client: { type: "participants.list", participants: [...] }
    else Token invalid
        WS-->>Client: Close(4001, "Unauthorized: invalid token")
    end
```

**Message Types (Client → Server):**
- `join_session` — Join a governance session
- `leave_session` — Leave current session
- `cursor_update` — Share cursor position
- `state_sync` — Request state synchronization

**Message Types (Server → Client):**
- `participant.joined` — New participant
- `participant.left` — Participant left
- `cursor.updated` — Cursor from another user
- `state.changed` — Session state changed
- `proposal.updated` — Proposal modified

---

## 38. Health & Readiness

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Root-level health check (bypasses SessionGuard) |
| `GET /api/v1/health/...` | API-level health endpoints |

---

## 39. Configuration & Networking

### 39.1 VS Code Settings

```json
{
    "aegion.backendUrl": "http://localhost:8000",
    "aegion.autoStartSession": false,
    "aegion.clientGenerationMode": "automatic-with-review"
}
```

| Setting | Default | Purpose |
|---------|---------|---------|
| `aegion.backendUrl` | `http://localhost:8000` | Backend API server URL |
| `aegion.autoStartSession` | `false` | Auto-start session on workspace open |
| `aegion.clientGenerationMode` | `automatic-with-review` | How API client types are generated |

### 39.2 Backend Configuration

```python
# app/core/config.py
class Settings:
    api_prefix: str = "/api/v1"
    environment: str = "development"
```

### 39.3 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGION_AUTH_ADAPTER` | `firebase` | Auth provider: `firebase`, `jwt`, `mock` |
| `AEGION_JWT_ISSUER` | — | JWT issuer URL (for JWT/OIDC) |
| `AEGION_JWT_AUDIENCE` | `aegion-api` | JWT audience claim |
| `AEGION_JWT_ALGORITHM` | `RS256` | JWT signing algorithm |
| `AEGION_JWKS_URL` | — | JWKS endpoint for key retrieval |
| `AEGION_JWT_SECRET` | — | Shared secret for HS256 |
| `AEGION_REQUIRE_TLS` | `true` | Enforce TLS for auth endpoints |
| `AEGION_DEBUG` | `false` | Enable mock tokens (development only) |
| `AEGION_STORE_BACKEND` | — | Durable store backend selector |

### 39.4 URL Resolution

```
VS Code Extension                              Backend
┌──────────────────────────────────────┐       ┌─────────────────────┐
│ aegion.backendUrl = "http://host:8000"│       │ api_prefix = /api/v1│
│ + Endpoints.sessions.start()         │       │                     │
│ = "/api/v1/sessions/start"           │──────▶│ POST /sessions/start│
│                                      │       │ (under /api/v1)     │
└──────────────────────────────────────┘       └─────────────────────┘
```

---

## 40. Middleware & Guards

### 40.1 SessionGuard Middleware

Every request (except `/health`) requires session headers:

```
X-Aegion-Session: <session-id>
X-Aegion-Intent: <action-intent>
```

### 40.2 Freeze Guard

All mutating endpoints are protected by `guard_writable()`:

```python
if archon._freeze_mode:
    raise GovernanceError("System is in FREEZE mode - mutations blocked")
```

### 40.3 Re-Approval Guard

Proposals cannot be approved twice:

```python
# proposals.py lines 257-264
existing_decisions = await _graph_service.graph.get_edges(...)
if any(e.edge_type == GraphEdgeType.APPROVED_BY for e in existing_decisions):
    raise HTTPException(status_code=409, detail="Proposal already approved")
```

### 40.4 Authentication

Endpoints requiring user context use `Depends(get_current_user)` which returns an `AuthorityContext` with:
- `user_id`
- `role` (Developer, Architect, Admin)
- `permissions` list
- `can_propose_t1`, `can_propose_t2`, `can_approve_t1`, `can_approve_t2`

---

## 41. Authentication & Authorization

> **Added Sprint 12-21**

### 41.1 Multi-Provider Auth

Aegion supports multiple authentication providers via `auth_config.py`:

```mermaid
graph LR
    TOKEN[JWT/Bearer Token] --> VERIFY{verify_token}
    VERIFY -->|AEGION_AUTH_ADAPTER=firebase| FIREBASE[Firebase Admin SDK]
    VERIFY -->|AEGION_AUTH_ADAPTER=jwt| JWT[Generic JWT/OIDC]
    VERIFY -->|AEGION_AUTH_ADAPTER=mock| MOCK["Mock (dev only)"]
    FIREBASE --> CLAIMS[Decoded Claims]
    JWT --> CLAIMS
    MOCK --> CLAIMS
    CLAIMS --> AUTHORITY[AuthorityContext]
```

| Provider | Use Case | Config |
|----------|----------|--------|
| `firebase` | Production (GCP) | Firebase Admin SDK initialized |
| `jwt` | Self-hosted (Auth0, Keycloak) | `AEGION_JWKS_URL` or `AEGION_JWT_SECRET` |
| `mock` | Development only | `AEGION_DEBUG=true`, tokens: `mock-<uid>` |

### 41.2 Authority Model

```python
# Doctrine: "Separate auth from authority"
# Authentication = Identity ("Who is this?")
# Authorization  = Power    ("What can they do?")

class AuthorityContext:
    user_id: str
    role: Role          # ADMIN | ARCHITECT | DEVELOPER | VIEWER
    can_propose_t1: bool
    can_propose_t2: bool
    can_approve_t1: bool
    can_approve_t2: bool
    can_write_memory: bool
    allowed_modules: Set[str]
```

### 41.3 Role Capabilities

| Role | Propose T1 | Propose T2 | Approve T1 | Approve T2 |
|------|-----------|-----------|-----------|-----------|
| Admin | ✅ | ✅ | ✅ | ✅ |
| Architect | ✅ | ✅ | ✅ | ❌ |
| Developer | ✅ | ❌ | ❌ | ❌ |
| Viewer | ❌ | ❌ | ❌ | ❌ |

---

## 42. Knowledge Graph Infrastructure

> **Added Sprint 21**

### 42.1 Shared Graph Provider

**Doctrine**: *"One graph. One truth. All modules speak to the same knowledge base."*

All API modules share a single `InMemoryKnowledgeGraph` instance via `graph_provider.py`:

```python
from app.services.graph_provider import get_shared_graph_service

_graph_service = get_shared_graph_service()  # Same instance everywhere
```

**Modules using shared graph**: proposals, evidence, analytics, sessions, reasoning, architecture

### 42.2 Graph Node Types

| Type | Immutability | Purpose |
|------|-------------|---------|
| `SOURCE` | Mutable | External data sources |
| `EVIDENCE` | **Append-only** | Governance evidence (cannot be updated or deleted) |
| `DECISION` | **Append-only** | Decision records (cannot be updated or deleted) |
| `PROPOSAL` | Mutable | Code change proposals |
| `SESSION` | Mutable | Governance sessions |
| `USER` | Mutable | User identities |
| `WORKSPACE` | Mutable | Workspace containers |
| `REVIEW` | **Append-only** | Peer reviews on proposals |

### 42.3 Graph Edge Types

| Edge | Meaning |
|------|---------|
| `SUPPORTS` | Evidence supports a proposal |
| `PROPOSED_IN` | Proposal created in a session |
| `SUPERSEDES` | Decision supersedes another |
| `CREATED_BY` | Node created by user |
| `APPROVED_BY` | Proposal approved by user |
| `REJECTED_BY` | Proposal rejected by user |
| `REVIEWED_BY` | Review linked to proposal |
| `BELONGS_TO` | Entity belongs to workspace |
| `DEPENDS_ON` | Dependency relationship |
| `RELATED_TO` | General relationship |

---

## 43. Durable Storage & Crash Safety

> **Added Sprint 21**

### 43.1 Architecture

**Doctrine**: *"Data survives crashes. Writes are atomic. Sessions are never lost."*

```mermaid
graph TB
    subgraph "JsonFileStore"
        SAVE[save item] --> DIRTY[Mark dirty]
        DIRTY --> ATOMIC["Atomic Write"]

        subgraph "Atomic Write"
            TEMP[Write to temp file] --> FSYNC[os.fsync]
            FSYNC --> REPLACE[os.replace → target]
        end
    end

    subgraph "Crash Safety"
        SIGNAL["SIGTERM/SIGINT handler"] --> FLUSH[Flush all dirty stores]
        ATEXIT["atexit handler"] --> FLUSH
        TIMER["Auto-flush (30s)"] --> FLUSH
    end
```

### 43.2 Crash Safety Mechanisms

| Mechanism | Trigger | Purpose |
|-----------|---------|---------|
| Atomic writes | Every save | temp-file → `os.fsync()` → `os.replace()` prevents corruption |
| Signal handlers | SIGTERM, SIGINT | Flushes all dirty stores before process exit |
| atexit handler | Clean shutdown | Last-resort save on normal exit |
| Auto-flush | Every 30 seconds | Background task saves dirty stores periodically |
| Dirty tracking | On mutation | Only writes when data actually changed |

### 43.3 Usage

```python
from app.services.durable_store import JsonFileStore

store = JsonFileStore(
    file_path="data/pipelines.json",
    model_class=DecisionPipeline,
    key_field="pipeline_id",
    auto_flush_interval=30.0,
)

await store.save(pipeline)          # Save (marks dirty, writes atomically)
pipeline = await store.get(id)      # Load by key
all_items = await store.list_all()  # Load all
await store.delete(id)              # Remove
await store.flush()                 # Force immediate write
```

### 43.4 Services Using Durable Store

| Service | File | Key Field |
|---------|------|-----------|
| Pipelines | `data/pipelines.json` | `pipeline_id` |
| Sessions/Drafts | `data/drafts.json` | `session_id` |

---

## 44. Observability & Tracing

> **Added Sprint 14-16**

### 44.1 Structured Logging

```python
# app/core/logging.py
logger.audit(
    action="PROPOSAL_APPROVED",
    actor=user_id,
    target=proposal_id,
    justification="T2 evidence requirements met",
    metadata={"tier": "T2", "evidence_count": 3}
)
```

Every governance action emits a structured audit log with: `action`, `actor`, `target`, `justification`, `metadata`, `timestamp`.

### 44.2 Cloud Logging

`app/core/cloud_logging.py` provides Google Cloud Logging integration for production environments.

### 44.3 Metrics

`app/core/metrics.py` exposes Prometheus-compatible metrics:
- Request latency histograms
- Active session gauges
- Proposal/decision counters
- Error rate counters

### 44.4 Distributed Tracing

`app/core/tracing.py` provides OpenTelemetry tracing integration for request correlation across services.

---

## 45. Data Governance & Isolation

> **Added Sprint 17-21**

### 45.1 Workspace Scoping

All entities are scoped to workspaces:
- **Proposals** → `workspace_id` field
- **Decisions** → `workspace_id` field  
- **Incidents** → `workspace_id` field (Sprint 21)
- **Pipelines** → `workspace_id` field
- **Evidence** → Scoped via proposal linkage

### 45.2 Immutability Doctrine

The following entities are **append-only** in the knowledge graph:

| Entity | Can Create | Can Update | Can Delete |
|--------|-----------|-----------|-----------|
| Evidence | ✅ | ❌ `ValueError` | ❌ `ValueError` |
| Decision | ✅ | ❌ `ValueError` | ❌ `ValueError` |
| Review | ✅ | ❌ | ❌ |
| Proposal | ✅ | ✅ (status only) | ❌ |
| Session | ✅ | ✅ | ❌ |

### 45.3 Security Invariants

| Invariant | Enforcement | Location |
|-----------|------------|----------|
| No client evidence injection | Graph-validated IDs only | `proposals.py:265-284` |
| No duplicate approvals | 409 on re-approval | `proposals.py:257-264` |
| No mutations during freeze | `guard_writable()` | 12 endpoints across 5 files |
| No duplicate node IDs | ValueError on collision | `memory_graph.py:48-52` |
| WebSocket requires auth token | 4001 close on invalid | `websocket.py:210-222` |

---

## Complete Command Reference

| VS Code Command | Action |
|-----------------|--------|
| `aegion.startSession` | Start governed session |
| `aegion.closeSession` | Close session (with/without distillation) |
| `aegion.showSessionMenu` | Quick session actions menu |
| `aegion.createProposal` | Create governance proposal |
| `aegion.invokeCouncil` | Ask AI Council |
| `aegion.approveProposal` | Approve a proposal |
| `aegion.rejectDecision` | Reject a proposal |
| `aegion.supersedeDecision` | Supersede a decision |
| `aegion.generateADR` | Generate ADR from decision |
| `aegion.queryMemory` | Search Chronos memory |
| `aegion.showGovernancePolicy` | View governance policy |
| `aegion.setRole` | Set user role |
| `aegion.openDashboard` | Open main dashboard |
| `aegion.openGovernanceCenter` | Open Archon governance UI |
| `aegion.openSessionExplorer` | Open session explorer |
| `aegion.openSystemHealth` | Open health/failure mode panel |
| `aegion.openObservability` | Open risk observatory |
| `aegion.openTimeline` | Open architecture timeline |
| `aegion.openTaskInbox` | Open task inbox |
| `aegion.openCheckpoints` | Open checkpoints panel |
| `aegion.openMemoryRules` | Open memory & rules panel |
| `aegion.openSkillCatalog` | Open skill catalog |
| `aegion.openCollaboration` | Open collaboration panel |
| `aegion.openWarRoom` | Open war room |
| `aegion.openCloudDelegate` | Open cloud delegation |
| `aegion.openAuditLog` | Open audit log viewer |
| `aegion.openAdminDashboard` | Open admin dashboard |
| `aegion.openMultiFileReview` | Open multi-file review |
| `aegion.showADRGraph` | Show ADR graph |
| `aegion.chronos.refresh` | Refresh Chronos explorer |
| `aegion.sentinel.refresh` | Refresh Sentinel explorer |
| `aegion.navigateConcept` | Navigate evidence graph concepts |

---

## End-to-End Example: Full Governance Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Ext as VS Code Extension
    participant BE as Backend
    participant Archon as Archon
    participant Graph as Knowledge Graph

    Dev->>Ext: Start Session
    Ext->>BE: POST /sessions/start
    BE-->>Ext: session_id = "s-123"

    Dev->>Ext: Create Proposal "Add auth module"
    Ext->>BE: POST /proposals { impact: cross_module }
    BE->>Archon: classify → T2
    BE->>Graph: add_node(PROPOSAL) + add_edge(PROPOSED_IN)
    BE-->>Ext: proposal "p-456" (T2)

    Dev->>Ext: Submit Evidence (test results)
    Ext->>BE: POST /evidence/submit { proposal_id: "p-456" }
    BE->>Graph: add_node(EVIDENCE, immutable) + add_edge(SUPPORTS)
    BE-->>Ext: evidence "e-789" (immutable)

    Dev->>Ext: Invoke Council "How to implement?"
    Ext->>BE: POST /council/stream
    BE-->>Ext: SSE chunks with code suggestion

    Dev->>Ext: Show Diff → Reviews AI code

    Dev->>Ext: Submit Review
    Ext->>BE: POST /proposals/p-456/review
    BE->>Graph: add_node(REVIEW) + add_edge(REVIEWED_BY)
    BE-->>Ext: review "rev-abc" persisted

    Dev->>Ext: Approve Proposal
    Ext->>BE: POST /proposals/p-456/approve
    BE->>BE: Re-approval guard (409 if already approved)
    BE->>Archon: validate(T2 authority + evidence required)
    BE->>Graph: Fetch validated evidence_nodes
    Note over BE: Uses graph evidence IDs only<br/>Never trusts client input
    BE->>Graph: add_node(DECISION) + link evidence
    Archon-->>BE: ✅ Approved
    BE-->>Ext: decision_id = "d-321"

    Dev->>Ext: Generate ADR
    Ext->>BE: POST /architecture/adrs
    BE-->>Ext: ADR markdown document

    Dev->>Ext: Close Session (distill)
    Ext->>BE: POST /sessions/s-123/close
    BE-->>Ext: Artifacts distilled to memory
```
