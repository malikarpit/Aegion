# ADR 001: Data Foundation Storage & Integrity

**Date:** 2026-02-14
**Status:** PROPOSED

## Context
Aegion requires a durable, replayable, and workspace-safe state management system. In Phase 0, we relied on in-memory structures or ad-hoc file storage. To support "Team Mode" and ensure auditability, we must formalize the storage architecture.

## Decision

### 1. Canonical Source of Truth
The **Event Log** is the single source of truth.
- All state changes (decisions, proposals, evidence) MUST be recorded as immutable events.
- Projections (e.g., current decision list, graph topology) are derived from the Event Log.
- If a projection and the Event Log disagree, the Event Log is correct.

### 2. Storage Modes
We support two distinct storage modes to accommodate individual developers and teams:

| Feature | Local Mode (Personal) | Team Mode (Production) |
| :--- | :--- | :--- |
| **Event Store** | `SQLite` or Append-only `JSONL` file | `PostgreSQL` or `Firestore` |
| **Graph DB** | In-memory `NetworkX` (persisted to file) | `Neo4j` or `ArangoDB` |
| **Artifacts** | Local filesystem (`.aegion/`) | `S3` / `GCS` buckets |
| **Auth** | Local mock / env vars | `Firebase` / `OIDC` |

### 3. Identity & Metadata Schema
All events and entities must adhere to the following schema to ensure traceability across distributed components.

#### Standard IDs
- **`workspace_id`**: Tenant identifier. UUID.
- **`actor_id`**: User or Agent initiating the action. Format: `user|{uid}` or `agent|{agent_name}`.
- **`correlation_id`**: Trace ID for a request chain. Propagated via `X-Correlation-ID`.
- **`causation_id`**: The ID of the event that *caused* this new event (for causality chains).

#### Event Structure
```json
{
  "event_id": "evt_...",       // ULID (Time-sortable)
  "event_type": "decision.proposed",
  "workspace_id": "ws_...",
  "actor_id": "user|arpit",
  "data": { ... },
  "metadata": {
    "correlation_id": "corr_...",
    "causation_id": "evt_prev...",
    "timestamp": "ISO8601",
    "version": 1
  },
  "hash": "sha256(content)"   // Tamper-evidence
}
```

## Consequences
- **Positive**:
    - Replayability is guaranteed by design.
    - "Time Travel" debugging becomes possible by replaying up to a specific timestamp.
    - Clear separation between "my machine" and "prod" makes local dev fast.
- **Negative**:
    - Querying current state requires re-projection or keeping a read-model in sync.
    - Initial implementation overhead for the dual-adapter pattern.

## Compliance
- All backend services must accept `STORAGE_MODE` config.
- All API writes must return the `event_id` generated.
