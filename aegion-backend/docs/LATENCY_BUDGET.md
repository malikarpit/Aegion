# Aegion Latency Budget — Phase 114

## Overview

This document defines the target latency budgets for every operation in the
Aegion system. All latency numbers are **p95** (95th percentile) targets.

## Ghost Text (Inline Completions)

| Stage | Target | Notes |
|---|---|---|
| VS Code keypress → backend | 50ms | WebSocket already open |
| Semantic cache check (pgvector) | 15ms | Cosine similarity on 768-dim vectors |
| Ollama local fast-path | 100ms | codellama:7b, zero cost |
| Cloud cascade Tier 0 (DeepSeek/Gemini Flash) | 300ms | Cheapest cloud model |
| Cloud cascade Tier 1 (GPT-4o-mini) | 500ms | Balanced fallback |
| **Total (local hit)** | **~165ms** | Cache hit or Ollama |
| **Total (cloud, Tier 0)** | **~365ms** | Semantic cache miss |
| **Total (cloud, Tier 1)** | **~565ms** | Tier 0 confidence < 0.75 |

## Child Council (Single-Pass)

| Stage | Target | Notes |
|---|---|---|
| Semantic cache check | 15ms | pgvector cosine lookup |
| Complexity classification | 5ms | Heuristic + gateway |
| FrugalGPT cascade T0 | 400ms | DeepSeek Chat |
| FrugalGPT cascade T1 | 800ms | GPT-4o-mini |
| FrugalGPT cascade T2 | 1500ms | Claude Sonnet / GPT-4o |
| **Total (cache hit)** | **~20ms** | |
| **Total (T0 hit)** | **~420ms** | Most common path |
| **Total (T1 escalation)** | **~1.2s** | Low-confidence T0 |

## Parent Council (Full Debate)

| Stage | Target | Notes |
|---|---|---|
| Context gathering (parallel) | 200ms | Constitution + evidence + temporal |
| Model selection | 10ms | ModelRouter.select_models() |
| Parallel model queries (3 models) | 2000ms | Slowest model wins |
| Persona debate (1 round) | 1500ms | 4 personas in parallel |
| Peer review (3-stage) | 3000ms | Sequential: claim→challenge→synthesis |
| Rubric scoring | 500ms | LLM-graded eval |
| Consensus synthesis | 800ms | Weighted merge |
| Red team validation (optional) | 1500ms | Adversarial check |
| **Total (T2, 2 rounds)** | **~8-10s** | |
| **Total (T3, 3 rounds)** | **~12-15s** | Full critical review |

## Dashboard API Endpoints

| Endpoint | Target | Notes |
|---|---|---|
| `GET /health` | 50ms | Simple healthcheck |
| `GET /dashboard/kpi` | 200ms | Aggregated metrics |
| `GET /knowledge/search` | 300ms | pgvector semantic search |
| `POST /council/invoke` | Streaming | First byte < 500ms |
| `POST /council/stream` (SSE) | First event < 1s | debate.started event |
| `GET /cost/summary` | 150ms | Cost aggregation query |
| `POST /ws/ticket` | 100ms | WebSocket ticket generation |

## WebSocket Operations

| Operation | Target | Notes |
|---|---|---|
| Ticket exchange | 30ms | Token validation + session init |
| Ghost text request | Ghost text latency above | Routed through WS |
| Session event push | 10ms | Server → client notification |
| Heartbeat interval | 30s | Connection keepalive |

## Frontend Rendering Targets

| Operation | Target | Notes |
|---|---|---|
| Dashboard initial render | 200ms | After JS hydration |
| Council opinion render | 50ms | Each SSE event → DOM update |
| Knowledge graph visualization | 500ms | D3/WebGL force graph |
| Settings page load | 100ms | Static form |

## Optimization Levers

1. **Semantic Cache** — Eliminates ~40% of LLM calls at 0 latency
2. **Ollama Fast-Path** — Local inference at ~100ms, zero cost
3. **FrugalGPT Cascade** — Cheapest model first, only escalate if needed
4. **DAG Pipeline** — Parallel context gathering (constitution + evidence + temporal)
5. **pgvector Index** — HNSW index for sub-20ms vector searches
6. **Connection Pooling** — Reuse httpx clients per provider
7. **Context Pruning** — Reduces token count → faster LLM responses
