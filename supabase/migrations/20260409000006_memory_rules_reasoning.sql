-- Phases 29, 43, 45: Memory, Rejection Learning, Reasoning Chains

-- ── Phase 29: Workspace Memories ──

CREATE TABLE IF NOT EXISTS memories (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL DEFAULT 'context',
    embedding vector(384),
    source_session_id UUID,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memories_workspace ON memories(workspace_id);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(workspace_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- RPC for semantic memory recall
CREATE OR REPLACE FUNCTION match_memories(
    query_embedding vector(384),
    p_workspace_id UUID,
    match_count INT,
    match_threshold FLOAT,
    p_memory_type TEXT DEFAULT NULL
)
RETURNS TABLE (id UUID, content TEXT, memory_type TEXT, similarity FLOAT)
LANGUAGE sql STABLE
AS $$
    SELECT m.id, m.content, m.memory_type,
           1 - (m.embedding <=> query_embedding) AS similarity
    FROM memories m
    WHERE m.workspace_id = p_workspace_id
      AND 1 - (m.embedding <=> query_embedding) > match_threshold
      AND (p_memory_type IS NULL OR m.memory_type = p_memory_type)
    ORDER BY m.embedding <=> query_embedding
    LIMIT match_count;
$$;


-- ── Phase 29: Workspace Rules ──

CREATE TABLE IF NOT EXISTS rules (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    condition JSONB NOT NULL DEFAULT '{}',
    action TEXT NOT NULL DEFAULT 'warn',
    priority INT DEFAULT 0,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rules_workspace ON rules(workspace_id, enabled);


-- ── Phase 43: Rejection Learning ──

CREATE TABLE IF NOT EXISTS rejection_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    proposal_id UUID,
    rejection_reason TEXT NOT NULL,
    proposal_context JSONB DEFAULT '{}',
    council_output JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rejection_log_workspace ON rejection_log(workspace_id);


-- ── Phase 45: Reasoning Chains ──

CREATE TABLE IF NOT EXISTS reasoning_chains (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    decision_id TEXT NOT NULL,
    query TEXT NOT NULL,
    steps JSONB DEFAULT '[]',
    conclusion TEXT,
    overall_confidence FLOAT DEFAULT 0.0,
    total_cost_usd FLOAT DEFAULT 0.0,
    step_count INT DEFAULT 0,
    created_at FLOAT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reasoning_workspace ON reasoning_chains(workspace_id);
CREATE INDEX IF NOT EXISTS idx_reasoning_decision ON reasoning_chains(decision_id);
