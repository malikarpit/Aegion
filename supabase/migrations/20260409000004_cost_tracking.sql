-- Phase 8: ACK Cost Tracking Table
-- Used by CouncilEngine._track_cost() to record every council invocation cost

CREATE TABLE cost_tracking (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    models TEXT NOT NULL,         -- comma-separated list of models used
    purpose TEXT NOT NULL,        -- council_type value (child, parent, sentinel, distillation)
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    cost_usd NUMERIC(10, 6) DEFAULT 0,
    cache_hit BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cost_tracking_workspace ON cost_tracking(workspace_id);
CREATE INDEX idx_cost_tracking_created ON cost_tracking(created_at);
