-- ============================================================
-- Migration 007: Vault, Custom Rubrics, Model Settings, Alerts
-- Phase 38 (Vault), Phase 15 (Rubrics), Phase 84 (Model Settings), Phase 74 (Alerting)
-- ============================================================

-- Vault secrets (encrypted at rest)
CREATE TABLE IF NOT EXISTS vault_secrets (
    id         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    key        TEXT NOT NULL,
    encrypted_value TEXT NOT NULL,
    version    INTEGER DEFAULT 1,
    workspace_id UUID REFERENCES workspaces(id),
    max_age_hours INTEGER,
    is_active  BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_vault_secrets_key_version ON vault_secrets(key, version);
CREATE INDEX IF NOT EXISTS idx_vault_secrets_active ON vault_secrets(is_active) WHERE is_active = TRUE;

-- Vault audit log
CREATE TABLE IF NOT EXISTS vault_audit_log (
    id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    key          TEXT NOT NULL,
    action       TEXT NOT NULL,  -- store, access, rotate, delete, token_generated, token_redeemed
    actor_id     TEXT DEFAULT 'system',
    workspace_id UUID,
    details      JSONB DEFAULT '{}',
    timestamp    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vault_audit_ws ON vault_audit_log(workspace_id, timestamp DESC);

-- Custom rubrics
CREATE TABLE IF NOT EXISTS custom_rubrics (
    id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    workspace_id UUID REFERENCES workspaces(id),
    criteria     JSONB NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- Model settings: workspace → active profile
CREATE TABLE IF NOT EXISTS workspace_model_settings (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id    UUID NOT NULL UNIQUE REFERENCES workspaces(id),
    active_profile  TEXT NOT NULL DEFAULT 'quality',
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Custom model profiles
CREATE TABLE IF NOT EXISTS custom_model_profiles (
    id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    profile_data JSONB NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    rule_id         TEXT NOT NULL,
    name            TEXT NOT NULL,
    severity        TEXT NOT NULL,  -- critical, warning, info
    description     TEXT,
    details         JSONB DEFAULT '{}',
    workspace_id    UUID REFERENCES workspaces(id),
    fired_at        TIMESTAMPTZ DEFAULT now(),
    acknowledged    BOOLEAN DEFAULT FALSE,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_alerts_ws_time ON alerts(workspace_id, fired_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_unacked ON alerts(workspace_id, acknowledged) WHERE acknowledged = FALSE;

-- RLS policies
ALTER TABLE vault_secrets ENABLE ROW LEVEL SECURITY;
ALTER TABLE vault_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE custom_rubrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_model_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE custom_model_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

-- Service role access (backend calls with service key)
CREATE POLICY "service_role_vault_secrets" ON vault_secrets FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_vault_audit" ON vault_audit_log FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_custom_rubrics" ON custom_rubrics FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_workspace_model" ON workspace_model_settings FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_custom_profiles" ON custom_model_profiles FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_alerts" ON alerts FOR ALL USING (TRUE) WITH CHECK (TRUE);
