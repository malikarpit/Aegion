-- AEGION Core Schema
-- ============================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Workspaces (multi-tenant isolation)
CREATE TABLE workspaces (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    owner_id UUID NOT NULL,
    settings JSONB DEFAULT '{}',
    security_level TEXT DEFAULT 'standard' CHECK (security_level IN ('standard', 'confidential', 'restricted')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    role TEXT DEFAULT 'developer' CHECK (role IN ('admin', 'architect', 'developer', 'viewer')),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    api_keys JSONB DEFAULT '{}', -- Encrypted LLM provider keys
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions
CREATE TABLE sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'closed', 'recovered')),
    mode TEXT DEFAULT 'standard' CHECK (mode IN ('standard', 'architecture', 'emergency', 'readonly')),
    intent TEXT,
    context JSONB DEFAULT '{}',
    artifacts JSONB DEFAULT '[]',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

-- Proposals
CREATE TABLE proposals (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    proposal_type TEXT DEFAULT 'code' CHECK (proposal_type IN ('code', 'architecture', 'policy', 'config')),
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'pending', 'approved', 'rejected', 'superseded')),
    tier INTEGER DEFAULT 0 CHECK (tier BETWEEN 0 AND 3),
    evidence JSONB DEFAULT '[]',
    votes JSONB DEFAULT '[]',
    comments JSONB DEFAULT '[]',
    council_result JSONB,
    created_by UUID REFERENCES users(id),
    reviewed_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Decisions (immutable — append only)
CREATE TABLE decisions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    proposal_id UUID REFERENCES proposals(id),
    decision_type TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('approved', 'rejected', 'deferred', 'superseded')),
    tier INTEGER NOT NULL CHECK (tier BETWEEN 0 AND 3),
    rationale TEXT,
    evidence JSONB DEFAULT '[]',
    dissenting_views JSONB DEFAULT '[]',
    supersedes_id UUID REFERENCES decisions(id),
    decided_by TEXT NOT NULL, -- 'archon_auto' | 'human:user_id' | 'council:session_id'
    decided_at TIMESTAMPTZ DEFAULT NOW(),
    -- Immutability: no UPDATE trigger, append-only
    lineage_hash TEXT -- SHA256 of parent decision chain
);

-- Architecture Decision Records (ADRs)
CREATE TABLE adrs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    decision_id UUID REFERENCES decisions(id),
    title TEXT NOT NULL,
    status TEXT DEFAULT 'proposed' CHECK (status IN ('proposed', 'accepted', 'deprecated', 'superseded')),
    context TEXT,
    decision_text TEXT,
    consequences TEXT,
    alternatives JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Knowledge Graph nodes
CREATE TABLE knowledge_nodes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    node_type TEXT NOT NULL, -- 'decision', 'adr', 'file', 'concept', 'entity'
    label TEXT NOT NULL,
    properties JSONB DEFAULT '{}',
    embedding vector(384), -- For semantic search
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Knowledge Graph edges
CREATE TABLE knowledge_edges (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    target_id UUID NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    edge_type TEXT NOT NULL, -- 'depends_on', 'supersedes', 'references', 'part_of'
    weight FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chronos timeline events (append-only)
CREATE TABLE timeline_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    actor TEXT NOT NULL,
    payload JSONB NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    sequence_number BIGSERIAL
);

-- Sentinel risk signals
CREATE TABLE risk_signals (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL, -- 'security', 'performance', 'drift', 'dependency'
    severity TEXT NOT NULL CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    source TEXT NOT NULL,
    description TEXT NOT NULL,
    evidence JSONB DEFAULT '{}',
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log (append-only, never delete)
CREATE TABLE audit_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID,
    details JSONB DEFAULT '{}',
    ip_address INET,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Memory entries
CREATE TABLE memories (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    memory_type TEXT NOT NULL, -- 'lesson', 'pattern', 'preference', 'context'
    content TEXT NOT NULL,
    embedding vector(384),
    source_session_id UUID REFERENCES sessions(id),
    confidence FLOAT DEFAULT 1.0,
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- Rules
CREATE TABLE rules (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    rule_type TEXT NOT NULL, -- 'governance', 'code_style', 'architecture', 'security'
    condition JSONB NOT NULL,
    action JSONB NOT NULL,
    priority INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Semantic cache (for cost optimization)
CREATE TABLE semantic_cache (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    query_embedding vector(384) NOT NULL,
    response_text TEXT NOT NULL,
    response_model TEXT NOT NULL,
    council_type TEXT,
    hit_count INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0,
    cost_saved FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- Cost tracking
CREATE TABLE cost_tracking (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    provider TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd FLOAT NOT NULL,
    council_type TEXT,
    cache_hit BOOLEAN DEFAULT FALSE,
    cascade_tier INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Skills
CREATE TABLE skills (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    version TEXT DEFAULT '1.0.0',
    manifest JSONB NOT NULL,
    source_url TEXT,
    installed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks
CREATE TABLE tasks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id),
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'blocked', 'cancelled')),
    priority INTEGER DEFAULT 0,
    assigned_to UUID REFERENCES users(id),
    due_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Checkpoints
CREATE TABLE checkpoints (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id),
    label TEXT NOT NULL,
    checkpoint_type TEXT DEFAULT 'manual' CHECK (checkpoint_type IN ('manual', 'auto', 'pre_decision')),
    state_snapshot JSONB NOT NULL,
    git_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_sessions_workspace ON sessions(workspace_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_proposals_workspace ON proposals(workspace_id);
CREATE INDEX idx_proposals_status ON proposals(status);
CREATE INDEX idx_decisions_workspace ON decisions(workspace_id);
CREATE INDEX idx_timeline_workspace ON timeline_events(workspace_id, timestamp DESC);
CREATE INDEX idx_timeline_entity ON timeline_events(entity_type, entity_id);
CREATE INDEX idx_knowledge_nodes_workspace ON knowledge_nodes(workspace_id);
CREATE INDEX idx_knowledge_nodes_type ON knowledge_nodes(node_type);
CREATE INDEX idx_knowledge_nodes_embedding ON knowledge_nodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_memories_workspace ON memories(workspace_id);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_semantic_cache_embedding ON semantic_cache USING ivfflat (query_embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_audit_workspace ON audit_log(workspace_id, timestamp DESC);
CREATE INDEX idx_risk_signals_workspace ON risk_signals(workspace_id, severity);
CREATE INDEX idx_cost_tracking_workspace ON cost_tracking(workspace_id, created_at DESC);

-- Row Level Security (multi-tenant isolation)
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- RLS Policies (workspace-scoped)
CREATE POLICY workspace_isolation ON sessions
    FOR ALL USING (workspace_id IN (
        SELECT workspace_id FROM users WHERE id = auth.uid()
    ));
