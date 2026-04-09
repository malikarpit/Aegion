-- Migration: Create council_findings table for Phase 51 analytics
-- Tracks red team findings per consultation for hallucination rate, model accuracy, etc.

CREATE TABLE IF NOT EXISTS council_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id TEXT NOT NULL,
    attack_vector TEXT NOT NULL,       -- 'injection', 'hallucination', 'logic', 'governance'
    severity TEXT NOT NULL DEFAULT 'medium',  -- 'critical', 'high', 'medium', 'low'
    description TEXT NOT NULL,
    model_used TEXT DEFAULT 'unknown',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_findings_workspace ON council_findings(workspace_id);
CREATE INDEX IF NOT EXISTS idx_findings_vector ON council_findings(attack_vector);
CREATE INDEX IF NOT EXISTS idx_findings_created ON council_findings(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_findings_workspace_created ON council_findings(workspace_id, created_at DESC);

COMMENT ON TABLE council_findings IS 'Red team findings per council consultation — used for Phase 51 analytics (hallucination rate, model accuracy, etc.)';
