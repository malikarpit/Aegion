"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import { ConfidenceEvolution } from "./ConfidenceEvolution";
import { TrustBadge } from "./TrustBadge";
import { GovernancePipeline } from "./GovernancePipeline";
import { TemporalMeta } from "./TemporalMeta";
import { WhyPanel } from "./WhyPanel";
import { TransparencyPanel } from "./TransparencyPanel";
import { BlastRadius } from "./BlastRadius";
import type {
  GovernanceTier, DecisionStatus, TrustLevel, StabilityLevel,
  ConfidencePoint, PipelineStageStatus,
} from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   DECISION CARD — The most complex component.
   
   Weight Discipline (v4.1 Law 2):
   L1 (Primary)   — Always visible: Title, Tier, Confidence+sparkline, Trust, Status, one-line summary
   L2 (Secondary)  — On expand: WhyPanel, Risk context, Blast radius, Evidence
   L3 (Deep)       — On "Show Raw": TransparencyPanel, Pipeline stages, Raw provenance
   
   L1 must be scannable in <2 seconds.
   L2 must answer "should I act?"
   L3 must answer "prove it."
   ══════════════════════════════════════════════════════════════ */

export interface DecisionCardData {
  id: string;
  title: string;
  summary: string;
  tier: GovernanceTier;
  status: DecisionStatus;
  confidence: number;
  confidenceEvolution: ConfidencePoint[];
  trust: TrustLevel;
  createdAt: number;
  stability: StabilityLevel;
  pipeline: Array<{ stage: "session" | "distillation" | "sentinel" | "archon" | "memory"; status: PipelineStageStatus }>;
  // L2 data (optional — fetched on expand)
  provenance?: {
    originSession: { id: string; name: string };
    buildsOn: Array<{ id: string; title: string; tier: GovernanceTier; age: string }>;
    triggeredBy?: { type: string; description: string; age: string };
    supersedes?: Array<{ id: string; title: string; age: string }>;
    memories?: Array<{ id: string; title: string; stability: StabilityLevel }>;
  };
  blastRadius?: {
    files: string[];
    services: string[];
    consumers: string[];
  };
  riskDelta?: number;
  // L3 data
  models?: Array<{ name: string; tokensIn: number; tokensOut: number; cost: number; latency: number }>;
  totalCost?: number;
  totalLatency?: number;
}

interface DecisionCardProps {
  decision: DecisionCardData;
  defaultLevel?: 1 | 2 | 3;
  compact?: boolean;
  href?: string;
}

