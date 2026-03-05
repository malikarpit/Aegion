/**
 * Aegion API Types
 *
 * Shared type definitions for the Aegion API client and extension components.
 * Extracted from client.ts to prevent circular dependencies.
 */

// ========== Configuration ==========

export type ClientGenerationMode = 'manual' | 'automatic' | 'automatic-with-review';

export interface AegionClientConfig {
    baseUrl: string;
    sessionId?: string;
    workspaceId?: string;
    authToken?: string;
    timeout?: number;
}

// ========== Base Domain Types ==========

// Decision Intent
export type ImpactLevel = 'trivial' | 'local' | 'cross_module' | 'system_wide' | 'external';
export type ReversibilityLevel = 'trivial' | 'easy' | 'moderate' | 'difficult' | 'irreversible';
export type DecisionTier = 'T0' | 'T1' | 'T2' | 'T3';

// Proposal Status
export type ProposalStatus =
    | 'draft'
    | 'pending_review'
    | 'approved'
    | 'rejected'
    | 'superseded'
    | 'expired';

// Evidence
export type EvidenceClassification =
    | 'supporting'
    | 'contradictory'
    | 'inconclusive';

// ========== Collaboration ==========

export type OwnershipStatus = 'claimed' | 'released' | 'pending';

export type TransferReason = 'handoff' | 'interruption' | 'requested' | 'force';

export interface OwnershipTransfer {
    transfer_id: string;
    from_user_id?: string;
    to_user_id: string;
    reason: TransferReason;
    timestamp: string;
    status: string;
}

export interface SessionOwnership {
    session_id: string;
    workspace_id: string;
    owner_id?: string;
    status: OwnershipStatus;
    expires_at?: string;
    pending_transfer_to?: string;
    history: OwnershipTransfer[];
    metadata?: Record<string, unknown>;
    updated_at: string;
}

export interface TransferOwnershipRequest {
    target_user_id: string;
}

// ========== Thought-Commit Protocol (Phase 4) ==========

export type ThoughtState = 'draft' | 'sealed' | 'superseded' | 'orphaned';

export type ThoughtLinkType =
    | 'explains'          // Thought -> Commit
    | 'supersedes'        // Thought -> Thought
    | 'references'        // Thought -> Evidence/Context
    | 'derives_from';     // Thought -> Proposal/Council

export interface ThoughtLink {
    link_id: string;
    type: ThoughtLinkType;
    target_id: string;
    target_type: 'commit' | 'proposal' | 'decision' | 'evidence';
    metadata?: Record<string, unknown>;
    created_at: string;
}

export interface ThoughtCommit {
    thought_id: string;
    workspace_id: string;
    session_id: string;
    title: string;
    rationale: string;
    alternatives: string[];
    links: ThoughtLink[];
    created_by: string;
    created_at: string;
    updated_at: string;
    sealed_at?: string;
    state: ThoughtState;
    content_hash?: string;
    tier?: string;
    drivers?: unknown[]; // DecisionDriver[]
}

export interface CreateThoughtRequest {
    workspace_id: string;
    session_id: string;
    title: string;
    rationale: string;
    proposal_id?: string;
    decision_id?: string;
}

export interface UpdateThoughtRequest {
    title?: string;
    rationale?: string;
    alternatives?: string[];
    add_links?: ThoughtLink[];
    remove_link_ids?: string[];
}

export interface SealThoughtRequest {
    content_hash?: string;
}

export interface LinkCommitRequest {
    commit_sha: string;
    repo_path?: string;
    branch?: string;
}

// ========== Request/Response Types ==========

export interface CreateSessionRequest {
    workspace_id: string;
    context_hash?: string;
}

export interface SessionResponse {
    session_id: string;
    status: string;
    created_at: string;
    initial_context?: Record<string, unknown>;
}

// Structured reasoning
export interface ReasoningPhase {
    problem_framing: string;
    assumptions?: string[];
    constraints?: string[];
    boundaries?: string[];
    alternatives_considered?: string[];
    risk_assessment?: string;
    success_criteria?: string[];
}

// Uncertainty declaration
export type UncertaintyLevel = 'certain' | 'high' | 'medium' | 'low' | 'unknown';
export type UncertaintySource = 'data_quality' | 'model_limitation' | 'domain_complexity' | 'time_pressure' | 'incomplete_context';

export interface UncertaintyDeclaration {
    level: UncertaintyLevel;
    confidence_score: number;
    sources?: UncertaintySource[];
    reasoning: string;
    is_blocking?: boolean;
    blocking_reason?: string;
    additional_evidence_needed?: string[];
}

export interface CreateProposalRequest {
    session_id: string;
    title: string;
    description: string;
    impact_level: ImpactLevel;
    reversibility: ReversibilityLevel;
    affected_modules?: string[];
    affected_files?: string[];
    reasoning: ReasoningPhase;
    uncertainty?: UncertaintyDeclaration;
    metadata?: Record<string, unknown>;
}

