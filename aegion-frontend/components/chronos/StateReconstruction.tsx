"use client";

import React from "react";

/* ══════════════════════════════════════════════════════════════
   STATE RECONSTRUCTION — Shows system state at a point in time
   
   Right panel that renders decision list, risk, governance,
   and diff-vs-now at a selected time marker.
   ══════════════════════════════════════════════════════════════ */

export interface HistoricalState {
  timestamp: number;
  decisions: Array<{ id: string; title: string; tier: string; stability: string }>;
  riskScore: number;
  riskLevel: string;
  governance: string;
  session?: { name: string; status: string };
  diffVsNow?: {
    newDecisions: number;
    riskChange: number;
    superseded: number;
    newMemories: number;
  };
}

function formatDate(ts: number): string {
  return new Date(ts).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

const STABILITY_COLORS: Record<string, string> = {
  stable: "var(--status-success)",
  settling: "var(--status-warning)",
  volatile: "var(--status-error)",
};

export function StateReconstruction({ state }: { state: HistoricalState | null }) {
  if (!state) {
    return (
      <div className="glass-l1 rounded-xl p-6 flex items-center justify-center h-full">
        <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
          Select a point in time to reconstruct state
        </p>
      </div>
    );
  }

  return (
    <div className="glass-l1 rounded-xl p-4 space-y-4 animate-fade-in">
      <div
        className="flex items-center justify-between pb-3"
        style={{ borderBottom: "0.5px solid var(--border-subtle)" }}
      >
        <span className="hud-label">STATE AT</span>
        <span className="mono-data font-medium" style={{ color: "var(--accent-memory)" }}>
          {formatDate(state.timestamp)}
        </span>
      </div>

      {/* Active Decisions */}
      <div>
        <p className="hud-label mb-2">ACTIVE DECISIONS</p>
        <div className="space-y-1.5">
          {state.decisions.map((d) => (
            <div key={d.id} className="flex items-center gap-2">
              <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>├─</span>
              <span className={`tier-badge tier-badge-${d.tier.toLowerCase()}`} style={{ fontSize: 9 }}>
                {d.tier}
              </span>
              <span className="text-[13px] truncate" style={{ color: "var(--text-primary)" }}>
                {d.title}
              </span>
              <span
                className="mono-data-sm ml-auto"
                style={{ color: STABILITY_COLORS[d.stability] || "var(--text-muted)" }}
              >
                {d.stability.toUpperCase()}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* System State */}
      <div className="grid grid-cols-2 gap-3">
        <div className="glass-l1 p-3 rounded-lg">
          <p className="hud-label mb-1">RISK SCORE</p>
          <p
            className="mono-data font-medium"
            style={{
              color:
                state.riskScore > 0.6
                  ? "var(--status-error)"
                  : state.riskScore > 0.3
                    ? "var(--status-warning)"
                    : "var(--status-success)",
            }}
          >
            {state.riskScore.toFixed(2)} ({state.riskLevel})
          </p>
        </div>
        <div className="glass-l1 p-3 rounded-lg">
          <p className="hud-label mb-1">GOVERNANCE</p>
          <p className="mono-data font-medium" style={{ color: "var(--text-primary)" }}>
            {state.governance}
          </p>
        </div>
      </div>

      {state.session && (
        <div className="glass-l1 p-3 rounded-lg">
          <p className="hud-label mb-1">SESSION</p>
          <p className="text-[13px]" style={{ color: "var(--text-primary)" }}>
            &quot;{state.session.name}&quot;{" "}
            <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
              ({state.session.status})
            </span>
          </p>
        </div>
      )}

      {/* Diff vs Now */}
      {state.diffVsNow && (
        <div
          className="glass-l2 p-3 rounded-lg"
          style={{ borderLeft: "3px solid var(--accent-memory)" }}
        >
          <p className="hud-label mb-2">DIFF VS NOW</p>
          <div className="space-y-1">
            <p className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
              +{state.diffVsNow.newDecisions} decisions made since
            </p>
            <p className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
              Risk:{" "}
              <span className="mono-data-sm">
                {state.riskScore.toFixed(2)} → {(state.riskScore + state.diffVsNow.riskChange).toFixed(2)}
              </span>{" "}
              <span
                style={{
                  color: state.diffVsNow.riskChange > 0 ? "var(--status-error)" : "var(--status-success)",
                }}
              >
                ({state.diffVsNow.riskChange > 0 ? "+" : ""}
                {state.diffVsNow.riskChange.toFixed(2)})
              </span>
            </p>
            <p className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
              {state.diffVsNow.superseded} decisions superseded
            </p>
            <p className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
              {state.diffVsNow.newMemories} new memory entries
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
