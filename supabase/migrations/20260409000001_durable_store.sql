-- Phase 5: Durable Store → PostgreSQL Migration
-- KV Store table for general key-value persistence

CREATE TABLE kv_store (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    namespace TEXT NOT NULL DEFAULT 'default',
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(workspace_id, namespace, key)
);

CREATE INDEX idx_kv_workspace_ns ON kv_store(workspace_id, namespace);

-- Session ownership table (migrated from JsonFileStore)
CREATE TABLE session_ownership (
    session_id TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    owner_id TEXT,
    status TEXT NOT NULL DEFAULT 'claimed' CHECK (status IN ('claimed', 'pending', 'released')),
    pending_transfer_to TEXT,
    history JSONB DEFAULT '[]',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_session_ownership_workspace ON session_ownership(workspace_id);
