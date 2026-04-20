"use client";

import { useState } from "react";
import {
  AlertOctagon, Shield, Clock, Users,
  ChevronRight, Radio, CheckCircle2,
} from "lucide-react";
import { useSystemContext } from "@/lib/context/SystemContext";
import { TemporalMeta } from "@/components/cognitive/TemporalMeta";

/* ══════════════════════════════════════════════════════════════
   WAR ROOM — Incident management dashboard
   
   Active incidents, lifecycle tracking, Sentinel integration.
   ══════════════════════════════════════════════════════════════ */

interface Incident {
  id: string;
  title: string;
  severity: "critical" | "high" | "medium";
  status: "active" | "investigating" | "mitigating" | "resolved";
  createdAt: number;
  assignees: string[];
  relatedDecisions: string[];
}

const SEVERITY_CONFIG: Record<string, { color: string; bg: string }> = {
  critical: { color: "var(--status-error)", bg: "hsla(348,82%,52%,0.08)" },
  high: { color: "var(--accent-risk)", bg: "hsla(28,90%,55%,0.06)" },
  medium: { color: "var(--status-warning)", bg: "hsla(38,88%,52%,0.06)" },
};

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  active: { color: "var(--status-error)", label: "ACTIVE" },
  investigating: { color: "var(--status-warning)", label: "INVESTIGATING" },
  mitigating: { color: "var(--accent-reason)", label: "MITIGATING" },
  resolved: { color: "var(--status-success)", label: "RESOLVED" },
};

const SEED_INCIDENTS: Incident[] = [
  {
    id: "INC-001",
    title: "Auth module latency spike — 5x normal response time",
    severity: "critical",
    status: "investigating",
    createdAt: Date.now() - 1800000,
    assignees: ["Sentinel", "Architecture Agent"],
    relatedDecisions: ["#42 Use Redis", "#43 JWT Migration"],
  },
  {
    id: "INC-002",
    title: "Rate limiter false positives on internal services",
    severity: "medium",
    status: "mitigating",
    createdAt: Date.now() - 7200000,
    assignees: ["Performance Agent"],
    relatedDecisions: ["#40 Rate Limiting"],
  },
];

export default function WarRoomPage() {
  const { state } = useSystemContext();
  const [selectedIncident, setSelectedIncident] = useState<string | null>(null);

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-page-enter">
      <div>
        <h1 className="text-[22px] font-bold flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
          <AlertOctagon size={20} style={{ color: "var(--accent-risk)" }} />
          War Room
        </h1>
        <p className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
          Incident management and real-time crisis response
        </p>
      </div>

      {/* Status Overview */}
      <div className="grid grid-cols-4 gap-4">
        <div className="glass-l2 p-4 rounded-xl" style={{ borderLeft: "3px solid var(--status-error)" }}>
          <p className="hud-label mb-1">ACTIVE</p>
          <p className="text-[28px] font-bold" style={{ fontFamily: "var(--font-mono)", color: "var(--status-error)" }}>
            {SEED_INCIDENTS.filter((i) => i.status !== "resolved").length}
          </p>
        </div>
        <div className="glass-l1 p-4 rounded-xl">
          <p className="hud-label mb-1">SYSTEM RISK</p>
          <p className="text-[28px] font-bold" style={{
            fontFamily: "var(--font-mono)",
            color: state.risk.score > 0.5 ? "var(--status-error)" : state.risk.score > 0.3 ? "var(--status-warning)" : "var(--status-success)",
          }}>
            {state.risk.score.toFixed(2)}
          </p>
        </div>
        <div className="glass-l1 p-4 rounded-xl">
          <p className="hud-label mb-1">GOVERNANCE</p>
          <p className="text-[28px] font-bold" style={{
            fontFamily: "var(--font-mono)",
            color: state.governance.frozen ? "var(--status-error)" : "var(--text-primary)",
          }}>
            {state.governance.frozen ? "FROZEN" : "NORMAL"}
          </p>
        </div>
        <div className="glass-l1 p-4 rounded-xl">
          <p className="hud-label mb-1">RESPONDERS</p>
          <p className="text-[28px] font-bold" style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
            {new Set(SEED_INCIDENTS.flatMap((i) => i.assignees)).size}
          </p>
        </div>
      </div>

      {/* Incidents */}
      <div className="space-y-3">
        <p className="hud-label">INCIDENTS</p>
        {SEED_INCIDENTS.map((incident) => {
          const sev = SEVERITY_CONFIG[incident.severity];
          const status = STATUS_CONFIG[incident.status];
          const isSelected = selectedIncident === incident.id;

          return (
            <button
              key={incident.id}
              onClick={() => setSelectedIncident(isSelected ? null : incident.id)}
              className="w-full glass-l1 p-5 rounded-xl text-left card-lift"
              style={{ borderLeft: `4px solid ${sev.color}` }}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-3">
                  <Radio size={14} style={{ color: status.color }} className={incident.status === "active" ? "animate-pulse" : ""} />
                  <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>{incident.id}</span>
                  <span className="text-[14px] font-medium" style={{ color: "var(--text-primary)" }}>{incident.title}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="hud-label px-1.5 py-[1px] rounded-[4px]" style={{ background: sev.bg, color: sev.color }}>
                    {incident.severity.toUpperCase()}
                  </span>
                  <span className="hud-label px-1.5 py-[1px] rounded-[4px]" style={{
                    background: `color-mix(in srgb, ${status.color} 10%, transparent)`,
                    color: status.color,
                  }}>
                    {status.label}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1">
                  <Users size={12} style={{ color: "var(--text-ghost)" }} />
                  <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                    {incident.assignees.join(", ")}
                  </span>
                </div>
                <TemporalMeta createdAt={incident.createdAt} stability="volatile" inline />
              </div>

              {isSelected && (
                <div className="mt-4 pt-3 space-y-2 animate-slide-down" style={{ borderTop: "0.5px solid var(--border-subtle)" }}>
                  <p className="hud-label">RELATED DECISIONS</p>
                  <div className="flex gap-2 flex-wrap">
                    {incident.relatedDecisions.map((d) => (
                      <span key={d} className="glass-l1 px-2 py-1 rounded text-[12px]" style={{ color: "var(--accent-reason)" }}>
                        {d}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
