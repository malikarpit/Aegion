/**
 * Aegion Typed API Client
 *
 * Contract-first client matching backend OpenAPI specification.
 * Eliminates manual endpoint strings and prevents API drift.
 *
 * Client generation modes (configurable via aegion.clientGenerationMode):
 *   manual              — hand-written types only (this file)
 *   automatic           — types regenerated from OpenAPI on build
 *   automatic-with-review — generated into .tmp/, diff shown for approval
 */

// ========== Base Configuration ==========

import {
    ClientGenerationMode,
    AegionClientConfig,
    ImpactLevel,
    ReversibilityLevel,
    DecisionTier,
    ProposalStatus,
    EvidenceClassification,
    ThoughtState,
    ThoughtLinkType,
    ThoughtLink,
    ThoughtCommit,
    CreateThoughtRequest,
    UpdateThoughtRequest,
    SealThoughtRequest,
    LinkCommitRequest,
    CreateSessionRequest,
    SessionResponse,
    ReasoningPhase,
    UncertaintyLevel,
    UncertaintySource,
    UncertaintyDeclaration,
    CreateProposalRequest,
    ProposalResponse,
    ApprovalRecord,
    ApproveProposalRequest,
    InvokeCouncilRequest,
    CouncilResponse,
    HealthResponse,
    ComponentHealth,
    TimelineEvent,
    GraphNode,
    GraphEdge,
    GraphResponse,
    DriftReport,
    DriftMetric,
    DriftRequest,
    DriftStatus,
    GhostTextRequest,
    GhostTextSuggestion,
    MemorySearchResult,
    MemoryQueryResult,
    SentinelAlert,
    TaskResponse,
    TaskRunResponse,
    CreateTaskRequest,
    RunTaskRequest,
    CheckpointResponse,
    RollbackResponse,
    CreateCheckpointRequest,
    MemoryEntryResponse,
    CreateMemoryRequest,
    DecisionGraphResponse,
    SupersedeResponse,
    DecisionLineage,
    RuleResponse,
    CreateRuleRequest,
    EvaluationResult,
    SkillResponse,
    CreateSkillRequest,
    InstallSkillResponse,
    ValidateSkillResponse,
    HeartbeatRequest,
    PresenceResponse,
    WorkspacePresenceResponse,
    IncidentResponse,
    CreateIncidentRequest,
    WarRoomOverview,
    CloudResource,
    DeploymentResult,
    DeployRequest,
    TriggerRunRequest,
    RemoteRun,
    OwnershipStatus,
    TransferReason,
    OwnershipTransfer,
    SessionOwnership,
    TransferOwnershipRequest,
} from './types';

export {
    ClientGenerationMode,
    AegionClientConfig,
    ImpactLevel,
    ReversibilityLevel,
    DecisionTier,
    ProposalStatus,
    EvidenceClassification,
    ThoughtState,
    ThoughtLinkType,
    ThoughtLink,
    ThoughtCommit,
    CreateThoughtRequest,
    UpdateThoughtRequest,
    SealThoughtRequest,
    LinkCommitRequest,
    CreateSessionRequest,
    SessionResponse,
    ReasoningPhase,
    UncertaintyLevel,
    UncertaintySource,
    UncertaintyDeclaration,
    CreateProposalRequest,
    ProposalResponse,
    ApprovalRecord,
    ApproveProposalRequest,
    InvokeCouncilRequest,
    CouncilResponse,
    HealthResponse,
    ComponentHealth,
    TimelineEvent,
    GraphNode,
    GraphEdge,
    GraphResponse,
    DriftReport,
    DriftMetric,
    DriftRequest,
    DriftStatus,
    GhostTextRequest,
    GhostTextSuggestion,
    MemorySearchResult,
    MemoryQueryResult,
    SentinelAlert,
    TaskResponse,
    TaskRunResponse,
    CreateTaskRequest,
    RunTaskRequest,
    CheckpointResponse,
    RollbackResponse,
    CreateCheckpointRequest,
    MemoryEntryResponse,
    CreateMemoryRequest,
    DecisionGraphResponse,
    SupersedeResponse,
    DecisionLineage,
    RuleResponse,
    CreateRuleRequest,
    EvaluationResult,
    SkillResponse,
    CreateSkillRequest,
    InstallSkillResponse,
    ValidateSkillResponse,
    HeartbeatRequest,
    PresenceResponse,
    WorkspacePresenceResponse,
    IncidentResponse,
    CreateIncidentRequest,
    WarRoomOverview,
    CloudResource,
    DeploymentResult,
    DeployRequest,
    TriggerRunRequest,
    RemoteRun,
    OwnershipStatus,
    TransferReason,
    OwnershipTransfer,
    SessionOwnership,
    TransferOwnershipRequest,
};
// ========== API Endpoints (frozen contract — single source of truth) ==========

const API_VERSION = 'v1';
const API_PREFIX = `/api/${API_VERSION}`;

