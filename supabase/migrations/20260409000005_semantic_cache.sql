-- Phase 11: Semantic Cache table with TTL and pgvector similarity search

CREATE TABLE semantic_cache (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    query_embedding vector(384) NOT NULL,
    response_text TEXT NOT NULL,
    response_model TEXT NOT NULL,
    cache_type TEXT DEFAULT 'default',
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_semantic_cache_workspace ON semantic_cache(workspace_id);
CREATE INDEX idx_semantic_cache_embedding ON semantic_cache USING ivfflat (query_embedding vector_cosine_ops) WITH (lists = 100);

-- RPC function used by SemanticCache.check()
CREATE OR REPLACE FUNCTION match_semantic_cache(
    query_embedding vector(384),
    match_threshold float,
    match_count int,
    p_workspace_id uuid,
    p_now timestamptz
)
RETURNS TABLE (
    id uuid,
    query_text text,
    response_text text,
    response_model text,
    cache_type text,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT
        sc.id,
        sc.query_text,
        sc.response_text,
        sc.response_model,
        sc.cache_type,
        1 - (sc.query_embedding <=> query_embedding) AS similarity
    FROM semantic_cache sc
    WHERE
        sc.workspace_id = p_workspace_id
        AND sc.expires_at > p_now
        AND 1 - (sc.query_embedding <=> query_embedding) >= match_threshold
    ORDER BY sc.query_embedding <=> query_embedding
    LIMIT match_count;
$$;
