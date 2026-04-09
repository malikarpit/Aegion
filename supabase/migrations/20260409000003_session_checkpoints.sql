-- Phase 7: Session Manager Hardening
-- Session checkpoints

CREATE TABLE session_checkpoints (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    label TEXT NOT NULL,
    state_snapshot JSONB NOT NULL,
    git_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_checkpoints_session ON session_checkpoints(session_id);