export const Endpoints = {
    // Sessions
    sessions: {
        start: () => `${API_PREFIX}/sessions/start`,
        get: (id: string) => `${API_PREFIX}/sessions/${id}`,
        close: (id: string) => `${API_PREFIX}/sessions/${id}/close`,
        list: () => `${API_PREFIX}/sessions/active`,
        active: () => `${API_PREFIX}/sessions/active`,
    },

    // Proposals
    proposals: {
        create: (_sessionId?: string) => `${API_PREFIX}/proposals`,
        get: (_sessionId: string, id: string) => `${API_PREFIX}/proposals/${id}`,
        list: (_sessionId?: string) => `${API_PREFIX}/proposals`,
        approve: (_sessionId: string, id: string) => `${API_PREFIX}/proposals/${id}/approve`,
        reject: (_sessionId: string, id: string) => `${API_PREFIX}/proposals/${id}/reject`,
        review: (_sessionId: string, id: string) => `${API_PREFIX}/proposals/${id}/review`,
        vote: (_sessionId: string, id: string) => `${API_PREFIX}/proposals/${id}/vote`,
        bySession: (sessionId: string) => `${API_PREFIX}/proposals/session/${sessionId}`,
    },

    // Council
    council: {
        invoke: (_sessionId?: string) => `${API_PREFIX}/council/invoke`,
        stream: (_sessionId?: string) => `${API_PREFIX}/council/stream`,
    },

    // Workspaces
    workspaces: {
        activity: (workspaceId: string, limit: number) => `${API_PREFIX}/workspaces/${workspaceId}/activity?limit=${limit}`,
    },

    // Health (root-level, no API_PREFIX)
    health: {
        check: () => `${API_PREFIX}/health`,
    },

    // Architecture (Timeline/ADRs)
    architecture: {
        timeline: (workspaceId: string) => `${API_PREFIX}/architecture/timeline/${workspaceId}`,
        adrs: () => `${API_PREFIX}/architecture/adrs`,
        adr: (id: string) => `${API_PREFIX}/architecture/adrs/${id}`,
    },

    // Thought-Commit Protocol (Phase 4)
    thoughts: {
        create: () => `${API_PREFIX}/thoughts`,
        get: (id: string) => `${API_PREFIX}/thoughts/${id}`,
        update: (id: string) => `${API_PREFIX}/thoughts/${id}`,
        seal: (id: string) => `${API_PREFIX}/thoughts/${id}/seal`,
        link: (id: string) => `${API_PREFIX}/thoughts/${id}/link`,
        byCommit: (sha: string) => `${API_PREFIX}/thoughts/commit/${sha}`,
    },

    // Collaboration (Phase 5)
    collaboration: {
        ownership: (sessionId: string) => `${API_PREFIX}/collaboration/session/${sessionId}/ownership`,
        claim: (sessionId: string) => `${API_PREFIX}/collaboration/session/${sessionId}/claim`,
        transfer: (sessionId: string) => `${API_PREFIX}/collaboration/session/${sessionId}/transfer`,
        release: (sessionId: string) => `${API_PREFIX}/collaboration/session/${sessionId}/release`,
    },

    // Graph
    graph: {
        decisions: (workspaceId: string) => `${API_PREFIX}/noesis/workspace/${workspaceId}/topology`,
        subgraph: (nodeId: string) => `${API_PREFIX}/noesis/decisions/${nodeId}/provenance`,
        influential: (_workspaceId: string) => `${API_PREFIX}/noesis/impact-analysis`,
    },

    // Decisions (Phase 34)
    decisions: {
        list: () => `${API_PREFIX}/decisions`,
        supersede: (id: string) => `${API_PREFIX}/decisions/${id}/supersede`,
        lineage: (id: string) => `${API_PREFIX}/decisions/${id}/lineage`,
        graph: () => `${API_PREFIX}/decisions/graph`,
    },

    // Sentinel
    sentinel: {
        drift: () => `${API_PREFIX}/sentinel/drift`,
        status: (workspaceId: string) => `${API_PREFIX}/sentinel/drift/${workspaceId}/status`,
        health: () => `${API_PREFIX}/sentinel/drift`,  // health check via drift status
        alerts: () => `${API_PREFIX}/sentinel/alerts`,
    },

    // Ghost Text
    ghostText: {
        complete: () => `${API_PREFIX}/ghost-text/complete`,
    },


    // Governance
    governance: {
        policy: () => `${API_PREFIX}/governance/policy`,
        conflicts: (workspaceId: string) => `${API_PREFIX}/governance/workspaces/${workspaceId}/conflicts`,
        scanBranch: () => `${API_PREFIX}/governance/scan/branch`,
    },

    // Events (SSE)
    events: {
        subscribe: (workspaceId: string) => `${API_PREFIX}/events/stream/${workspaceId}`,
    },



    // Delegation (Phase 35)
    delegation: {
        deploy: () => `${API_PREFIX}/delegation/deploy`,
        status: (id: string) => `${API_PREFIX}/delegation/deployments/${id}`,
        resources: () => `${API_PREFIX}/delegation/resources`,
        logs: (id: string) => `${API_PREFIX}/delegation/resources/${id}/logs`,
        health: () => `${API_PREFIX}/delegation/health`,
        // Remote Runs
        runs: {
            trigger: () => `${API_PREFIX}/delegation/runs`,
            list: () => `${API_PREFIX}/delegation/runs`,
            get: (id: string) => `${API_PREFIX}/delegation/runs/${id}`,
        },
    },

    // Tasks
    tasks: {
        create: () => `${API_PREFIX}/tasks`,
        list: () => `${API_PREFIX}/tasks`,
        get: (id: string) => `${API_PREFIX}/tasks/${id}`,
        update: (id: string) => `${API_PREFIX}/tasks/${id}`,
        run: (id: string) => `${API_PREFIX}/tasks/${id}/run`,
        runs: (id: string) => `${API_PREFIX}/tasks/${id}/runs`,
    },
    // ...
    // ...


    // Checkpoints
    checkpoints: {
        create: () => `${API_PREFIX}/checkpoints`,
        list: () => `${API_PREFIX}/checkpoints`,
        get: (id: string) => `${API_PREFIX}/checkpoints/${id}`,
        rollback: (id: string) => `${API_PREFIX}/checkpoints/${id}/rollback`,
        delete: (id: string) => `${API_PREFIX}/checkpoints/${id}`,
    },

    // Memory
    memory: {
        store: () => `${API_PREFIX}/memory`,
        list: () => `${API_PREFIX}/memory`,
        get: (id: string) => `${API_PREFIX}/memory/${id}`,
        delete: (id: string) => `${API_PREFIX}/memory/${id}`,
        query: () => `${API_PREFIX}/memory/query`,
    },

    // Rules
    rules: {
        create: () => `${API_PREFIX}/rules`,
        list: () => `${API_PREFIX}/rules`,
        get: (id: string) => `${API_PREFIX}/rules/${id}`,
        update: (id: string) => `${API_PREFIX}/rules/${id}`,
        delete: (id: string) => `${API_PREFIX}/rules/${id}`,
        evaluate: () => `${API_PREFIX}/rules/evaluate`,
    },

    // Skills
    skills: {
        create: () => `${API_PREFIX}/skills`,
        list: () => `${API_PREFIX}/skills`,
        get: (id: string) => `${API_PREFIX}/skills/${id}`,
        install: (id: string) => `${API_PREFIX}/skills/${id}/install`,
        validate: (id: string) => `${API_PREFIX}/skills/${id}/validate`,
        delete: (id: string) => `${API_PREFIX}/skills/${id}`,
    },

    // Presence
    presence: {
        heartbeat: () => `${API_PREFIX}/presence/heartbeat`,
        list: () => `${API_PREFIX}/presence`,
        get: (userId: string) => `${API_PREFIX}/presence/${userId}`,
        leave: () => `${API_PREFIX}/presence/leave`,
    },

    // War Room
    warroom: {
        overview: () => `${API_PREFIX}/warroom/overview`,
        createIncident: () => `${API_PREFIX}/warroom/incidents`,
        listIncidents: () => `${API_PREFIX}/warroom/incidents`,
        getIncident: (id: string) => `${API_PREFIX}/warroom/incidents/${id}`,
        updateIncident: (id: string) => `${API_PREFIX}/warroom/incidents/${id}`,
    },

    // Audit
    audit: {
        list: () => `${API_PREFIX}/audit/events`,
        replay: (taskId: string) => `${API_PREFIX}/audit/replay/${taskId}`,
    },

    // Admin
    admin: {
        usage: () => `${API_PREFIX}/admin/usage`,
        policyDashboard: () => `${API_PREFIX}/admin/policy-dashboard`,
    },
} as const;

