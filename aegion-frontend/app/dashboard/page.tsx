"use client";

import React from "react";
import Link from "next/link";
import {
  FileCheck,
  Brain,
  DollarSign,
  Shield,
  Activity,
  ChevronRight,
  Zap,
  Clock,
} from "lucide-react";
import { useSystemContext } from "@/lib/context/SystemContext";
import { GovernancePipeline } from "@/components/cognitive/GovernancePipeline";
import { TemporalMeta } from "@/components/cognitive/TemporalMeta";
import { TrustBadge } from "@/components/cognitive/TrustBadge";
import { ConfidenceEvolution } from "@/components/cognitive/ConfidenceEvolution";
import { SystemInterruptionBanner } from "@/components/cognitive/SystemInterruptionBanner";
import { EntryExperienceLoop } from "@/components/cognitive/EntryExperienceLoop";
import type {
  GovernanceTier,
  DecisionStatus,
  TrustLevel,
  StabilityLevel,
  PipelineStageStatus,
  ConfidencePoint,
  SystemEvent,
} from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   DASHBOARD — Cognitive OS Command Center
   
   Not a "metrics dashboard." A cognitive overview:
   - KPIs with meaning (not just numbers)
   - Active pipeline status
   - Recent decisions (with tier, trust, temporal)
   - System initiative feed
   - Sentinel mini + risk gauge
   - Entry experience for new users
   ══════════════════════════════════════════════════════════════ */

// ── Seed data (replaced by API in production) ──
const SEED_DECISIONS: Array<{
  id: string;
  title: string;
  tier: GovernanceTier;
  status: DecisionStatus;
  confidence: number;
  confidenceEvolution: ConfidencePoint[];
  trust: TrustLevel;
  createdAt: number;
  stability: StabilityLevel;
  pipeline: Array<{ stage: "session" | "distillation" | "sentinel" | "archon" | "memory"; status: PipelineStageStatus }>;
}> = [
  {
    id: "42",
    title: "Use Redis for Session Caching",
    tier: "T1",
    status: "approved",
    confidence: 0.87,
    confidenceEvolution: [
      { agentId: "a1", agentType: "architecture", value: 0.82, timestamp: Date.now() - 3600000 },
      { agentId: "a2", agentType: "performance", value: 0.90, timestamp: Date.now() - 2400000 },
      { agentId: "a3", agentType: "security", value: 0.85, timestamp: Date.now() - 1200000 },
    ],
    trust: "validated",
    createdAt: Date.now() - 86400000 * 12,
    stability: "stable",
    pipeline: [
      { stage: "session", status: "completed" },
      { stage: "distillation", status: "completed" },
      { stage: "sentinel", status: "completed" },
      { stage: "archon", status: "completed" },
      { stage: "memory", status: "completed" },
    ],
  },
  {
    id: "41",
    title: "Add Rate Limiting to API Gateway",
    tier: "T2",
    status: "pending_approval",
    confidence: 0.72,
    confidenceEvolution: [
      { agentId: "a1", agentType: "architecture", value: 0.65, timestamp: Date.now() - 1800000 },
      { agentId: "a2", agentType: "security", value: 0.78, timestamp: Date.now() - 1200000 },
      { agentId: "a3", agentType: "performance", value: 0.72, timestamp: Date.now() - 600000 },
    ],
    trust: "moderate",
    createdAt: Date.now() - 86400000 * 2,
    stability: "settling",
    pipeline: [
      { stage: "session", status: "completed" },
      { stage: "distillation", status: "completed" },
      { stage: "sentinel", status: "completed" },
      { stage: "archon", status: "active" },
      { stage: "memory", status: "waiting" },
    ],
  },
  {
    id: "40",
    title: "Migrate Auth to JWT + RBAC",
    tier: "T3",
    status: "deliberating",
    confidence: 0.58,
    confidenceEvolution: [
      { agentId: "a1", agentType: "architecture", value: 0.55, timestamp: Date.now() - 3600000 },
      { agentId: "a2", agentType: "security", value: 0.60, timestamp: Date.now() - 2400000 },
    ],
    trust: "novel",
    createdAt: Date.now() - 86400000,
    stability: "volatile",
    pipeline: [
      { stage: "session", status: "completed" },
      { stage: "distillation", status: "completed" },
      { stage: "sentinel", status: "active" },
      { stage: "archon", status: "waiting" },
      { stage: "memory", status: "waiting" },
    ],
  },
];

