-- Phase 6: Knowledge Graph → PostgreSQL Migration
-- Graph traversal function and semantic search RPC

-- Recursive neighbors traversal up to N hops
CREATE OR REPLACE FUNCTION get_graph_neighbors(
    p_node_id UUID,
    p_workspace_id UUID,
    p_depth INTEGER DEFAULT 1
) RETURNS JSONB
LANGUAGE SQL
STABLE
AS $$
WITH RECURSIVE traversal AS (
    -- Base: direct edges touching the seed node
    SELECT
        source_id,
        target_id,
        edge_type,
        1 AS depth
    FROM knowledge_edges
    WHERE (source_id = p_node_id OR target_id = p_node_id)
      AND workspace_id = p_workspace_id

    UNION ALL

    -- Recursive: extend one hop further
    SELECT
        e.source_id,
        e.target_id,
        e.edge_type,
        t.depth + 1
    FROM knowledge_edges e
    JOIN traversal t
        ON (e.source_id = t.target_id OR e.source_id = t.source_id)
    WHERE t.depth < p_depth
      AND e.workspace_id = p_workspace_id
)
SELECT COALESCE(
    jsonb_agg(
        jsonb_build_object(
            'source', source_id,
            'target', target_id,
            'type',   edge_type,
            'depth',  depth
        )
    ),
    '[]'::jsonb
)
FROM traversal;
$$;

-- Semantic similarity search over knowledge_nodes embeddings (pgvector cosine)
CREATE OR REPLACE FUNCTION match_knowledge_nodes(
    query_embedding vector(384),
    match_threshold  FLOAT    DEFAULT 0.7,
    match_count      INT      DEFAULT 10,
    p_workspace_id   UUID     DEFAULT NULL
)
RETURNS TABLE (
    id          UUID,
    label       TEXT,
    node_type   TEXT,
    properties  JSONB,
    similarity  FLOAT
)
LANGUAGE SQL
STABLE
AS $$
    SELECT
        id,
        label,
        node_type,
        properties,
        1 - (embedding <=> query_embedding) AS similarity
    FROM knowledge_nodes
    WHERE
        (p_workspace_id IS NULL OR workspace_id = p_workspace_id)
        AND 1 - (embedding <=> query_embedding) > match_threshold
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$;
