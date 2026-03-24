# AEGION — Master Remaining Work Checklist
> **Purpose**: Single source of truth for all remaining work. Chronological build order. References detail docs.  
> **Last Updated**: 2026-03-24  
> **Status**: ~20-25% complete overall | ~162 days remaining

---

## How to Use
- Work through blocks **in order** — each block depends on the previous
- Every item links to the primary reference document for implementation details
- `[ ]` = not started | `[/]` = in progress | `[x]` = complete
- Detailed steps, SQL, code, acceptance criteria → [`MASTER_WORK_PLAN.md`](./MASTER_WORK_PLAN.md)
- ACK architecture → [`COUNCIL_KERNEL_ARCHITECTURE.md`](./COUNCIL_KERNEL_ARCHITECTURE.md)
- Cost strategies → [`COST_OPTIMIZATION_STRATEGY.md`](./COST_OPTIMIZATION_STRATEGY.md)
- Current completion state → [`completion_audit_report.md`](./completion_audit_report.md)
- Work already done → [`PROGRESS_REPORT.md`](./PROGRESS_REPORT.md)

---

## ⚠️ Critical Blockers (Must Do Before Anything Else)
> Nothing in Blocks 2–14 is production-usable until these are done.

- [x] **[Ph 1]** Git hygiene — clean commit, branching strategy → [`MASTER_WORK_PLAN.md § Phase 1`](./MASTER_WORK_PLAN.md)
- [x] **[Ph 2]** GCP Cloud Run deployment + Firebase Hosting → [`MASTER_WORK_PLAN.md § Phase 2`](./MASTER_WORK_PLAN.md)
- [x] **[Ph 3]** Supabase setup + pgvector + core SQL schema (workspaces, users, sessions, proposals, decisions, knowledge nodes, timeline events, audit log, memories, rules) → [`MASTER_WORK_PLAN.md § Phase 3`](./MASTER_WORK_PLAN.md)
- [x] **[Ph 4]** Firebase Auth hardening — token revocation enforcement, signing key hardening, SQL safety, frontend/extension lifecycle → [`MASTER_WORK_PLAN.md § Phase 4`](./MASTER_WORK_PLAN.md)
- [x] **[Ph 5]** Durable Store → PostgreSQL migration (replace all in-memory/Firestore) → [`MASTER_WORK_PLAN.md § Phase 5`](./MASTER_WORK_PLAN.md)
- [x] **[Ph 6]** Knowledge Graph → PostgreSQL migration (replace NetworkX/in-memory graph) → [`MASTER_WORK_PLAN.md § Phase 6`](./MASTER_WORK_PLAN.md)
- [x] **[Ph 7]** Session Manager hardening — persistence, recovery, workspace isolation → [`MASTER_WORK_PLAN.md § Phase 7`](./MASTER_WORK_PLAN.md)

---

## Block 1 — Core ACK Council Kernel (Phases 8–18)
> Reference: [`MASTER_WORK_PLAN.md § Phases 8-18`](./MASTER_WORK_PLAN.md) | [`COUNCIL_KERNEL_ARCHITECTURE.md`](./COUNCIL_KERNEL_ARCHITECTURE.md)

