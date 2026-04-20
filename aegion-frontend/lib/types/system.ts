/* ══════════════════════════════════════════════════════════════
   AEGION SYSTEM TYPES — Complete Type Definitions
   ══════════════════════════════════════════════════════════════ */

// ── Governance ──
export type GovernanceTier = "T0" | "T1" | "T2" | "T3";
export type CognitiveMode = "explore" | "decide" | "execute" | "audit";

export type PipelineStage =
  | "session"
  | "distillation"
  | "sentinel"
  | "archon"
  | "memory";

export type PipelineStageStatus =
  | "completed"
  | "active"
  | "failed"
  | "waiting"
  | "skipped";

// ── Agent Types ──
export type AgentType =
  | "architecture"
  | "security"
  | "performance"
  | "ux"
  | "redteam"
  | "general";

export type AgentStatus = "waiting" | "thinking" | "decided" | "dissenting";

// ── Decision ──
export type DecisionStatus =
  | "deliberating"
  | "pending_approval"
  | "approved"
  | "rejected";

// ── Trust ──
export type TrustLevel = "validated" | "moderate" | "novel" | "unproven";

export interface TrustValidation {
  decisionId: string;
  title: string;
  age: string;
  outcome: "succeeded" | "mixed";
}

// ── Temporal ──
export type StabilityLevel = "stable" | "settling" | "volatile";

export interface TemporalInfo {
  createdAt: number;
  lastReferencedAt?: number;
  amendmentCount: number;
  stability: StabilityLevel;
}

// ── Confidence ──
export interface ConfidencePoint {
  agentId: string;
  agentType: AgentType;
  value: number;
  timestamp: number;
}

// ── Decision Meta (5-point contract) ──
export interface DecisionMeta {
  id: string;
  title: string;
  summary: string;
  tier: GovernanceTier;
  status: DecisionStatus;
  confidence: number;
  confidenceEvolution: ConfidencePoint[];
  trust: TrustLevel;
  trustValidations: TrustValidation[];
  temporal: TemporalInfo;
  riskDelta?: number;
  sessionId?: string;
  sessionName?: string;
  pipelineStages: Array<{
    stage: PipelineStage;
    status: PipelineStageStatus;
    duration?: number;
    error?: string;
  }>;
}

// ── Evidence / Opposition ──
export interface Evidence {
  id: string;
  text: string;
  source?: string;
  url?: string;
}

export interface Opposition {
  agent: { id: string; type: AgentType; name: string };
  text: string;
  rebuttal?: {
    agent: { id: string; type: AgentType };
    text: string;
  };
}

// ── Argument Graph ──
export interface Claim {
  id: string;
  agent: { id: string; type: AgentType; name: string };
  text: string;
  confidence: ConfidencePoint[];
  supports: Evidence[];
  opposes: Opposition[];
  status: "thinking" | "decided" | "withdrawn";
}

export interface ContestedZone {
  topic: string;
  agents: string[];
  confidenceRange: [number, number];
  description: string;
}

// ── System Initiative ──
export type SystemEventPriority = "critical" | "high" | "normal" | "low";
export type SystemEventType = "risk" | "proposal" | "stability" | "cost" | "memory" | "reeval";

export interface SystemEvent {
  id: string;
  type: SystemEventType;
  priority: SystemEventPriority;
  title: string;
  description: string;
  entityId?: string;
  entityType?: "decision" | "session" | "memory" | "proposal";
  timestamp: number;
  acknowledged: boolean;
}

// ── Degradation ──
export type DegradationStage = "healthy" | "degraded" | "extended" | "critical";

// ── Backend Status ──
export type BackendStatus = "connected" | "degraded" | "disconnected";

// ── System Context State ──
export interface SystemState {
  // Session
  session: {
    id: string;
    name: string;
    status: "active" | "paused" | "closed";
    mode: CognitiveMode;
    startedAt: number;
    duration: number;
    decisionsThisSession: number;
    costThisSession: number;
  } | null;

  // Active Decision
  activeDecision: {
    id: string;
    title: string;
    tier: GovernanceTier;
    status: DecisionStatus;
    pipelineStage: PipelineStage;
  } | null;

  // Risk (Sentinel)
  risk: {
    score: number;
    level: "low" | "medium" | "high" | "critical";
    trend: "rising" | "stable" | "falling";
    trendDelta: number;
    activeAlerts: number;
    topAlert: string | null;
  };

  // Governance (Archon)
  governance: {
    frozen: boolean;
    freezeReason?: string;
    pendingApprovals: number;
    pendingByTier: { T1: number; T2: number; T3: number };
    activePipelines: number;
  };

  // System
  system: {
    thinking: boolean;
    thinkingContext?: string;
    backendStatus: BackendStatus;
    degradationStage: DegradationStage;
    degradedSince?: number;
    lastSync: number;
    uptime: number;
    activeAgents: string[];
  };

  // Temporal (Chronos)
  temporal: {
    totalDecisions: number;
    oldestDecisionAge: number;
    recentDecisionRate: number;
    lastSystemEvent: {
      type: string;
      timestamp: number;
      description: string;
    } | null;
  };

  // System Initiative
  systemEvents: SystemEvent[];
  activeInterruption: SystemEvent | null;

  // Focus Mode
  focusMode: boolean;
}

// ── System Context Actions ──
export type SystemAction =
  | { type: "SESSION"; payload: SystemState["session"] }
  | { type: "GOVERNANCE"; payload: Partial<SystemState["governance"]> }
  | { type: "FREEZE"; payload: { frozen: boolean; reason?: string } }
  | { type: "RISK"; payload: Partial<SystemState["risk"]> }
  | { type: "ALERT"; payload: { count: number; topAlert: string | null } }
  | { type: "THINKING"; payload: { context?: string } }
  | { type: "THINKING_DONE"; payload: Record<string, never> }
  | { type: "SYSTEM_EVENT"; payload: SystemEvent }
  | { type: "ACKNOWLEDGE_EVENT"; payload: { eventId: string } }
  | { type: "DISMISS_INTERRUPTION"; payload: Record<string, never> }
  | { type: "SET_MODE"; payload: CognitiveMode }
  | { type: "TOGGLE_FOCUS"; payload: Record<string, never> }
  | { type: "TICK_DURATION"; payload: Record<string, never> }
  | { type: "BACKEND_STATUS"; payload: { status: BackendStatus } }
  | { type: "FULL_SYNC"; payload: Partial<SystemState> }
  | { type: "ACTIVE_DECISION"; payload: SystemState["activeDecision"] };

// ── WebSocket Message Types ──
export type WSChannel =
  | "session:lifecycle"
  | "governance:proposal"
  | "governance:freeze"
  | "sentinel:risk"
  | "sentinel:alerts"
  | "ai:reasoning"
  | "ai:response"
  | "system:initiative"
  | "system:heartbeat";

export type WSPriority = "critical" | "high" | "low";

export interface WSMessage<T = unknown> {
  channel: WSChannel;
  priority: WSPriority;
  data: T;
  timestamp: number;
}
