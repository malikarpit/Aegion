"use client";

import React from "react";

/* ══════════════════════════════════════════════════════════════
   SESSION BOUNDARY — Session End Overlay
   
   Emotional calibration: brief screen dim (200ms, opacity 0.95)
   before overlay appears. Creates sense of "closing a chapter."
   
   Shows session summary: decisions made, cost, duration, 
   memories created, risk change.
   ══════════════════════════════════════════════════════════════ */

interface SessionSummary {
  name: string;
  duration: number; // seconds
  decisionsCount: number;
  totalCost: number;
  memoriesCreated: number;
  riskStart: number;
  riskEnd: number;
}

interface SessionBoundaryProps {
  summary: SessionSummary;
  onNewSession: () => void;
  onClose: () => void;
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m} minutes`;
}

export function SessionBoundary({
  summary,
  onNewSession,
  onClose,
}: SessionBoundaryProps) {
  const riskDelta = summary.riskEnd - summary.riskStart;

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center"
      role="dialog"
      aria-label="Session ended"
    >
      {/* Backdrop with emotional dim */}
      <div
        className="absolute inset-0"
        style={{
          background: "hsla(222, 15%, 3%, 0.85)",
          backdropFilter: "blur(20px)",
          animation: "fadeIn 200ms ease-out",
        }}
        onClick={onClose}
      />

      {/* Content */}
      <div className="relative glass-l3 p-8 max-w-[440px] w-full animate-slide-up">
        <p className="hud-label mb-1" style={{ color: "var(--text-ghost)" }}>
          SESSION CLOSED
        </p>
        <h2 className="text-[20px] font-semibold mb-6">
          &quot;{summary.name}&quot;
        </h2>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <p className="hud-label mb-0.5">DURATION</p>
            <p className="mono-data-lg">{formatDuration(summary.duration)}</p>
          </div>
          <div>
            <p className="hud-label mb-0.5">DECISIONS</p>
            <p className="mono-data-lg">{summary.decisionsCount}</p>
          </div>
          <div>
            <p className="hud-label mb-0.5">COST</p>
            <p className="mono-data-lg" style={{ color: "var(--accent-cost)" }}>
              ${summary.totalCost.toFixed(3)}
            </p>
          </div>
          <div>
            <p className="hud-label mb-0.5">MEMORIES</p>
            <p className="mono-data-lg" style={{ color: "var(--accent-memory)" }}>
              {summary.memoriesCreated}
            </p>
          </div>
        </div>

        {/* Risk change */}
        <div className="glass-l1 p-3 rounded-lg mb-6">
          <p className="hud-label mb-1">RISK CHANGE</p>
          <div className="flex items-center gap-3">
            <span className="mono-data" style={{ color: "var(--text-muted)" }}>
              {summary.riskStart.toFixed(2)}
            </span>
            <span style={{ color: "var(--text-ghost)" }}>→</span>
            <span
              className="mono-data font-medium"
              style={{
                color:
                  riskDelta > 0
                    ? "var(--status-error)"
                    : riskDelta < 0
                      ? "var(--status-success)"
                      : "var(--text-muted)",
              }}
            >
              {summary.riskEnd.toFixed(2)}
            </span>
            <span
              className="mono-data-sm"
              style={{
                color:
                  riskDelta > 0 ? "var(--status-error)" : "var(--status-success)",
              }}
            >
              ({riskDelta > 0 ? "+" : ""}
              {riskDelta.toFixed(2)})
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onNewSession}
            className="px-4 py-2 rounded-lg text-[14px] font-medium"
            style={{
              background: "var(--tier-1-bg)",
              border: "1px solid var(--tier-1-border)",
              color: "var(--tier-1)",
            }}
          >
            New Session
          </button>
          <button onClick={onClose} className="btn-bracket text-[14px] px-4 py-2">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
