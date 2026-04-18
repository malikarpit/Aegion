-- ═══════════════════════════════════════════════════════════════
-- Aegion Migration 002: Application Tables (W8.4)
-- 
-- Creates all tables referenced by seed_data.py and core services.
-- Includes: workspaces, timeline_events, decisions, risk_signals,
--           adrs, rejection_log, cost_tracking, vault_secrets,
--           vault_audit_log, custom_rubrics, workspace_model_settings,
--           alerts, constitutional_rules, presence, incidents,
--           collaboration_state
--
-- Idempotent: Uses CREATE TABLE IF NOT EXISTS throughout.
-- ═══════════════════════════════════════════════════════════════

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ──────────────────────────────────────────────
-- Workspaces
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workspaces (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    display_name    TEXT,
    description     TEXT,
    owner_id        TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- Timeline Events (Chronos)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS timeline_events (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL REFERENCES workspaces(id),
    event_type      TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    severity        TEXT DEFAULT 'info',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_timeline_workspace
    ON timeline_events(workspace_id, created_at DESC);

-- ──────────────────────────────────────────────
-- Decisions
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS decisions (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL REFERENCES workspaces(id),
    session_id      TEXT,
    title           TEXT NOT NULL,
    verdict         TEXT NOT NULL,
    tier            TEXT DEFAULT 'T0',
    confidence      REAL DEFAULT 0.0,
    consensus_score REAL DEFAULT 0.0,
    evidence        JSONB DEFAULT '[]',
    dissenting      JSONB DEFAULT '[]',
    supersedes      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decisions_workspace
    ON decisions(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_supersedes
    ON decisions(supersedes) WHERE supersedes IS NOT NULL;

-- ──────────────────────────────────────────────
-- Risk Signals (Sentinel)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_signals (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL REFERENCES workspaces(id),
    signal_type     TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'low',
    score           REAL DEFAULT 0.0,
    description     TEXT,
    evidence        JSONB DEFAULT '{}',
    resolved        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_workspace
    ON risk_signals(workspace_id, created_at DESC);

-- ──────────────────────────────────────────────
-- Architecture Decision Records (ADRs)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS adrs (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL REFERENCES workspaces(id),
    title           TEXT NOT NULL,
    status          TEXT DEFAULT 'proposed',
    context         TEXT,
    decision_text   TEXT,
    consequences    TEXT,
    superseded_by   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- Rejection Log (RLHF)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rejection_log (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    proposal_id     TEXT,
    proposal_title  TEXT,
    proposal_tier   TEXT,
    rejected_by     TEXT,
    reason_category TEXT NOT NULL,
    reason_detail   TEXT,
    session_id      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rejection_workspace
    ON rejection_log(workspace_id, created_at DESC);

-- ──────────────────────────────────────────────
-- Cost Tracking
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cost_tracking (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    period          TEXT NOT NULL,
    provider        TEXT NOT NULL,
    model           TEXT,
    input_tokens    BIGINT DEFAULT 0,
    output_tokens   BIGINT DEFAULT 0,
    cost_usd        REAL DEFAULT 0.0,
    request_count   INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cost_workspace_period
    ON cost_tracking(workspace_id, period);

-- ──────────────────────────────────────────────
-- Vault (Secrets)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vault_secrets (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    key_name        TEXT NOT NULL,
    encrypted_value TEXT NOT NULL,
    provider        TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(workspace_id, key_name)
);

CREATE TABLE IF NOT EXISTS vault_audit_log (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    action          TEXT NOT NULL,
    key_name        TEXT,
    actor           TEXT,
    ip_address      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- Custom Rubrics
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS custom_rubrics (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    name            TEXT NOT NULL,
    criteria        JSONB DEFAULT '[]',
    weight_scheme   JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- Workspace Model Settings
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workspace_model_settings (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL UNIQUE,
    default_model   TEXT,
    provider_keys   JSONB DEFAULT '{}',
    tier_config     JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- Alerts
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    alert_type      TEXT NOT NULL,
    severity        TEXT DEFAULT 'info',
    title           TEXT NOT NULL,
    message         TEXT,
    acknowledged    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_workspace
    ON alerts(workspace_id, created_at DESC);

-- ──────────────────────────────────────────────
-- Constitutional Rules (W2.1)
-- ──────────────────────────────────────────────
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

CREATE INDEX IF NOT EXISTS idx_rules_workspace
    ON constitutional_rules(workspace_id) WHERE workspace_id IS NOT NULL;

-- ──────────────────────────────────────────────
-- Presence (W5.2)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS presence (
    user_id         TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    status          TEXT DEFAULT 'online',
    last_heartbeat  TIMESTAMPTZ DEFAULT NOW(),
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_presence_workspace
    ON presence(workspace_id, last_heartbeat DESC);

-- ──────────────────────────────────────────────
-- Incidents (War Room — W5.3)
-- ──────────────────────────────────────────────
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

-- ──────────────────────────────────────────────
-- Collaboration State
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS collaboration_state (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    session_id      TEXT,
    state_type      TEXT NOT NULL,
    payload         JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- Reasoning Chains (1.15 — MCTS/ToT persistence)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reasoning_chains (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    session_id      TEXT,
    chain_type      TEXT NOT NULL DEFAULT 'mcts',
    query           TEXT,
    best_path       JSONB DEFAULT '[]',
    all_paths       JSONB DEFAULT '[]',
    scores          JSONB DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reasoning_workspace
    ON reasoning_chains(workspace_id, created_at DESC);

-- ──────────────────────────────────────────────
-- Add parent_decision_id to decisions for lineage (W2.3)
-- ──────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'decisions' AND column_name = 'parent_decision_id'
    ) THEN
        ALTER TABLE decisions ADD COLUMN parent_decision_id TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'decisions' AND column_name = 'status'
    ) THEN
        ALTER TABLE decisions ADD COLUMN status TEXT DEFAULT 'accepted';
    END IF;
END $$;