const SEED_ACTIVITY: Array<Partial<SystemEvent> & { user?: string; action: string }> = [
  { id: "ev1", type: "reeval", priority: "high", title: "Council deliberation on #40 in progress", description: "3 agents active", timestamp: Date.now() - 120000, action: "SYSTEM", user: "system" },
  { id: "ev2", type: "risk", priority: "normal", title: "Sentinel: auth module velocity above threshold", description: "+0.06 risk", timestamp: Date.now() - 900000, action: "SENTINEL", user: "sentinel" },
  { id: "ev3", type: "proposal", priority: "normal", title: "Decision #42 approved by Archon", description: "T1 auto-approved", timestamp: Date.now() - 3600000, action: "ARCHON", user: "archon" },
  { id: "ev4", type: "memory", priority: "low", title: "Memory created: 'Prefer FastAPI over Flask'", description: "From decision #38", timestamp: Date.now() - 18000000, action: "CHRONOS", user: "chronos" },
];

// ── KPI Card ──
function KpiCard({
  icon: Icon,
  label,
  value,
  accent,
  suffix,
  trend,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  accent: string;
  suffix?: string;
  trend?: string;
}) {
  return (
    <div className="glass-l1 p-4 rounded-xl card-lift">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} style={{ color: accent }} />
        <span className="hud-label">{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-[24px] font-bold mono-data-lg" style={{ color: "var(--text-primary)" }}>
          {value}
        </span>
        {suffix && (
          <span className="text-[13px]" style={{ color: "var(--text-muted)" }}>
            {suffix}
          </span>
        )}
      </div>
      {trend && (
        <span className="mono-data-sm mt-1 block" style={{ color: "var(--text-ghost)" }}>
          {trend}
        </span>
      )}
    </div>
  );
}

