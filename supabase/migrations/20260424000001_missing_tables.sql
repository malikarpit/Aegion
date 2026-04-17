-- ════════════════════════════════════════════════════════════════════════════
-- Aegion — Missing Table Reconciliation Migration
-- Version: 20260424000001
--
-- Ports tables that existed only in aegion-backend/migrations/ into the
-- canonical supabase/migrations/ directory.
--
-- Tables ported:
--   1. batch_queue            — Deferred query queue (batch_processor.py)
--   2. task_runs              — Task execution log (tasks.py)
--   3. constitutional_rules   — Governance rule store (constitution.py)
--   4. presence               — User presence tracking (presence.py)
--   5. incidents              — War room incidents (warroom.py)
--   6. collaboration_state    — Session collaboration state (collaboration.py)
--
-- All tables use IF NOT EXISTS for idempotency.
-- ════════════════════════════════════════════════════════════════════════════

-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │ 1. BATCH QUEUE                                                          │
-- │    Used by: batch_processor.py, api/v1/batch.py                        │
-- └──────────────────────────────────────────────────────────────────────────┘

CREATE TABLE IF NOT EXISTS batch_queue (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     TEXT NOT NULL,
    query            TEXT NOT NULL,
    priority         TEXT NOT NULL DEFAULT 'deferred',
    status           TEXT NOT NULL DEFAULT 'queued',
    metadata         JSONB DEFAULT '{}',
    result           JSONB,
    error            TEXT,
    scheduled_after  TIMESTAMPTZ NOT NULL,
    created_at       TIMESTAMPTZ DEFAULT now(),
    completed_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_batch_queue_ready
    ON batch_queue(status, scheduled_after)
    WHERE status = 'queued';

CREATE INDEX IF NOT EXISTS idx_batch_queue_workspace
    ON batch_queue(workspace_id, created_at DESC);

-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │ 2. TASK RUNS                                                            │
-- │    Used by: api/v1/tasks.py                                             │
-- └──────────────────────────────────────────────────────────────────────────┘

CREATE TABLE IF NOT EXISTS task_runs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id          UUID NOT NULL,
    workspace_id     TEXT NOT NULL,
    status           TEXT DEFAULT 'pending',
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    result           JSONB,
    error            TEXT,
    duration_ms      INT,
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_task_runs_task
    ON task_runs(task_id);

CREATE INDEX IF NOT EXISTS idx_task_runs_workspace_status
    ON task_runs(workspace_id, status);

-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │ 3. CONSTITUTIONAL RULES                                                 │
-- │    Used by: council_kernel/constitution.py                               │
-- └──────────────────────────────────────────────────────────────────────────┘

CREATE TABLE IF NOT EXISTS constitutional_rules (
    id              TEXT PRIMARY KEY,
    rule_type       TEXT NOT NULL DEFAULT 'hard',
    rule_id         TEXT NOT NULL,
    description     TEXT NOT NULL,
    severity        TEXT DEFAULT 'block',
    enabled         BOOLEAN DEFAULT TRUE,
    workspace_id    TEXT,
    metadata_json   JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_constitutional_rules_workspace
    ON constitutional_rules(workspace_id) WHERE workspace_id IS NOT NULL;

-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │ 4. PRESENCE                                                             │
-- │    Used by: api/v1/presence.py                                          │
-- └──────────────────────────────────────────────────────────────────────────┘

CREATE TABLE IF NOT EXISTS presence (
    user_id         TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    status          TEXT DEFAULT 'online',
    last_heartbeat  TIMESTAMPTZ DEFAULT NOW(),
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_presence_workspace
    ON presence(workspace_id, last_heartbeat DESC);

-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │ 5. INCIDENTS (War Room)                                                 │
-- │    Used by: api/v1/warroom.py                                           │
-- └──────────────────────────────────────────────────────────────────────────┘

CREATE TABLE IF NOT EXISTS incidents (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    severity        TEXT DEFAULT 'medium',
    status          TEXT DEFAULT 'open',
    assigned_to     TEXT,
    reported_by     TEXT,
    status_history  JSONB DEFAULT '[]',
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incidents_workspace
    ON incidents(workspace_id, created_at DESC);

-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │ 6. COLLABORATION STATE                                                  │
-- │    Used by: api/v1/collaboration.py                                     │
-- └──────────────────────────────────────────────────────────────────────────┘

CREATE TABLE IF NOT EXISTS collaboration_state (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    session_id      TEXT,
    state_type      TEXT NOT NULL,
    payload         JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_collaboration_state_workspace
    ON collaboration_state(workspace_id);