// ========== Typed Client ==========

export class AegionClient {
    private config: AegionClientConfig;
    private eventSource?: EventSource;

    constructor(config: AegionClientConfig) {
        this.config = config;
    }

    public get baseUrl(): string {
        return this.config.baseUrl;
    }

    public get workspaceId(): string | undefined {
        return this.config.workspaceId;
    }

    // ========== HTTP Helpers ==========

    private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
        const url = `${this.config.baseUrl}${endpoint}`;

        // Determine intent: explicit > inferred from method
        // Cast to any because HeadersInit can be Headers|string[][] which index access doesn't support easily
        // but in our usage it is Record<string, string>
        const explicitIntent = (options?.headers as Record<string, string> | undefined)?.['X-Aegion-Intent'];
        const method = options?.method || 'GET';
        const defaultIntent = method === 'GET' ? 'read.generic' : 'write.generic';

        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.config.authToken}`,
            'X-Aegion-Session': this.config.sessionId || '',
            'X-Workspace-ID': this.config.workspaceId || '',
            'X-Aegion-Intent': explicitIntent || defaultIntent,
        };

        // Remove empty headers if necessary, but empty session/workspace might be valid for some endpoints?
        // Backend determines validity.

        const response = await fetch(url, {
            ...options,
            headers: {
                ...headers,
                ...options?.headers,
            },
        });

        if (!response.ok) {
            if (response.status === 401) {
                // eslint-disable-next-line @typescript-eslint/no-var-requires
                const vscode = require('vscode');
                const selection = await vscode.window.showErrorMessage(
                    'Aegion: Session token is expired or has been revoked. Please re-authenticate.',
                    'Re-authenticate',
                    'Dismiss',
                );
                if (selection === 'Re-authenticate') {
                    vscode.commands.executeCommand('aegion.setAuthToken');
                }
            }

            let errorBody: Record<string, unknown>;
            try {
                errorBody = await response.json() as Record<string, unknown>;
            } catch {
                errorBody = { detail: response.statusText };
            }
            throw new AegionAPIError(
                response.status,
                String(errorBody.detail || 'API Request Failed'),
                errorBody,
            );
        }

        return response.json() as Promise<T>;
    }

    public async get<T = any>(endpoint: string, options?: RequestInit): Promise<T> {
        return this.fetch<T>(endpoint, options);
    }

    // ========== Sessions ==========

    async startSession(req: CreateSessionRequest): Promise<SessionResponse> {
        return this.fetch(Endpoints.sessions.start(), {
            method: 'POST',
            body: JSON.stringify(req),
            headers: { 'X-Aegion-Intent': 'session.start' },
        });
    }

    async getSession(sessionId: string): Promise<SessionResponse> {
        return this.fetch(Endpoints.sessions.get(sessionId));
    }

    async getActiveSessions(): Promise<SessionResponse[]> {
        return this.fetch(Endpoints.sessions.active());
    }

    async closeSession(sessionId: string): Promise<void> {
        return this.fetch(Endpoints.sessions.close(sessionId), {
            method: 'POST',
            headers: { 'X-Aegion-Intent': 'session.close' },
        });
    }

    // ========== Proposals ==========

    async createProposal(sessionId: string, req: CreateProposalRequest): Promise<ProposalResponse> {
        return this.fetch(Endpoints.proposals.create(sessionId), {
            method: 'POST',
            body: JSON.stringify(req),
            headers: { 'X-Aegion-Intent': 'proposal.create' },
        });
    }

    async getProposal(sessionId: string, id: string): Promise<ProposalResponse> {
        return this.fetch(Endpoints.proposals.get(sessionId, id));
    }

    async listProposals(sessionId: string): Promise<ProposalResponse[]> {
        return this.fetch(Endpoints.proposals.list(sessionId));
    }

    async listPendingProposals(): Promise<ProposalResponse[]> {
        return this.fetch(Endpoints.proposals.list() + '?status=pending_review');
    }

    async approveProposal(sessionId: string, proposalId: string, req: ApproveProposalRequest): Promise<ProposalResponse> {
        return this.fetch(Endpoints.proposals.approve(sessionId, proposalId), {
            method: 'POST',
            body: JSON.stringify(req),
            headers: { 'X-Aegion-Intent': 'proposal.approve' },
        });
    }

    async rejectProposal(sessionId: string, proposalId: string, justification: string, evidenceIds: string[] = []): Promise<ProposalResponse> {
        return this.fetch(Endpoints.proposals.reject(sessionId, proposalId), {
            method: 'POST',
            body: JSON.stringify({ evidence_ids: evidenceIds, justification }),
            headers: { 'X-Aegion-Intent': 'proposal.reject' },
        });
    }

    async submitForReview(sessionId: string, proposalId: string): Promise<ProposalResponse> {
        return this.fetch(Endpoints.proposals.review(sessionId, proposalId), {
            method: 'POST',
            headers: { 'X-Aegion-Intent': 'proposal.review' },
        });
    }

    async listDecisions(sessionId?: string): Promise<ProposalResponse[]> {
        if (sessionId) {
            return this.listProposals(sessionId);
        }
        return this.listPendingProposals();
    }

    // ========== AI Council ==========

    async invokeCouncil(
        sessionId: string,
        request: InvokeCouncilRequest,
    ): Promise<CouncilResponse> {
        return this.fetch(Endpoints.council.invoke(sessionId), {
            method: 'POST',
            body: JSON.stringify(request),
            headers: { 'X-Aegion-Intent': 'council.invoke' },
        });
    }

    async *invokeCouncilStream(
        sessionId: string,
        request: InvokeCouncilRequest,
    ): AsyncGenerator<string> {
        const url = `${this.config.baseUrl}${Endpoints.council.stream(sessionId)}`;
        // Use fetch for POST streaming
        const response = await fetch(url, {
            method: 'POST',
            body: JSON.stringify(request),
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.config.authToken}`,
                'X-Aegion-Session': sessionId,
                'X-Aegion-Intent': 'council.invoke',
            },
        });

        if (!response.ok) {
            throw new Error(`Council stream failed: ${response.statusText}`);
        }

        if (response.body) {
            // Handle streaming response
            if (response.body.getReader) {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) { break; }
                    yield decoder.decode(value, { stream: true });
                }
            } else {
                // Node.js ReadableStream
                for await (const chunk of response.body) {
                    yield new TextDecoder().decode(chunk);
                }
            }
        }
    }


    // ========== Health ==========

    async checkHealth(): Promise<HealthResponse> {
        return this.fetch(Endpoints.health.check());
    }

    async checkLiveness(): Promise<{ status: string }> {
        return this.fetch(Endpoints.health.check());
    }

    async checkReadiness(): Promise<{ status: string }> {
        return this.fetch(Endpoints.health.check());
    }

    // ========== Timeline & Architecture ==========

    async getTimeline(workspaceId: string): Promise<{ events: TimelineEvent[] }> { // Using any or specific type
        return this.fetch(Endpoints.architecture.timeline(workspaceId));
    }

    async getADRs(): Promise<ADRRecord[]> {
        return this.fetch(Endpoints.architecture.adrs());
    }

    async getADR(id: string): Promise<ADRRecord> {
        return this.fetch(Endpoints.architecture.adr(id));
    }

    // ========== Thought-Commit Protocol ==========

    async createThought(req: CreateThoughtRequest): Promise<ThoughtCommit> {
        return this.fetch(Endpoints.thoughts.create(), {
            method: 'POST',
            body: JSON.stringify(req),
        });
    }

    async getThought(id: string): Promise<ThoughtCommit> {
        return this.fetch(Endpoints.thoughts.get(id));
    }

    async updateThought(id: string, req: UpdateThoughtRequest): Promise<ThoughtCommit> {
        return this.fetch(Endpoints.thoughts.update(id), {
            method: 'PATCH',
            body: JSON.stringify(req),
        });
    }

    async sealThought(id: string, req: SealThoughtRequest = {}): Promise<ThoughtCommit> {
        return this.fetch(Endpoints.thoughts.seal(id), {
            method: 'POST',
            body: JSON.stringify(req),
        });
    }

    async linkThoughtToCommit(id: string, req: LinkCommitRequest): Promise<ThoughtLink> {
        return this.fetch(Endpoints.thoughts.link(id), {
            method: 'POST',
            body: JSON.stringify(req),
        });
    }

    async getThoughtByCommit(commitSha: string): Promise<ThoughtCommit> {
        return this.fetch(Endpoints.thoughts.byCommit(commitSha));
    }

    // ========== Collaboration (Phase 5) ==========

    async getSessionOwnership(sessionId: string): Promise<SessionOwnership> {
        return this.fetch(Endpoints.collaboration.ownership(sessionId));
    }

    async claimOwnership(sessionId: string, force: boolean = false): Promise<SessionOwnership> {
        return this.fetch(Endpoints.collaboration.claim(sessionId), {
            method: 'POST',
            body: JSON.stringify({ force }),
            headers: { 'X-Aegion-Intent': 'collaboration.claim' },
        });
    }

    async transferOwnership(sessionId: string, targetUserId: string): Promise<SessionOwnership> {
        return this.fetch(Endpoints.collaboration.transfer(sessionId), {
            method: 'POST',
            body: JSON.stringify({ target_user_id: targetUserId }),
            headers: { 'X-Aegion-Intent': 'collaboration.transfer' },
        });
    }

    async releaseOwnership(sessionId: string): Promise<SessionOwnership> {
        return this.fetch(Endpoints.collaboration.release(sessionId), {
            method: 'POST',
            headers: { 'X-Aegion-Intent': 'collaboration.release' },
        });
    }

    // Property accessor
    get thoughts() {
        return {
            create: (req: CreateThoughtRequest) => this.createThought(req),
            get: (id: string) => this.getThought(id),
            update: (id: string, req: UpdateThoughtRequest) => this.updateThought(id, req),
            seal: (id: string, req: SealThoughtRequest = {}) => this.sealThought(id, req),
            linkCommit: (id: string, req: LinkCommitRequest) => this.linkThoughtToCommit(id, req),
            getByCommit: (sha: string) => this.getThoughtByCommit(sha),
        };
    }

    // ========== Graph ==========

    // getDecisionGraph replaced by specialized version below
    // async getDecisionGraph(workspaceId: string): Promise<GraphResponse> {
    //     return this.fetch(Endpoints.graph.decisions(workspaceId));
    // }

    async getSubgraph(nodeId: string, radius?: number): Promise<GraphResponse> {
        const endpoint = radius
            ? `${Endpoints.graph.subgraph(nodeId)}?radius=${radius}`
            : Endpoints.graph.subgraph(nodeId);
        return this.fetch(endpoint);
    }

    async getInfluentialDecisions(
        workspaceId: string,
        limit?: number,
    ): Promise<GraphNode[]> {
        const endpoint = limit
            ? `${Endpoints.graph.influential(workspaceId)}?limit=${limit}`
            : Endpoints.graph.influential(workspaceId);
        return this.fetch(endpoint);
    }

    // ========== Sentinel ==========

    async detectDrift(request: DriftRequest): Promise<DriftReport> {
        return this.fetch(Endpoints.sentinel.drift(), {
            method: 'POST',
            body: JSON.stringify(request),
        });
    }

    async getDriftStatus(workspaceId: string): Promise<DriftStatus> {
        return this.fetch(Endpoints.sentinel.status(workspaceId));
    }

    // Legacy method for compatibility (maps to status for now)
    async getDriftReport(workspaceId: string): Promise<DriftStatus> {
        return this.getDriftStatus(workspaceId);
    }

    async getSentinelHealth(workspaceId: string): Promise<HealthResponse> {
        // Map to alerts or status? Logic unclear in backend, returning status for now
        return this.fetch(Endpoints.sentinel.status(workspaceId));
    }

    // ========== Governance ==========

    async getConflicts(workspaceId: string): Promise<unknown[]> {
        return this.fetch(Endpoints.governance.conflicts(workspaceId));
    }

    async scanBranch(baseBranch: string, headBranch: string): Promise<unknown[]> {
        return this.fetch(Endpoints.governance.scanBranch(), {
            method: 'POST',
            body: JSON.stringify({
                workspace_id: this.config.workspaceId,
                base_branch: baseBranch,
                head_branch: headBranch,
            }),
        });
    }

    // ========== Events ==========

    subscribeToEvents(
        workspaceId: string,
        handlers: {
            onProposal?: (data: ProposalResponse) => void;
            onApproval?: (data: ApprovalRecord) => void;
            onHealth?: (data: HealthResponse) => void;
            onError?: (error: Error) => void;
        },
    ): () => void {
        const url = `${this.config.baseUrl}${Endpoints.events.subscribe(workspaceId)}`;
        const eventSource = new EventSource(url);

        eventSource.addEventListener('proposal', (event) => {
            const messageEvent = event as MessageEvent;
            handlers.onProposal?.(JSON.parse(messageEvent.data));
        });

        eventSource.addEventListener('approval', (event) => {
            const messageEvent = event as MessageEvent;
            handlers.onApproval?.(JSON.parse(messageEvent.data));
        });

        eventSource.addEventListener('health', (event) => {
            const messageEvent = event as MessageEvent;
            handlers.onHealth?.(JSON.parse(messageEvent.data));
        });

        eventSource.onerror = () => {
            handlers.onError?.(new Error('Event stream error'));
        };

        return () => eventSource.close();
    }

    // ========== Configuration ==========

    setSession(sessionId: string): void {
        this.config.sessionId = sessionId;
    }

    setWorkspace(workspaceId: string): void {
        this.config.workspaceId = workspaceId;
    }

    setAuthToken(token: string): void {
        this.config.authToken = token;
    }

    // ========== Extended Methods for View Compatibility ==========

    async healthCheck(): Promise<HealthResponse> {
        return this.checkHealth();
    }

    async completeGhostText(
        promptOrContext: string | GhostTextRequest,
        context?: Record<string, unknown>,
    ): Promise<GhostTextSuggestion> {
        // Support both old string-based API and new object API
        const body = typeof promptOrContext === 'string'
            ? { prompt: promptOrContext, context }
            : promptOrContext;

        const response = await this.fetch<GhostTextSuggestion>(Endpoints.ghostText.complete(), {
            method: 'POST',
            body: JSON.stringify(body),
        });
        return response;
    }

    async generateADR(proposalId: string): Promise<{ adr: string; markdown: string; title: string }> {
        // ADRs are managed via the architecture endpoints, not per-proposal
        const response = await this.fetch<{ adr: string; markdown?: string; title?: string }>(
            Endpoints.architecture.adrs(),
            { method: 'POST', body: JSON.stringify({ proposal_id: proposalId }) },
        );
        return {
            adr: response.adr,
            markdown: response.markdown || response.adr,
            title: response.title || `ADR for ${proposalId}`,
        };
    }

    // queryMemory returns array-like for iteration with .map(), .length, .slice()
    async queryMemory(query: string): Promise<MemoryQueryResult> {
        const response = await this.fetch<{ results: MemorySearchResult[]; summary?: string }>(
            Endpoints.memory.query(),
            {
                method: 'POST',
                body: JSON.stringify({ query }),
            },
        );
        return new MemoryQueryResult(response.results || [], response.summary || '');
    }

    async getGovernancePolicy(): Promise<Record<string, unknown>> {
        return this.fetch(Endpoints.governance.policy());
    }

    async getSentinelAlerts(): Promise<SentinelAlert[]> {
        const response = await this.fetch<{ alerts: SentinelAlert[] }>(Endpoints.sentinel.alerts());
        return response.alerts || [];
    }

    async addReview(
        sessionId: string,
        proposalId: string,
        verdict: string,
        comments: string,
    ): Promise<ProposalResponse> {
        // Map verdict to decision actions
        if (verdict === 'approve') {
            return this.approveProposal(sessionId, proposalId, { evidence_ids: [], justification: comments });
        } else if (verdict === 'request_changes' || verdict === 'reject') {
            return this.rejectProposal(sessionId, proposalId, comments);
        }
        return this.getProposal(sessionId, proposalId);
    }

    // Convenience property accessors (namespace pattern for views)
    get proposals() {
        return {
            list: (sessionId: string) => this.listProposals(sessionId),
            get: (sessionId: string, id: string) => this.getProposal(sessionId, id),
            create: (sessionId: string, req: CreateProposalRequest) => this.createProposal(sessionId, req),
            approve: (sessionId: string, id: string, req: ApproveProposalRequest) => this.approveProposal(sessionId, id, req),
            reject: (sessionId: string, id: string, reason: string) => this.rejectProposal(sessionId, id, reason),
            review: (sessionId: string, id: string) => this.submitForReview(sessionId, id),
            addReview: (sessionId: string, id: string, verdict: string, comments: string) => this.addReview(sessionId, id, verdict, comments),
        };
    }

    get sessions() {
        return {
            start: (req: CreateSessionRequest) => this.startSession(req),
            get: (id: string) => this.getSession(id),
            close: (id: string) => this.closeSession(id),
        };
    }

    get workspaces() {
        // Real endpoint usage where available
        return {
            get: (id: string) => Promise.resolve({ workspace_id: id, name: 'Default Workspace' }), // Mock for now if endpoint missing
            list: () => Promise.resolve([]),
            getActivity: async (id: string, limit: number = 50) => {
                return this.fetch(Endpoints.workspaces.activity(id, limit));
            },
        };
    }

    // ========== Task Inbox ==========

    async createTask(req: CreateTaskRequest): Promise<TaskResponse> {
        return this.fetch(Endpoints.tasks.create(), {
            method: 'POST',
            body: JSON.stringify(req),
        });
    }

    async listTasks(statusFilter?: string, sessionId?: string): Promise<TaskResponse[]> {
        let url = Endpoints.tasks.list();
        const params: string[] = [];
        if (statusFilter) { params.push(`status_filter=${statusFilter}`); }
        if (sessionId) { params.push(`session_id=${sessionId}`); }
        if (params.length) { url += `?${params.join('&')}`; }
        return this.fetch(url);
    }

    async getTask(taskId: string): Promise<TaskResponse> {
        return this.fetch(Endpoints.tasks.get(taskId));
    }

    async updateTask(taskId: string, updates: Partial<Pick<TaskResponse, 'title' | 'description' | 'status' | 'priority' | 'assignee' | 'tags'>>): Promise<TaskResponse> {
        return this.fetch(Endpoints.tasks.update(taskId), {
            method: 'PATCH',
            body: JSON.stringify(updates),
        });
    }

    async runTask(taskId: string, req?: RunTaskRequest): Promise<TaskRunResponse> {
        return this.fetch(Endpoints.tasks.run(taskId), {
            method: 'POST',
            body: JSON.stringify(req || {}),
        });
    }

    async getTaskRuns(taskId: string): Promise<TaskRunResponse[]> {
        return this.fetch(Endpoints.tasks.runs(taskId));
    }

    get tasks() {
        return {
            create: (req: CreateTaskRequest) => this.createTask(req),
            list: (statusFilter?: string, sessionId?: string) => this.listTasks(statusFilter, sessionId),
            get: (id: string) => this.getTask(id),
            update: (id: string, updates: Partial<Pick<TaskResponse, 'title' | 'description' | 'status' | 'priority' | 'assignee' | 'tags'>>) => this.updateTask(id, updates),
            run: (id: string, req?: RunTaskRequest) => this.runTask(id, req),
            runs: (id: string) => this.getTaskRuns(id),
        };
    }

    // ========== Checkpoints ==========

    async createCheckpoint(req: CreateCheckpointRequest): Promise<CheckpointResponse> {
        return this.fetch(Endpoints.checkpoints.create(), {
            method: 'POST',
            body: JSON.stringify(req),
        });
    }

    async listCheckpoints(sessionId?: string): Promise<CheckpointResponse[]> {
        let url = Endpoints.checkpoints.list();
        if (sessionId) { url += `?session_id=${sessionId}`; }
        return this.fetch(url);
    }

    async getCheckpoint(checkpointId: string): Promise<CheckpointResponse> {
        return this.fetch(Endpoints.checkpoints.get(checkpointId));
    }

    async rollbackToCheckpoint(checkpointId: string): Promise<RollbackResponse> {
        return this.fetch(Endpoints.checkpoints.rollback(checkpointId), {
            method: 'POST',
        });
    }

    async deleteCheckpoint(checkpointId: string): Promise<void> {
        await this.fetch(Endpoints.checkpoints.delete(checkpointId), {
            method: 'DELETE',
        });
    }

    get checkpoints() {
        return {
            create: (req: CreateCheckpointRequest) => this.createCheckpoint(req),
            list: (sessionId?: string) => this.listCheckpoints(sessionId),
            get: (id: string) => this.getCheckpoint(id),
            rollback: (id: string) => this.rollbackToCheckpoint(id),
            delete: (id: string) => this.deleteCheckpoint(id),
        };
    }

    // ========== Memory ==========

    async storeMemory(req: CreateMemoryRequest): Promise<MemoryEntryResponse> {
        return this.fetch(Endpoints.memory.store(), { method: 'POST', body: JSON.stringify(req) });
    }

    async listMemory(scope?: string, tag?: string): Promise<MemoryEntryResponse[]> {
        let url = Endpoints.memory.list();
        const params: string[] = [];
        if (scope) { params.push(`scope=${scope}`); }
        if (tag) { params.push(`tag=${tag}`); }
        if (params.length) { url += `?${params.join('&')}`; }
        return this.fetch(url);
    }

    async getMemory(id: string): Promise<MemoryEntryResponse> {
        return this.fetch(Endpoints.memory.get(id));
    }

    async deleteMemory(id: string): Promise<void> {
        await this.fetch(Endpoints.memory.delete(id), { method: 'DELETE' });
    }

    get memory() {
        return {
            store: (req: CreateMemoryRequest) => this.storeMemory(req),
            list: (scope?: string, tag?: string) => this.listMemory(scope, tag),
            get: (id: string) => this.getMemory(id),
            delete: (id: string) => this.deleteMemory(id),
        };
    }



    // ========== Decisions ==========

    async getDecisionGraph(workspaceId?: string): Promise<DecisionGraphResponse> {
        const url = Endpoints.decisions.graph();
        return this.fetch(url, {
            headers: workspaceId ? { 'X-Workspace-Id': workspaceId } : undefined,
        });
    }

    async getDecisionLineage(decisionId: string): Promise<DecisionLineage[]> {
        return this.fetch(Endpoints.decisions.lineage(decisionId));
    }

    async supersedeDecision(decisionId: string, newProposalId: string, justification: string): Promise<SupersedeResponse> {
        return this.fetch(Endpoints.decisions.supersede(decisionId), {
            method: 'POST',
            body: JSON.stringify({ new_proposal_id: newProposalId, justification }),
        });
    }

    // ========== Rules ==========

    async createRule(req: CreateRuleRequest): Promise<RuleResponse> {
        return this.fetch(Endpoints.rules.create(), { method: 'POST', body: JSON.stringify(req) });
    }

    async listRules(scope?: string): Promise<RuleResponse[]> {
        let url = Endpoints.rules.list();
        if (scope) { url += `?scope=${scope}`; }
        return this.fetch(url);
    }

    async getRule(id: string): Promise<RuleResponse> {
        return this.fetch(Endpoints.rules.get(id));
    }

    async updateRule(id: string, updates: Partial<Pick<RuleResponse, 'name' | 'description' | 'condition' | 'action' | 'priority' | 'enabled' | 'tags'>>): Promise<RuleResponse> {
        return this.fetch(Endpoints.rules.update(id), { method: 'PATCH', body: JSON.stringify(updates) });
    }

    async deleteRule(id: string): Promise<void> {
        await this.fetch(Endpoints.rules.delete(id), { method: 'DELETE' });
    }

    async evaluateRules(context: Record<string, unknown>, scope?: string): Promise<EvaluationResult> {
        return this.fetch(Endpoints.rules.evaluate(), { method: 'POST', body: JSON.stringify({ context, scope }) });
    }

    get rules() {
        return {
            create: (req: CreateRuleRequest) => this.createRule(req),
            list: (scope?: string) => this.listRules(scope),
            get: (id: string) => this.getRule(id),
            update: (id: string, updates: Partial<Pick<RuleResponse, 'name' | 'description' | 'condition' | 'action' | 'priority' | 'enabled' | 'tags'>>) => this.updateRule(id, updates),
            delete: (id: string) => this.deleteRule(id),
            evaluate: (context: Record<string, unknown>, scope?: string) => this.evaluateRules(context, scope),
        };
    }

    // ========== Skills ==========

    async createSkill(req: CreateSkillRequest): Promise<SkillResponse> {
        return this.fetch(Endpoints.skills.create(), { method: 'POST', body: JSON.stringify(req) });
    }

    async listSkills(category?: string): Promise<SkillResponse[]> {
        let url = Endpoints.skills.list();
        if (category) { url += `?category=${category}`; }
        return this.fetch(url);
    }

    async getSkill(id: string): Promise<SkillResponse> {
        return this.fetch(Endpoints.skills.get(id));
    }

    async installSkill(id: string): Promise<InstallSkillResponse> {
        return this.fetch(Endpoints.skills.install(id), { method: 'POST' });
    }

    async validateSkill(id: string): Promise<ValidateSkillResponse> {
        return this.fetch(Endpoints.skills.validate(id), { method: 'POST' });
    }

    async deleteSkill(id: string): Promise<void> {
        await this.fetch(Endpoints.skills.delete(id), { method: 'DELETE' });
    }

    get skills() {
        return {
            create: (req: CreateSkillRequest) => this.createSkill(req),
            list: (category?: string) => this.listSkills(category),
            get: (id: string) => this.getSkill(id),
            install: (id: string) => this.installSkill(id),
            validate: (id: string) => this.validateSkill(id),
            delete: (id: string) => this.deleteSkill(id),
        };
    }

    // ========== Presence ==========

    async sendHeartbeat(req: HeartbeatRequest): Promise<PresenceResponse> {
        return this.fetch(Endpoints.presence.heartbeat(), { method: 'POST', body: JSON.stringify(req) });
    }

    async getWorkspacePresence(): Promise<WorkspacePresenceResponse> {
        return this.fetch(Endpoints.presence.list());
    }

    async getUserPresence(userId: string): Promise<PresenceResponse> {
        return this.fetch(Endpoints.presence.get(userId));
    }

    async leavePresence(): Promise<void> {
        await this.fetch(Endpoints.presence.leave(), { method: 'POST' });
    }

    get presence() {
        return {
            heartbeat: (req: HeartbeatRequest) => this.sendHeartbeat(req),
            list: () => this.getWorkspacePresence(),
            get: (userId: string) => this.getUserPresence(userId),
            leave: () => this.leavePresence(),
        };
    }

    // ========== War Room ==========

    async getWarRoomOverview(): Promise<WarRoomOverview> {
        return this.fetch(Endpoints.warroom.overview());
    }

    async createIncident(req: CreateIncidentRequest): Promise<IncidentResponse> {
        return this.fetch(Endpoints.warroom.createIncident(), { method: 'POST', body: JSON.stringify(req) });
    }

    async listIncidents(status?: string, severity?: string): Promise<IncidentResponse[]> {
        let url = Endpoints.warroom.listIncidents();
        const params = new URLSearchParams();
        if (status) { params.append('status_filter', status); }
        if (severity) { params.append('severity', severity); }
        if (params.toString()) { url += `?${params.toString()}`; }
        return this.fetch(url);
    }

    async updateIncident(id: string, statusUpdate: string): Promise<IncidentResponse> {
        return this.fetch(`${Endpoints.warroom.updateIncident(id)}?status_update=${statusUpdate}`, { method: 'PATCH' });
    }

    get warroom() {
        return {
            overview: () => this.getWarRoomOverview(),
            createIncident: (req: CreateIncidentRequest) => this.createIncident(req),
            listIncidents: (status?: string, severity?: string) => this.listIncidents(status, severity),
            resolveIncident: (id: string) => this.updateIncident(id, 'resolved'),
        };
    }
    // ========== Delegation ==========

    async deployArtifact(req: DeployRequest): Promise<DeploymentResult> {
        return this.fetch(Endpoints.delegation.deploy(), { method: 'POST', body: JSON.stringify(req) });
    }

    async getDeploymentStatus(id: string): Promise<DeploymentResult> {
        return this.fetch(Endpoints.delegation.status(id));
    }

    async listCloudResources(env: string = 'dev', type?: string): Promise<CloudResource[]> {
        let url = `${Endpoints.delegation.resources()}?env=${env}`;
        if (type) { url += `&type=${type}`; }
        return this.fetch(url);
    }

    async getResourceLogs(id: string): Promise<string[]> {
        return this.fetch(Endpoints.delegation.logs(id));
    }

    async checkProviderHealth(): Promise<Record<string, unknown>> {
        return this.fetch(Endpoints.delegation.health());
    }

    async triggerRun(req: TriggerRunRequest): Promise<RemoteRun> {
        return this.fetch(Endpoints.delegation.runs.trigger(), {
            method: 'POST',
            body: JSON.stringify(req),
        });
    }

    async listRuns(status?: string): Promise<RemoteRun[]> {
        let url = Endpoints.delegation.runs.list();
        if (status) {
            url += `?status=${status}`;
        }
        return this.fetch(url);
    }

    async getRun(id: string): Promise<RemoteRun> {
        return this.fetch(Endpoints.delegation.runs.get(id));
    }

    get delegation() {
        return {
            deploy: (req: DeployRequest) => this.deployArtifact(req),
            status: (id: string) => this.getDeploymentStatus(id),
            listResources: (env?: string, type?: string) => this.listCloudResources(env, type),
            logs: (id: string) => this.getResourceLogs(id),
            health: () => this.checkProviderHealth(),
            runs: {
                trigger: (req: TriggerRunRequest) => this.triggerRun(req),
                list: (status?: string) => this.listRuns(status),
                get: (id: string) => this.getRun(id),
            },
        };
    }

    // ========== Audit ==========

    get audit() {
        return {
            listEvents: (filters?: { action?: string; actor?: string }) => {
                let url = Endpoints.audit.list();
                const params = new URLSearchParams();
                if (filters?.action) { params.append('action', filters.action); }
                if (filters?.actor) { params.append('actor', filters.actor); }
                if (params.toString()) { url += `?${params.toString()}`; }
                return this.fetch<unknown[]>(url);
            },
            replay: (taskId: string) => this.fetch<unknown>(Endpoints.audit.replay(taskId)),
        };
    }

    // ========== Admin ==========

    get admin() {
        return {
            getUsage: () => this.fetch<unknown>(Endpoints.admin.usage()),
            getPolicyDashboard: () =>
                this.fetch<unknown>(Endpoints.admin.policyDashboard()),
        };
    }
}