export function DecisionCard({ decision: d, defaultLevel = 1, compact = false, href }: DecisionCardProps) {
  const [level, setLevel] = useState<1 | 2 | 3>(defaultLevel);

  const statusColor =
    d.status === "approved" ? "var(--status-success)"
    : d.status === "rejected" ? "var(--status-error)"
    : d.status === "pending_approval" ? "var(--tier-2)"
    : d.status === "deliberating" ? "var(--accent-reason)"
    : "var(--text-muted)";

  const statusBg =
    d.status === "approved" ? "hsla(142,60%,48%,0.1)"
    : d.status === "rejected" ? "hsla(348,82%,52%,0.1)"
    : d.status === "pending_approval" ? "var(--tier-2-bg)"
    : d.status === "deliberating" ? "hsla(217,85%,60%,0.08)"
    : "hsla(220,12%,48%,0.06)";

  const content = (
    <>
      {/* Row 1: Tier + Title + Status */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`tier-badge tier-badge-${d.tier.toLowerCase()}`}>{d.tier}</span>
          <span
            className="text-[14px] font-medium truncate"
            style={{ color: "var(--text-primary)" }}
          >
            {d.title}
          </span>
        </div>
        <span
          className="hud-label px-2 py-[1px] rounded-[4px] shrink-0 ml-2"
          style={{ color: statusColor, background: statusBg }}
        >
          {d.status.replace(/_/g, " ").toUpperCase()}
        </span>
      </div>

      {/* Row 2: Summary (optional) */}
      {!compact && d.summary && (
        <p className="text-[13px] mb-2 line-clamp-1" style={{ color: "var(--text-secondary)" }}>
          {d.summary}
        </p>
      )}

      {/* Row 3: Cognitive metadata strip */}
      <div className="flex items-center gap-3 flex-wrap">
        <ConfidenceEvolution points={d.confidenceEvolution} />
        <TrustBadge level={d.trust} />
        {!compact && <GovernancePipeline stages={d.pipeline} variant="compact" />}
        <div className="ml-auto">
          <TemporalMeta createdAt={d.createdAt} stability={d.stability} inline />
        </div>
      </div>
    </>
  );

  return (
    <div className="glass-l1 rounded-xl overflow-hidden card-lift">
      {/* ── L1: PRIMARY (always visible) ── */}
      {href ? (
        <Link href={href} className="block p-4 cursor-pointer">
          {content}
        </Link>
      ) : (
        <div className="block p-4">
          {content}
        </div>
      )}

      {/* ── L1→L2 toggle ── */}
      {!compact && (
        <button
          onClick={() => setLevel(level === 1 ? 2 : 1)}
          className="w-full flex items-center justify-center gap-1 py-1.5 transition-colors hover:bg-[var(--surface-hover)]"
          style={{
            borderTop: "0.5px solid var(--border-subtle)",
            color: "var(--text-ghost)",
          }}
        >
          {level >= 2 ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          <span className="hud-label">{level >= 2 ? "COLLAPSE" : "DETAILS"}</span>
        </button>
      )}

      {/* ── L2: SECONDARY (on expand) ── */}
      {level >= 2 && (
        <div
          className="p-4 space-y-3 animate-slide-down"
          style={{ borderTop: "0.5px solid var(--border-subtle)", background: "var(--surface-0)" }}
        >
          {/* WhyPanel */}
          {d.provenance && (
            <WhyPanel
              decisionId={d.id}
              defaultLevel={2}
              origin={d.provenance ? { sessionId: d.provenance.originSession.id, sessionName: d.provenance.originSession.name } : undefined}
              lineage={d.provenance?.buildsOn?.map((b) => ({ id: b.id, title: b.title, tier: b.tier, type: "builds_on" as const, createdAt: Date.now() - 12 * 86400000 }))}
              supersedes={d.provenance?.supersedes?.map((s) => ({ id: s.id, title: s.title, tier: "T0", type: "supersedes" as const, createdAt: Date.now() - 25 * 86400000 }))}
              memories={d.provenance?.memories?.map((m) => ({ id: m.id, title: m.title, tier: "T0", type: "references" as const, createdAt: Date.now() - 5 * 86400000, stability: m.stability }))}
            />
          )}

          {/* Blast Radius */}
          {d.blastRadius && (
            <div className="flex items-start gap-4">
              <BlastRadius
                directFiles={d.blastRadius.files}
                services={d.blastRadius.services}
                downstream={d.blastRadius.consumers}
                tier={d.tier}
                size={80}
              />
              {d.riskDelta !== undefined && (
                <div className="glass-l1 p-3 rounded-lg flex-1">
                  <p className="hud-label mb-1">RISK IMPACT</p>
                  <p
                    className="mono-data font-medium"
                    style={{
                      color: d.riskDelta > 0.05 ? "var(--accent-risk)" : d.riskDelta > 0 ? "var(--status-warning)" : "var(--status-success)",
                    }}
                  >
                    {d.riskDelta > 0 ? "+" : ""}{d.riskDelta.toFixed(3)}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Pipeline (expanded) */}
          <div>
            <p className="hud-label mb-2">GOVERNANCE PIPELINE</p>
            <GovernancePipeline stages={d.pipeline} variant="expanded" />
          </div>

          {/* L2→L3 toggle */}
          <button
            onClick={() => setLevel(level === 3 ? 2 : 3)}
            className="flex items-center gap-1 px-2 py-1 rounded-md transition-colors hover:bg-[var(--surface-hover)]"
            style={{ color: "var(--text-ghost)" }}
          >
            <span className="mono-data-sm">
              {level === 3 ? "▾ HIDE RAW" : "▸ SHOW RAW"}
            </span>
          </button>
        </div>
      )}

      {/* ── L3: DEEP TRACE (on "Show Raw") ── */}
      {level >= 3 && (
        <div
          className="p-4 space-y-3 animate-slide-down"
          style={{ borderTop: "0.5px solid var(--border-subtle)", background: "hsla(222,15%,4%,0.5)" }}
        >
          {d.models && d.totalCost !== undefined && d.totalLatency !== undefined && (
            <TransparencyPanel
              models={d.models}
              totalCost={d.totalCost}
              totalLatency={d.totalLatency}
              confidenceEvolution={d.confidenceEvolution}
              trust={d.trust}
              defaultLevel={2}
            />
          )}
        </div>
      )}
    </div>
  );
}
