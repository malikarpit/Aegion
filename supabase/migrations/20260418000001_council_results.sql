-- ========================================================================
-- Phase 8: ACK Council Results Table
-- Stores results from the AEGION Council Kernel (ACK) multi-model
-- council operations for audit trail, analytics, and cost tracking.
-- ========================================================================

CREATE TABLE IF NOT EXISTS council_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    council_type TEXT NOT NULL CHECK (council_type IN ('child', 'distillation', 'parent', 'sentinel')),
    profile TEXT NOT NULL CHECK (profile IN ('trivial', 'simple', 'moderate', 'complex', 'critical')),
    query TEXT NOT NULL,
    synthesis TEXT NOT NULL,
    consensus_score FLOAT DEFAULT 0.0,
    total_cost_usd FLOAT DEFAULT 0.0,
    total_tokens INTEGER DEFAULT 0,
    total_latency_ms INTEGER DEFAULT 0,
    cache_hit BOOLEAN DEFAULT FALSE,
    models_used TEXT[] DEFAULT '{}',
    providers_used TEXT[] DEFAULT '{}',
    individual_responses JSONB DEFAULT '[]',
    dissenting_views JSONB DEFAULT '[]',
    rubric_scores JSONB,
    persona_perspectives JSONB,
    evidence_used BOOLEAN DEFAULT FALSE,
    prompt_compressed BOOLEAN DEFAULT FALSE,
    tokens_saved_by_compression INTEGER DEFAULT 0,
    estimated_savings_vs_frontier FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common access patterns
CREATE INDEX IF NOT EXISTS idx_council_results_workspace
    ON council_results (workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_council_results_type
    ON council_results (council_type);

CREATE INDEX IF NOT EXISTS idx_council_results_cache
    ON council_results (cache_hit)
    WHERE cache_hit = TRUE;

-- Cost analytics query support
CREATE INDEX IF NOT EXISTS idx_council_results_cost
    ON council_results (workspace_id, total_cost_usd);

COMMENT ON TABLE council_results IS 'ACK multi-model council results for audit and analytics (Phase 8)';