// ========== Error Class ==========

export class AegionAPIError extends Error {
    constructor(
        public status: number,
        message: string,
        public details?: unknown,
    ) {
        super(message);
        this.name = 'AegionAPIError';
    }

    isNotFound(): boolean {
        return this.status === 404;
    }

    isUnauthorized(): boolean {
        return this.status === 401;
    }

    isForbidden(): boolean {
        return this.status === 403;
    }

    isRateLimited(): boolean {
        return this.status === 429;
    }


}

// ========== Factory ==========

export function createAegionClient(config: AegionClientConfig): AegionClient {
    return new AegionClient(config);
}

// ========== Backwards Compatibility ==========

// Type aliases for existing code
export type Proposal = ProposalResponse;
export type SessionStartResponse = SessionResponse;
export type Session = SessionResponse;
export { AegionClient as AegionApiClient };

// Additional types for existing views
export interface WorkspaceMember {
    user_id: string;
    email?: string;
    display_name: string;
    role: 'owner' | 'admin' | 'member' | 'viewer';
    joined_at: string;
    status: 'active' | 'pending' | 'inactive';
}

export interface ADRRecord {
    adr_id: string;
    title: string;
    status: 'proposed' | 'accepted' | 'deprecated' | 'superseded';
    created_at: string;
    author_id: string;
    decision_id?: string;
}

