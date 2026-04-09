-- Migration: Add council_config JSONB column to workspace_model_settings
-- Purpose: Per-workspace ACK advanced pipeline configuration
-- All features default to OFF (except constitution_enforcement which defaults to ON)

ALTER TABLE workspace_model_settings
ADD COLUMN IF NOT EXISTS council_config JSONB DEFAULT '{
  "mcts_enabled": false,
  "mcts_max_budget_usd": 0.10,
  "mcts_max_iterations": 4,
  "mcts_branch_factor": 2,
  "mcts_max_depth": 4,
  "mcts_exploration_c": 1.414,
  "dag_pipeline_enabled": false,
  "dag_max_retries": 2,
  "dag_timeout_seconds": 120.0,
  "reflector_enabled": false,
  "reflector_groupthink_threshold": 0.90,
  "reflector_circular_window": 2,
  "red_team_enabled": false,
  "red_team_max_budget_usd": 0.02,
  "red_team_min_score": 0.5,
  "temporal_memory_enabled": false,
  "temporal_recall_top_k": 3,
  "temporal_outcome_window_days": 30,
  "cross_council_enabled": false,
  "cross_council_max_sub_councils": 3,
  "cross_council_sub_budget_usd": 0.05,
  "cross_council_total_budget_usd": 0.20,
  "constitution_enforcement": true,
  "constitution_block_on_violation": true,
  "weighted_synthesis_enabled": false,
  "synthesis_merge_budget_usd": 0.03
}'::jsonb;

-- Add comment for documentation
COMMENT ON COLUMN workspace_model_settings.council_config IS 
  'Per-workspace ACK advanced pipeline configuration. All features opt-in through settings page.';