- [ ] **[Ph 8]** Council Service — Core Engine (replace v1 with ACK architecture)
- [ ] **[Ph 9]** Model Router & Provider Abstraction (multi-provider interface)
- [ ] **[Ph 10]** LLM Cascade / FrugalGPT (cost-first model fallback chain)
- [ ] **[Ph 11]** Semantic Cache Layer (pgvector-based prompt deduplication)
- [ ] **[Ph 12]** Prompt Compression Integration (LLMLingua-2)
- [ ] **[Ph 13]** Peer Review Engine (expert panel, rubric scoring)
- [ ] **[Ph 14]** Debate Engine (anti-sycophancy, devil's advocate)
- [ ] **[Ph 15]** Rubric Evaluation Engine (structured scoring)
- [ ] **[Ph 16]** Persona Engine (role-specific context injection)
- [ ] **[Ph 17]** Evidence Manager (attach, validate, link evidence to proposals)
- [ ] **[Ph 18]** Council Kernel Integration (wire all ACK components together)

---

## Block 2 — Cost Optimization Layer (Phases 76–83)
> Reference: [`MASTER_WORK_PLAN.md § Phases 76-83`](./MASTER_WORK_PLAN.md) | [`COST_OPTIMIZATION_STRATEGY.md`](./COST_OPTIMIZATION_STRATEGY.md)  
> **Build immediately after Block 1** — plugs into kernel before governance is built

- [ ] **[Ph 76]** Prompt Gateway & Intent Clarification Layer
- [ ] **[Ph 77]** Adaptive Council Size & Smart Routing
- [ ] **[Ph 78]** Output Token Budgeting & Dynamic Limits
- [ ] **[Ph 79]** Context Window Pruning & History Compression
- [ ] **[Ph 80]** Early Consensus Detection & Round Optimization
- [ ] **[Ph 81]** Speculative Decoding (Draft-Verify Pattern)
- [ ] **[Ph 82]** Batch Deferred Processing
- [ ] **[Ph 83]** RAG-Enhanced Council Prompts

---

## Block 3 — Model Settings Backend (Phase 84)
> Reference: [`MASTER_WORK_PLAN.md § Phase 84`](./MASTER_WORK_PLAN.md) | [`COST_OPTIMIZATION_STRATEGY.md`](./COST_OPTIMIZATION_STRATEGY.md)

- [ ] **[Ph 84]** Model Settings Engine — backend API, DB schema, preset system, budget controls, user overrides

---

## Block 4 — Governance Hardening (Phases 19–23)
> Reference: [`MASTER_WORK_PLAN.md § Phases 19-23`](./MASTER_WORK_PLAN.md) | [`docs before 13 march/03-Governance-Model.md`](./docs%20before%2013%20march/03-Governance-Model.md)

- [ ] **[Ph 19]** Archon Governance — Tier System (T0-T3 classification, quorum rules wired to real DB)
- [ ] **[Ph 20]** Archon — Freeze Mode & Policy Engine (emergency locks, policy pack loading)
- [ ] **[Ph 21]** Sentinel — Risk Scoring Engine (wired to real PostgreSQL signals table)
- [ ] **[Ph 22]** Sentinel — Drift Detection (diff codebase vs approved decisions)
- [ ] **[Ph 23]** Sentinel — Security Council (automated security review gate)

---

## Block 5 — Intelligence & Memory (Phases 24–29)
> Reference: [`MASTER_WORK_PLAN.md § Phases 24-29`](./MASTER_WORK_PLAN.md) | [`docs before 13 march/02-Architecture.md`](./docs%20before%2013%20march/02-Architecture.md)

- [ ] **[Ph 24]** Noesis — Cognitive Analytics (real graph queries, workspace topology)
- [ ] **[Ph 25]** Ghost Text — AI Completions (inline code suggestion in VS Code)
- [ ] **[Ph 26]** Chronos — Timeline & Event Sourcing (wired to `timeline_events` PostgreSQL table)
- [ ] **[Ph 27]** Chronos — Immutable Decision Records (lineage hash chain)
- [ ] **[Ph 28]** Praxis — Sandbox Hardening (seccomp, network policy enforcement)
- [ ] **[Ph 29]** Memory & Rules Engine (memories table + rule evaluation pipeline)

---

## Block 6 — Platform Services (Phases 30–32)
> Reference: [`MASTER_WORK_PLAN.md § Phases 30-32`](./MASTER_WORK_PLAN.md)

- [ ] **[Ph 30]** Skills System (skill registry, invocation, result capture)
- [ ] **[Ph 31]** Task Management System (task trees, status tracking, CRUD wired to DB)
- [ ] **[Ph 32]** Checkpoints & Recovery (snapshot state, restore on crash)

---

## Block 7 — Collaboration (Phases 33–34)
> Reference: [`MASTER_WORK_PLAN.md § Phases 33-34`](./MASTER_WORK_PLAN.md) | [`docs before 13 march/PRODUCT_SPEC.md`](./docs%20before%2013%20march/PRODUCT_SPEC.md)

- [ ] **[Ph 33]** Collaboration — Real-time Presence (WebSocket cursors, session participants, Supabase Realtime)
- [ ] **[Ph 34]** War Room — Incident Management (multi-player conflict resolution workspace)

---

## Block 8 — Code Review & Security (Phases 35–38)
> Reference: [`MASTER_WORK_PLAN.md § Phases 35-38`](./MASTER_WORK_PLAN.md)

- [ ] **[Ph 35]** Diff Review System (structured code review, inline comments, decisions from diffs)
- [ ] **[Ph 36]** Audit Trail & Compliance (complete audit_log wiring, OPA policy checks, Merkle chain)
- [ ] **[Ph 37]** Agent Identity & Zero Trust (mTLS, workspace-scoped tokens, identity verification)
- [ ] **[Ph 38]** Secrets Vault (encrypted key storage, per-user LLM API keys)

---

## Block 9 — Integrations & Agents (Phases 39–42)
> Reference: [`MASTER_WORK_PLAN.md § Phases 39-42`](./MASTER_WORK_PLAN.md)

- [ ] **[Ph 39]** ChatOps Integration (Slack/Teams webhooks, command parsing)
- [ ] **[Ph 40]** MCP Server & Tools (Model Context Protocol, tool registration)
- [ ] **[Ph 41]** Terminal & Browser Agents (shell execution, browser automation agents)
- [ ] **[Ph 42]** AI Commands Engine (slash commands, intent parsing, command execution)

---

## Block 10 — Advanced Intelligence (Phases 43–45)
> Reference: [`MASTER_WORK_PLAN.md § Phases 43-45`](./MASTER_WORK_PLAN.md)

- [ ] **[Ph 43]** Rejection Learning System (learn from rejected proposals, improve suggestions)
- [ ] **[Ph 44]** Decision Pipelines (multi-step decision workflows, branching)
- [ ] **[Ph 45]** Reasoning Chains (chain-of-thought capture, reasoning graph)

---

## Block 11 — Advanced ACK (Phases 46–51)
> Reference: [`MASTER_WORK_PLAN.md § Phases 46-51`](./MASTER_WORK_PLAN.md) | [`COUNCIL_KERNEL_ARCHITECTURE.md`](./COUNCIL_KERNEL_ARCHITECTURE.md)

- [ ] **[Ph 46]** Constitutional AI Layer (hard invariants, values-based rejection)
- [ ] **[Ph 47]** Cognitive Reflector (self-critique loop, confidence calibration)
- [ ] **[Ph 48]** Red Team Layer (adversarial challenge agent, stress testing proposals)
- [ ] **[Ph 49]** Temporal Council Memory (council learns from past sessions)
- [ ] **[Ph 50]** Cross-Council Orchestration (multi-council hierarchy, delegation)
- [ ] **[Ph 51]** Council Analytics Engine (council performance metrics, bias detection)

---

## Block 12 — VS Code Extension (Phases 52–56)
> Reference: [`MASTER_WORK_PLAN.md § Phases 52-56`](./MASTER_WORK_PLAN.md)

- [ ] **[Ph 52]** VS Code Extension — Auth & Connection (Supabase Auth, API key management in keychain)
- [ ] **[Ph 53]** VS Code Extension — TreeView Providers (Sessions, Proposals, Decisions panels)
- [ ] **[Ph 54]** VS Code Extension — Ghost Text Provider (inline AI completions, context-aware)
- [ ] **[Ph 55]** VS Code Extension — Commands & Webviews (all commands, sidebar webview panels)
- [ ] **[Ph 56]** VS Code Extension — Testing (unit tests, E2E mock server tests)

---

## Block 13 — Model Settings Surfaces (Phases 85–86)
> Reference: [`MASTER_WORK_PLAN.md § Phases 85-86`](./MASTER_WORK_PLAN.md) | [`COST_OPTIMIZATION_STRATEGY.md`](./COST_OPTIMIZATION_STRATEGY.md)

- [ ] **[Ph 85]** Model Settings Dashboard — Frontend (preset cards, budget display, per-model sliders)
- [ ] **[Ph 86]** Model Settings Panel — VS Code Extension (preset picker, status bar, quick switch)

---

## Block 14 — Frontend Dashboard (Phases 57–68)
> Reference: [`MASTER_WORK_PLAN.md § Phases 57-68`](./MASTER_WORK_PLAN.md)

- [ ] **[Ph 57]** Frontend — Project Setup & Design System (Tailwind/CSS tokens, typography, component library)
- [ ] **[Ph 58]** Frontend — Authentication Pages (login, signup, OAuth, invite flow)
- [ ] **[Ph 59]** Frontend — Dashboard Overview (workspace summary, activity feed, metrics cards)
- [ ] **[Ph 60]** Frontend — Timeline Page (Chronos event stream, filter, time-travel UI)
- [ ] **[Ph 61]** Frontend — Council Console (live council sessions, debate view, voting UI)
- [ ] **[Ph 62]** Frontend — Proposals & Decisions (proposal list, detail view, decision lineage)
- [ ] **[Ph 63]** Frontend — Settings & API Keys (user preferences, LLM key management, RBAC)
- [ ] **[Ph 64]** Frontend — Knowledge Graph Visualizer (interactive D3/Cytoscape graph)
- [ ] **[Ph 65]** Frontend — ADR Management (create, browse, link ADRs to decisions)
- [ ] **[Ph 66]** Frontend — Cost Dashboard (token spend, budget bars, provider breakdown)
- [ ] **[Ph 67]** Frontend — Memory & Skills Pages (memory browser, skill registry)
- [ ] **[Ph 68]** Frontend — Responsive & Polish (mobile breakpoints, animations, accessibility)

---

## Block 15 — Testing (Phases 69–71)
> Reference: [`MASTER_WORK_PLAN.md § Phases 69-71`](./MASTER_WORK_PLAN.md)

- [ ] **[Ph 69]** Backend Unit Tests (90%+ coverage — all services, ports, adapters; replace mocks with real adapters)
- [ ] **[Ph 70]** Frontend Tests (Playwright/Vitest — page renders, form flows, API mocking)
- [ ] **[Ph 71]** E2E & Load Tests (Prometheus Incident E2E with real Supabase; k6 load test to 100 RPS)

---

## Block 16 — DevOps & Infrastructure (Phases 72–74)
> Reference: [`MASTER_WORK_PLAN.md § Phases 72-74`](./MASTER_WORK_PLAN.md)

- [ ] **[Ph 72]** Docker & Local Dev (production-grade docker-compose, health checks, seed data)
- [ ] **[Ph 73]** GCP Cloud Run Deployment — CI/CD (GitHub Actions → Cloud Build → Cloud Run auto-deploy)
- [ ] **[Ph 74]** Monitoring & Alerting (GCP Cloud Monitoring dashboards, uptime alerts, error budget SLOs)

---

## Block 17 — Launch (Phase 75)
> Reference: [`MASTER_WORK_PLAN.md § Phase 75`](./MASTER_WORK_PLAN.md)

- [ ] **[Ph 75.1]** Full documentation review & update (README, API docs, architecture diagrams)
- [ ] **[Ph 75.2]** VS Code Marketplace listing (extension icon, description, screenshots, publisher account)
- [ ] **[Ph 75.3]** Final QA pass (smoke test all acceptance criteria across all 74 phases)
- [ ] **[Ph 75.4]** Public launch (publish extension, deploy production, announce)

---

## Estimated Remaining Timeline

| Block | Phases | Days |
|-------|--------|------|
| Critical Blockers | 1–7 | ~18 |
| Core ACK Council Kernel | 8–18 | ~25 |
| Cost Optimization | 76–83 | ~15 |
| Model Settings Backend | 84 | ~3 |
| Governance Hardening | 19–23 | ~14 |
| Intelligence & Memory | 24–29 | ~15 |
| Platform Services | 30–32 | ~6 |
| Collaboration | 33–34 | ~5 |
| Code Review & Security | 35–38 | ~6 |
| Integrations & Agents | 39–42 | ~8 |
| Advanced Intelligence | 43–45 | ~6 |
| Advanced ACK | 46–51 | ~12 |
| VS Code Extension | 52–56 | ~15 |
| Model Settings Surfaces | 85–86 | ~5 |
| Frontend Dashboard | 57–68 | ~25 |
| Testing | 69–71 | ~8 |
| DevOps & Infrastructure | 72–74 | ~6 |
| Launch | 75 | ~5 |
| **TOTAL REMAINING** | **~162 days** | |

---

*Reference documents: [`MASTER_WORK_PLAN.md`](./MASTER_WORK_PLAN.md) | [`COUNCIL_KERNEL_ARCHITECTURE.md`](./COUNCIL_KERNEL_ARCHITECTURE.md) | [`COST_OPTIMIZATION_STRATEGY.md`](./COST_OPTIMIZATION_STRATEGY.md) | [`PROGRESS_REPORT.md`](./PROGRESS_REPORT.md) | [`completion_audit_report.md`](./completion_audit_report.md)*