export interface FailureModeRecord {
    mode_id: string;
    name: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
    likelihood: 'rare' | 'unlikely' | 'possible' | 'likely' | 'certain';
    mitigation?: string;
    last_analyzed: string;
}

export interface ObservabilityMetric {
    metric_id: string;
    name: string;
    value: number;
    unit: string;
    timestamp: string;
    labels?: Record<string, string>;
}

export interface SentinelHealthData {
    overall_status: 'healthy' | 'degraded' | 'unhealthy';
    risk_score: number;
    staleness_ratio: number;
    last_check: string;
    components: Record<string, ComponentHealth>;
}

// Singleton client instance
let _apiClient: AegionClient | null = null;

export function getApiClient(): AegionClient {
    if (!_apiClient) {
        // Read base URL from VS Code settings (aegion.backendUrl),
        // falling back to localhost for local development.
        // Users deploying to remote servers MUST configure this setting
        // to their backend's URL (e.g., https://api.aegion.io).
        let baseUrl = 'http://localhost:8000';
        let authToken = '';
        try {
            // eslint-disable-next-line @typescript-eslint/no-var-requires
            const vscode = require('vscode');
            const config = vscode.workspace.getConfiguration('aegion');
            const configured = config.get('backendUrl') as string | undefined;
            if (configured) {
                // Strip trailing slash to avoid double-slash in URL construction
                baseUrl = configured.replace(/\/+$/, '');
            }
            authToken = config.get('authToken') as string || '';
        } catch {
            // Running outside VS Code context (tests, CLI) — use default
        }
        _apiClient = new AegionClient({ baseUrl, authToken });
    }
    return _apiClient;
}

export function initializeApiClient(config: AegionClientConfig): AegionClient {
    _apiClient = new AegionClient(config);
    return _apiClient;
}


