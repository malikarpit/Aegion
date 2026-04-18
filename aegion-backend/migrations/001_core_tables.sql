-- ════════════════════════════════════════════════════════════════════════════
-- ⚠️  LEGACY — DO NOT USE FOR NEW DEPLOYMENTS
--
-- This file has been superseded by the canonical Supabase migration set at:
--   supabase/migrations/20260424000001_missing_tables.sql
--   supabase/migrations/20260409000001_durable_store.sql
--
-- All tables defined here now exist in the canonical migration chain.
-- This file is retained for historical reference only.
-- ════════════════════════════════════════════════════════════════════════════
-- Aegion — Core Table Migrations (LEGACY)
-- Version: 001
--
-- Consolidates all table schemas that were previously scattered across
-- module docstrings into a single idempotent migration file.
--
-- Tables:
--   1. skills         — Skill registry (from implementation plan 1.9)
--   2. task_runs       — Task execution log (from implementation plan 1.9)
--   3. checkpoints     — Session state snapshots (from implementation plan 1.9)
--   4. batch_queue     — Deferred query queue (from batch_processor.py)
--
-- Usage: ⚠️ Use supabase/migrations/ instead
-- ════════════════════════════════════════════════════════════════════════════

-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │ 1. SKILLS REGISTRY                                                      │
-- │    Source: implementation_plan.md §1.9                                   │
-- │    Used by: skill_loader.py, api/v1/skills.py                           │
-- └──────────────────────────────────────────────────────────────────────────┘

CREATE TABLE IF NOT EXISTS skills (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     TEXT NOT NULL,
    name             TEXT NOT NULL,
    description      TEXT,
    handler          TEXT NOT NULL,           -- Python module path or SKILL.md ref
    parameters       JSONB DEFAULT '{}',
    category         TEXT DEFAULT 'custom',
    version          TEXT DEFAULT '1.0.0',
    status           TEXT DEFAULT 'active',   -- active | disabled | deprecated
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE(workspace_id, name)
);

CREATE INDEX IF NOT EXISTS idx_skills_workspace
    ON skills(workspace_id);


-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │ 2. TASK RUNS                                                            │
-- │    Source: implementation_plan.md §1.9                                   │
-- │    Used by: api/v1/tasks.py, batch_processor.py                         │
-- └──────────────────────────────────────────────────────────────────────────┘

CREATE TABLE IF NOT EXISTS task_runs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id          UUID NOT NULL,
    workspace_id     TEXT NOT NULL,
    status           TEXT DEFAULT 'pending',  -- pending | running | success | failed
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
-- │ 3. CHECKPOINTS (Session State Snapshots)                                │
-- │    Source: implementation_plan.md §1.9                                   │
-- │    Used by: session_manager.py, checkpoint/rollback service             │
-- └──────────────────────────────────────────────────────────────────────────┘

CREATE TABLE IF NOT EXISTS checkpoints (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id       UUID NOT NULL,
    workspace_id     TEXT NOT NULL,
    state            JSONB NOT NULL,          -- Full session snapshot
    label            TEXT,                     -- Optional human-readable label
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_session
    ON checkpoints(session_id, created_at DESC);


-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │ 4. BATCH QUEUE (Deferred Processing)                                    │
-- │    Source: batch_processor.py (Phase 82)                                │
-- │    Used by: batch_processor.py, api/v1/batch.py                        │
-- └──────────────────────────────────────────────────────────────────────────┘

CREATE TABLE IF NOT EXISTS batch_queue (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     TEXT NOT NULL,
    query            TEXT NOT NULL,
    priority         TEXT NOT NULL DEFAULT 'deferred',  -- immediate|soon|deferred|batch
    status           TEXT NOT NULL DEFAULT 'queued',    -- queued|processing|completed|failed
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
