# Database Migration Strategy: Aegion

> Current: JSON Files (Local/S3)
> Target: PostgreSQL (Managed RDS/Aurora)

## 1. Why Migration?

- **ACID Transactions**: Required for complex multi-step governance proposals.
- **Relational Integrity**: Foreign keys for `User` -> `Workspace` -> `Proposal`.
- **Query Performance**: Indexing for identifying "all proposals needing my review".
- **Row-Level Security (RLS)**: Native enforcement of workspace isolation.

## 2. Schema Mapping

| Entity | JSON Path | Postgres Table | Keys |
|---|---|---|---|
| Workspace | `workspaces/*.json` | `workspaces` | `id` (PK), `owner_id` (FK) |
| User | `users/*.json` | `users` | `id` (PK), `workspace_id` (FK) |
| Proposal | `proposals/*.json` | `proposals` | `id` (PK), `creator_id` (FK) |
| Vote | `proposals/*.json` | `votes` | `proposal_id` (FK), `voter_id` (FK) |
| Audit | `audit/*.log` | `audit_log` | `id` (PK), `chain_hash` (Unique) |

## 3. Migration Procedure

### Phase 1: Schema Setup
1. Define SQLAlchemy / SQLModel models.
2. Generate Alembic migrations.
3. Apply schema to production DB.

### Phase 2: Online Data Migration
1. **Stop Writes**: Enable `FREEZE_ALL_WORKSPACES` (Maintenance Mode).
2. **Snapshot**: Backup all JSON files.
3. **ETL Script**:
   - Parse JSON.
   - Validate integrity.
   - Bulk insert into Postgres (using `COPY`).
   - Verify row counts.
4. **Switchover**: Update `DB_BACKEND=postgres`.
5. **Resume**: Disable freeze.

### Phase 3: Rollback Plan
If Postgres fails:
1. Revert `DB_BACKEND=json`.
2. Restore JSON snapshot (data written to Postgres during outage is lost/manually reconciled).

## 4. Encryption & Security

- **At Rest**: RDS AES-256 encryption.
- **In Transit**: TLS 1.3 enforced.
- **Credentials**: Stored in AWS Secrets Manager / Vault.
- **RLS**: Postgres Row-Level Security policies enforcing `workspace_id` tenant isolation.

## 5. Backup Strategy

- **Point-in-Time Recovery (PITR)**: 35-day retention.
- **Cross-Region Replication**: Disaster recovery.
- **Snapshot Export**: Daily export to S3 (encrypted) for long-term compliance.