function formatTime(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function DashboardPage() {
  const { state } = useSystemContext();

  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-6">
      {/* System Interruption (if any) */}
      <SystemInterruptionBanner />

      {/* Entry Experience (first time / no session) */}
      {!state.session && (
        <EntryExperienceLoop
          lastDecision={{
            id: "42",
            title: "Use Redis for Session Caching",
            tier: "T1",
            createdAt: Date.now() - 86400000 * 12,
            stability: "stable",
            trust: "validated",
          }}
          changesSince={{ newDecisions: 2, riskDelta: 0.06 }}
          riskSignal={{ alertText: "Auth module velocity above threshold" }}
        />
      )}

      {/* ── KPI ROW ── */}
      <div className="grid grid-cols-4 gap-4 stagger-1">
        <KpiCard
          icon={FileCheck}
          label="DECISIONS"
          value={state.temporal.totalDecisions || 142}
          accent="var(--accent-reason)"
          suffix="total"
          trend="3 this week"
        />
        <KpiCard
          icon={Shield}
          label="RISK SCORE"
          value={state.risk.score > 0 ? state.risk.score.toFixed(2) : "0.28"}
          accent={
            state.risk.level === "high" || state.risk.level === "critical"
              ? "var(--accent-risk)"
              : state.risk.level === "medium"
                ? "var(--status-warning)"
                : "var(--status-success)"
          }
          trend={`${state.risk.trend === "rising" ? "↑" : state.risk.trend === "falling" ? "↓" : "→"} 24h`}
        />
        <KpiCard
          icon={DollarSign}
          label="COST TODAY"
          value={state.session?.costThisSession?.toFixed(2) ?? "2.47"}
          accent="var(--accent-cost)"
          suffix="USD"
          trend="$12.30 this week"
        />
        <KpiCard
          icon={Brain}
          label="MEMORIES"
          value={89}
          accent="var(--accent-memory)"
          suffix="stored"
          trend="6 this session"
        />
      </div>

      {/* ── TWO COLUMN LAYOUT ── */}
      <div className="grid grid-cols-[1fr_340px] gap-6">
        {/* LEFT: Decisions + Pipeline */}
        <div className="space-y-4">
          {/* Active decisions */}
          <div className="stagger-2">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[16px] font-semibold flex items-center gap-2">
                <Zap size={15} style={{ color: "var(--accent-reason)" }} />
                Recent Decisions
              </h2>
              <Link
                href="/dashboard/proposals"
                className="btn-bracket text-[12px] flex items-center gap-1"
              >
                [ View All <ChevronRight size={12} /> ]
              </Link>
            </div>

            <div className="space-y-2">
              {SEED_DECISIONS.map((d) => (
                <Link
                  key={d.id}
                  href={`/dashboard/proposals?id=${d.id}`}
                  className="glass-l1 p-4 rounded-xl block card-lift"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`tier-badge tier-badge-${d.tier.toLowerCase()}`}
                      >
                        {d.tier}
                      </span>
                      <span className="text-[14px] font-medium">
                        {d.title}
                      </span>
                    </div>
                    <span
                      className="hud-label px-2 py-[1px] rounded-[4px]"
                      style={{
                        color:
                          d.status === "approved"
                            ? "var(--status-success)"
                            : d.status === "pending_approval"
                              ? "var(--tier-2)"
                              : "var(--accent-reason)",
                        background:
                          d.status === "approved"
                            ? "hsla(142, 60%, 48%, 0.1)"
                            : d.status === "pending_approval"
                              ? "var(--tier-2-bg)"
                              : "hsla(217, 85%, 60%, 0.08)",
                      }}
                    >
                      {d.status.replace("_", " ").toUpperCase()}
                    </span>
                  </div>

                  <div className="flex items-center gap-4">
                    <ConfidenceEvolution points={d.confidenceEvolution} />
                    <TrustBadge level={d.trust} />
                    <GovernancePipeline stages={d.pipeline} variant="compact" />
                    <div className="ml-auto">
                      <TemporalMeta
                        createdAt={d.createdAt}
                        stability={d.stability}
                        inline
                      />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          {/* Sentinel Mini */}
          <div className="glass-l1 p-4 rounded-xl stagger-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[14px] font-semibold flex items-center gap-2">
                <Shield size={14} style={{ color: "var(--accent-risk)" }} />
                Sentinel Overview
              </h3>
              <Link
                href="/dashboard/risk"
                className="btn-bracket text-[12px]"
              >
                [ Full Report ]
              </Link>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <p className="hud-label mb-0.5">RISK LEVEL</p>
                <p
                  className="mono-data font-medium"
                  style={{
                    color:
                      state.risk.level === "high" || state.risk.level === "critical"
                        ? "var(--accent-risk)"
                        : state.risk.level === "medium"
                          ? "var(--status-warning)"
                          : "var(--status-success)",
                  }}
                >
                  {(state.risk.level || "LOW").toUpperCase()}
                </p>
              </div>
              <div>
                <p className="hud-label mb-0.5">ACTIVE ALERTS</p>
                <p className="mono-data font-medium" style={{ color: state.risk.activeAlerts > 0 ? "var(--accent-risk)" : "var(--text-muted)" }}>
                  {state.risk.activeAlerts || 1}
                </p>
              </div>
              <div>
                <p className="hud-label mb-0.5">TREND</p>
                <p
                  className="mono-data font-medium"
                  style={{
                    color:
                      state.risk.trend === "rising"
                        ? "var(--accent-risk)"
                        : state.risk.trend === "falling"
                          ? "var(--status-success)"
                          : "var(--text-muted)",
                  }}
                >
                  {state.risk.trend === "rising" ? "↑ RISING" : state.risk.trend === "falling" ? "↓ FALLING" : "→ STABLE"}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT: Activity Feed */}
        <div className="stagger-3">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[16px] font-semibold flex items-center gap-2">
              <Activity size={15} style={{ color: "var(--text-muted)" }} />
              Activity
            </h2>
          </div>

          <div className="space-y-2">
            {SEED_ACTIVITY.map((event) => {
              const isSystem = event.user === "system" || event.user === "sentinel" || event.user === "archon" || event.user === "chronos";
              return (
                <div
                  key={event.id}
                  className="glass-l1 p-3 rounded-lg"
                  style={{
                    borderLeft: isSystem
                      ? "2px solid var(--accent-reason)"
                      : "2px solid transparent",
                  }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    {isSystem && (
                      <span
                        className="hud-label px-1.5 py-[0.5px] rounded-[3px]"
                        style={{
                          background: "hsla(217, 85%, 60%, 0.1)",
                          color: "var(--accent-reason)",
                          fontSize: "9px",
                        }}
                      >
                        SYSTEM
                      </span>
                    )}
                    <span className="hud-label" style={{ color: "var(--text-ghost)" }}>
                      {event.action}
                    </span>
                    <span className="ml-auto mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                      {event.timestamp ? formatTime(event.timestamp) : ""}
                    </span>
                  </div>
                  <p className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
                    {event.title}
                  </p>
                  {event.description && (
                    <p className="mono-data-sm mt-0.5" style={{ color: "var(--text-ghost)" }}>
                      {event.description}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          {/* Quick actions */}
          <div className="mt-4 space-y-2">
            <Link
              href="/dashboard/council"
              className="glass-l1 p-3 rounded-lg flex items-center gap-2 card-lift block"
            >
              <Clock size={13} style={{ color: "var(--accent-govern)" }} />
              <span className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
                Open Council Session
              </span>
              <ChevronRight size={12} className="ml-auto" style={{ color: "var(--text-ghost)" }} />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
