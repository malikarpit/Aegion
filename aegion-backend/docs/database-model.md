# Aegion Database & Storage Model

## Storage Architecture

Aegion uses a polyglot persistence strategy — different storage engines for different data shapes.

```
┌─────────────────────────────────────────────────────────────┐
│                     Storage Layer                            │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  Firestore   │   Neo4j      │   GCS        │  File/Memory   │
│  (Documents) │   (Graph)    │  (Blobs)     │  (Local Dev)   │
├──────────────┼──────────────┼──────────────┼────────────────┤
│ Users        │ Evidence     │ ADR docs     │ Sessions       │
│ Workspaces   │ Decisions    │ Artifacts    │ Drafts         │
│ Memberships  │ Proposals    │ Snapshots    │ Config         │
│ Presence     │ Dependencies │ Attachments  │ Audit chain    │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

## Adapter Pattern

All storage access is through ports (interfaces):

| Port | Production Adapter | Dev Adapter |
|---|---|---|
| `KnowledgeGraphPort` | `Neo4jKnowledgeGraph` | `InMemoryKnowledgeGraph` |
| `WorkspaceRepository` | `FirestoreWorkspaceRepository` | `InMemoryWorkspaceRepo` |
| Storage | `GCSStorage` | `FileSystemStorage` |
| Events | `KafkaEventBus` | `InProcessEventBus` |

## Neo4j Graph Schema

### Node Types
| Type | Properties | Purpose |
|---|---|---|
| `SOURCE` | path, content_hash, workspace_id | Code files, configs |
| `EVIDENCE` | type, content_hash, workspace_id, timestamp | Test results, metrics |
| `DECISION` | proposal_id, workspace_id, decided_at, verdict | Approval records |
| `PROPOSAL` | title, tier, status, session_id, origin | Change proposals |
| `ARTIFACT` | type, version, created_at | Generated documents |

### Edge Types
| Type | Semantics |
|---|---|
| `DEPENDS_ON` | Source A requires Source B |
| `SUPPORTS` | Evidence supports Decision |
| `SUPERSEDES` | Newer Decision replaces older |
| `APPROVED_BY` | Decision approved by User |
| `PRODUCED_BY` | Artifact produced by Session |

## Transaction Model

| Operation | Isolation | Consistency |
|---|---|---|
| Node creation | Atomic (single node) | Strong |
| Edge creation | Atomic (single edge) | Strong |
| Decision recording | Multi-operation (node + edges) | Eventual within request |
| Graph queries | Read-committed | Eventual |

## Migration Strategy

1. **Schema evolution**: New node/edge types added via code. No DDL migrations needed for Neo4j.
2. **Data migration**: Python migration scripts in `scripts/migrations/`.
3. **Backward compatibility**: New fields added with defaults. Old data remains valid.
4. **Blue-green deploys**: Both schema versions coexist during transition.

## Concurrency

- **Graph writes**: Protected by `guard_writable()` (freeze prevents all writes)
- **Evidence nodes**: Append-only (no update/delete) — no conflicts possible
- **Decisions**: Idempotent creation with duplicate check (409 Conflict)
- **Sessions**: Per-session isolation (workspace_id partitioning)

## Backup & Recovery

| Component | Strategy | Frequency |
|---|---|---|
| Neo4j | `neo4j-admin dump` + GCS upload | Daily |
| Firestore | Automated GCP backups | Continuous |
| GCS | Cross-region replication | Built-in |
| Audit chain | Hash-verified restore | On-demand |