export interface ProposalResponse {
    proposal_id: string;
    tier: DecisionTier;
    status: string;
    title: string;
    quorum_required: number;
    approvals_count: number;
    tier_reasons: string[];
    uncertainty?: UncertaintyDeclaration;
    visibility_label: string;
}

export interface ApprovalRecord {
    approver_id: string;
    decision: 'approve' | 'reject';
    reason?: string;
    timestamp: string;
}

export interface ApproveProposalRequest {
    evidence_ids: string[];
    justification: string;
}

export interface InvokeCouncilRequest {
    prompt: string;
    context?: Record<string, unknown>;
    stream?: boolean;
}

export interface CouncilResponse {
    response: string;
    reasoning?: string;
    confidence?: number;
    alternatives?: string[];
    // Extended properties for views
    consensus?: boolean;
    recommendation?: string;
    child_confidence?: number;
    sentinel_blocking?: boolean;
    diff?: string;
}

export interface HealthResponse {
    status: string;
    version: string;
    timestamp: string;
    components: Record<string, ComponentHealth>;
}

export interface ComponentHealth {
    status: 'healthy' | 'degraded' | 'unhealthy';
    latency_ms?: number;
    message?: string;
}

export interface TimelineEvent {
    event_id: string;
    event_type: string;
    timestamp: string;
    actor_id: string;
    summary: string;
    details?: Record<string, unknown>;
}

export interface GraphNode {
    node_id: string;
    node_type: string;
    label: string;
    properties: Record<string, unknown>;
}

export interface GraphEdge {
    source_id: string;
    target_id: string;
    edge_type: string;
    weight?: number;
}

export interface GraphResponse {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

export interface DriftReport {
    workspace_id: string;
    timestamp: string;
    drifts: Record<string, DriftMetric>;
}

export interface DriftMetric {
    drift_percentage: number | null;
    current_value: number | null;
    alert: boolean;
}

export interface DriftRequest {
    workspace_id: string;
    current_period: Record<string, unknown>[];
    baseline_period: Record<string, unknown>[];
    observation_hours?: number;
}

export interface DriftStatus {
    workspace_id: string;
    status: string;
    last_check: string;
    signals_count: number;
}

// Ghost Text Request for inline completions
export interface GhostTextRequest {
    file_path: string;
    file_content: string;
    cursor_position: { line: number; character: number };
    language_id: string;
    workspace_id?: string;
    prompt?: string;
}

export interface GhostTextSuggestion {
    text: string;
    confidence: number;
    reasoning?: string;
    is_governance_compliant?: boolean;
}

// Memory Search Result
export interface MemorySearchResult {
    id: string;
    content: string;
    score: number;
    metadata?: Record<string, unknown>;
    source?: string;
}

// Memory Query Result - array-like for iteration
export class MemoryQueryResult {
    result: string;
    sources: string[];

    constructor(private items: MemorySearchResult[], public summary: string) {
        this.result = summary;
        this.sources = items.map(i => i.source || i.id);
    }

    get results(): MemorySearchResult[] { return this.items; }

    get length(): number { return this.items.length; }

    slice(start?: number, end?: number): MemorySearchResult[] {
        return this.items.slice(start, end);
    }

    map<T>(fn: (item: MemorySearchResult, index: number) => T): T[] {
        return this.items.map(fn);
    }

    filter(fn: (item: MemorySearchResult) => boolean): MemorySearchResult[] {
        return this.items.filter(fn);
    }

    [Symbol.iterator](): Iterator<MemorySearchResult> {
        return this.items[Symbol.iterator]();
    }
}

// Sentinel Alert
export interface SentinelAlert {
    alert_id: string;
    type: string;
    severity: 'info' | 'warning' | 'error' | 'critical';
    message: string;
    timestamp: string;
    acknowledged: boolean;
    source?: string;
}

// Task Inbox Types
export interface TaskResponse {
    task_id: string;
    session_id: string;
    workspace_id: string;
    title: string;
    description?: string;
    status: string;
    priority: string;
    assignee?: string;
    created_by: string;
    created_at: string;
    updated_at: string;
    completed_at?: string;
    run_count: number;
    tags: string[];
}

export interface TaskRunResponse {
    run_id: string;
    task_id: string;
    agent_id: string;
    status: string;
    started_at?: string;
    completed_at?: string;
    duration_ms?: number;
    result?: string;
    error?: string;
    logs: string[];
}

export interface CreateTaskRequest {
    session_id: string;
    title: string;
    description?: string;
    priority?: string;
    assignee?: string;
    tags?: string[];
}

export interface RunTaskRequest {
    agent_id?: string;
    parameters?: Record<string, unknown>;
}

// Checkpoint Types
export interface CheckpointResponse {
    checkpoint_id: string;
    session_id: string;
    created_by: string;
    label: string;
    reason: string;
    status: string;
    created_at: string;
    expires_at?: string;
    rolled_back_at?: string;
    state_key_count: number;
}

export interface RollbackResponse {
    checkpoint_id: string;
    session_id: string;
    rolled_back_at: string;
    previous_state_keys: number;
    message: string;
}

export interface CreateCheckpointRequest {
    session_id: string;
    label?: string;
    reason?: string;
    state_snapshot?: Record<string, unknown>;
}

// Memory Types
export interface MemoryEntryResponse {
    memory_id: string;
    key: string;
    value: unknown;
    scope: string;
    scope_id: string;
    tags: string[];
    created_by: string;
    created_at: string;
    updated_at?: string;
    source?: string;
    confidence: number;
}

export interface CreateMemoryRequest {
    key: string;
    value: unknown;
    scope?: string;
    scope_id?: string;
    tags?: string[];
    source?: string;
    confidence?: number;
}

// Decision Graph Types (Use existing GraphNode/GraphEdge)


export interface DecisionGraphResponse {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

export interface SupersedeResponse {
    original_decision_id: string;
    new_decision_id: string;
    chain_position: number;
    superseded_at: string;
}

export interface DecisionLineage {
    decision_id: string;
    title: string;
    chain_position: number;
    supersedes?: string;
    superseded_by?: string;
    created_at: string;
    status: string;
}

// Rule Types
export interface RuleResponse {
    rule_id: string;
    name: string;
    description: string;
    condition: string;
    action: string;
    scope: string;
    scope_id: string;
    priority: string;
    enabled: boolean;
    tags: string[];
    created_by: string;
    created_at: string;
    updated_at?: string;
}

export interface CreateRuleRequest {
    name: string;
    condition: string;
    action: string;
    description?: string;
    scope?: string;
    priority?: string;
    tags?: string[];
}

export interface EvaluationResult {
    matched_rules: RuleResponse[];
    actions: string[];
    total_evaluated: number;
}

// Skill Types
export interface SkillResponse {
    skill_id: string;
    name: string;
    version: string;
    description: string;
    prompt_template: string;
    category: string;
    author: string;
    signature?: string;
    source_url?: string;
    tags: string[];
    parameters: string[];
    status: string;
    install_count: number;
    created_at: string;
    installed_at?: string;
}

export interface CreateSkillRequest {
    name: string;
    prompt_template: string;
    description?: string;
    category?: string;
    version?: string;
    tags?: string[];
    parameters?: string[];
}

export interface InstallSkillResponse {
    skill_id: string;
    name: string;
    status: string;
    installed_at: string;
    message: string;
}

export interface ValidateSkillResponse {
    skill_id: string;
    valid: boolean;
    signature?: string;
    message: string;
}

// Presence Types
export interface HeartbeatRequest {
    status?: string;
    active_file?: string;
    cursor_line?: number;
    session_id?: string;
}

export interface PresenceResponse {
    user_id: string;
    workspace_id: string;
    session_id?: string;
    status: string;
    active_file?: string;
    cursor_line?: number;
    connected_at: string;
    last_heartbeat: string;
}

export interface WorkspacePresenceResponse {
    workspace_id: string;
    online_count: number;
    users: PresenceResponse[];
}

// War Room Types
export interface IncidentResponse {
    incident_id: string;
    title: string;
    description: string;
    severity: string;
    status: string;
    service: string;
    created_by: string;
    created_at: string;
    resolved_at?: string;
    tags: string[];
}

export interface CreateIncidentRequest {
    title: string;
    description?: string;
    severity?: string;
    service: string;
    tags?: string[];
    metadata?: Record<string, string>;
}

export interface WarRoomOverview {
    system_status: string;
    active_incidents: number;
    critical_incidents: number;
    online_users: number;
    active_checkpoints: number;
    recent_incidents: IncidentResponse[];
}

// Delegation Types
export interface CloudResource {
    resource_id: string;
    name: string;
    type: string;
    provider: string;
    region: string;
    status: string;
    created_at: string;
}

export interface DeploymentResult {
    deployment_id: string;
    status: string;
    resources: CloudResource[];
    logs: string[];
    error?: string;
    completed_at?: string;
}

export interface DeployRequest {
    artifact_id: string;
    target_env: string;
    config?: Record<string, unknown>;
}

export interface TriggerRunRequest {
    command: string;
    image?: string;
    env_vars?: Record<string, string>;
    timeout_seconds?: number;
    resource_size?: string;
}

export interface RemoteRun {
    run_id: string;
    config: {
        command: string;
        image: string;
        resource_size: string;
    };
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
    created_at: string;
    started_at?: string;
    completed_at?: string;
    resource_id?: string;
    exit_code?: number;
    logs_url?: string;
}

// ========== Governance Conflict ==========

export type ConflictSeverity = 'low' | 'medium' | 'high' | 'critical';
export type ConflictStatus = 'open' | 'resolved' | 'ignored';

export interface Conflict {
    conflict_id: string;
    workspace_id: string;
    rule_id: string;
    severity: ConflictSeverity;
    status: ConflictStatus;
    file_path?: string;
    line_number?: number;
    message: string;
    context?: Record<string, unknown>;
    detected_at: string;
    resolved_at?: string;
    resolved_by?: string;
}
