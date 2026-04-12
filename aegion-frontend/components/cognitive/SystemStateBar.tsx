"use client";

import React from "react";
import { useSystemContext } from "@/lib/context/SystemContext";
import type { CognitiveMode } from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   SYSTEM STATE BAR
   
   The user NEVER wonders "what state is the system in?"
   Fixed strip, 44px, above all page content.
   5 sections: Session | Mode | Risk | Pending | System
   ══════════════════════════════════════════════════════════════ */

const MODE_LABELS: Record<CognitiveMode, { icon: string; label: string }> = {
  explore: { icon: "⊕", label: "EXPLORE" },
  decide:  { icon: "⚙", label: "DECIDE" },
  execute: { icon: "▸", label: "EXECUTE" },
  audit:   { icon: "◎", label: "AUDIT" },
};

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function RiskGauge({ score, trend }: { score: number; trend: string }) {
  const blocks = [
    score >= 0.1,
    score >= 0.4,
    score >= 0.7,
  ];
  const color =
    score <= 0.3
      ? "var(--status-success)"
      : score <= 0.6
        ? "var(--status-warning)"
        : "var(--status-error)";

  return (
    <div className="flex items-center gap-1">
      {blocks.map((filled, i) => (
        <div
          key={i}
          className="w-[6px] h-[14px] rounded-[2px]"
          style={{
            background: filled ? color : "var(--surface-4)",
            transition: "background 500ms ease-in-out",
          }}
        />
      ))}
      <span className="mono-data ml-1" style={{ color }}>
        {score.toFixed(2)}
      </span>
      <span className="mono-data-sm" style={{ color: "var(--text-muted)" }}>
        {trend === "rising" ? "↑" : trend === "falling" ? "↓" : "→"}
      </span>
    </div>
  );
}

export function SystemStateBar() {
  const { state, setMode } = useSystemContext();
  const { session, risk, governance, system } = state;
  const isDegraded = system.backendStatus !== "connected";
  const isSystemInitiative =
    state.activeInterruption?.priority === "critical" ||
    state.systemEvents.some((e) => !e.acknowledged && e.priority === "critical");

  return (
    <div
      role="status"
      aria-live="polite"
      className="glass-static flex items-center justify-between h-[44px] px-4 border-b z-30 select-none"
      style={{
        borderColor: isDegraded
          ? "var(--tier-2-border)"
          : governance.frozen
            ? "var(--tier-3-border)"
            : "var(--border-subtle)",
        borderWidth: "0 0 0.5px 0",
      }}
    >
      {/* ── SESSION ── */}
      <div className="flex items-center gap-3 min-w-[180px]">
        {session ? (
          <>
            <div
              className="status-dot-pulse"
              style={{
                background:
                  session.status === "active"
                    ? "var(--status-success)"
                    : session.status === "paused"
                      ? "var(--status-warning)"
                      : "var(--status-neutral)",
              }}
            />
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-medium truncate max-w-[120px]">
                  {session.name}
                </span>
                <span
                  className="hud-label px-1.5 py-[1px] rounded-[4px]"
                  style={{
                    background:
                      session.status === "active"
                        ? "hsla(142, 60%, 48%, 0.1)"
                        : "hsla(220, 12%, 48%, 0.1)",
                    color:
                      session.status === "active"
                        ? "var(--status-success)"
                        : "var(--text-muted)",
                  }}
                >
                  {session.status.toUpperCase()}
                </span>
              </div>
              <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                {formatDuration(session.duration)} elapsed
              </span>
            </div>
          </>
        ) : (
          <span className="text-[12px]" style={{ color: "var(--text-ghost)" }}>
            No active session
          </span>
        )}
      </div>

      {/* ── DIVIDER ── */}
      <div className="h-[24px] w-[1px]" style={{ background: "var(--border-subtle)" }} />

      {/* ── MODE ── */}
      <button
        className="flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-[var(--surface-hover)] transition-colors"
        onClick={() => {
          const modes: CognitiveMode[] = ["explore", "decide", "execute", "audit"];
          const currentIdx = modes.indexOf(session?.mode ?? "explore");
          setMode(modes[(currentIdx + 1) % modes.length]);
        }}
        aria-label="Switch cognitive mode"
      >
        <span
          className="text-[14px]"
          style={{ color: `var(--mode-${session?.mode ?? "explore"})` }}
        >
          {MODE_LABELS[session?.mode ?? "explore"].icon}
        </span>
        <span
          className="hud-label"
          style={{ color: `var(--mode-${session?.mode ?? "explore"})` }}
        >
          {MODE_LABELS[session?.mode ?? "explore"].label}
        </span>
      </button>

      <div className="h-[24px] w-[1px]" style={{ background: "var(--border-subtle)" }} />

      {/* ── RISK (SENTINEL) ── */}
      <div className="flex flex-col items-start min-w-[100px]">
        <RiskGauge score={risk.score} trend={risk.trend} />
        {risk.trendDelta !== 0 && (
          <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
            {risk.trendDelta > 0 ? "+" : ""}
            {risk.trendDelta.toFixed(2)} 24h
          </span>
        )}
      </div>

      <div className="h-[24px] w-[1px]" style={{ background: "var(--border-subtle)" }} />

      {/* ── PENDING ── */}
      <div className="flex flex-col items-start min-w-[90px]">
        <div className="flex items-center gap-1.5">
          <span className="text-[13px]" style={{ color: "var(--text-muted)" }}>⏳</span>
          <span
            className="mono-data"
            style={{
              color:
                governance.pendingApprovals > 0
                  ? "var(--tier-2)"
                  : "var(--text-muted)",
            }}
          >
            {governance.pendingApprovals}
          </span>
          <span className="text-[12px]" style={{ color: "var(--text-muted)" }}>
            pending
          </span>
        </div>
        {governance.pendingApprovals > 0 && (
          <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
            {governance.pendingByTier.T2 > 0 && `T2:${governance.pendingByTier.T2} `}
            {governance.pendingByTier.T3 > 0 && (
              <span style={{ color: "var(--tier-3)" }}>
                T3:{governance.pendingByTier.T3}
              </span>
            )}
          </span>
        )}
      </div>

      <div className="h-[24px] w-[1px]" style={{ background: "var(--border-subtle)" }} />

      {/* ── SYSTEM STATUS ── */}
      <div className="flex items-center gap-2 min-w-[160px]">
        {isDegraded ? (
          <>
            <div className="status-dot" style={{ background: "var(--status-warning)" }} />
            <div className="flex flex-col">
              <span
                className="hud-label"
                style={{ color: "var(--status-warning)" }}
              >
                DEGRADED
              </span>
              <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                Working with last known data
              </span>
            </div>
          </>
        ) : governance.frozen ? (
          <>
            <div className="status-dot animate-breathe" style={{ background: "var(--tier-3)" }} />
            <span className="hud-label" style={{ color: "var(--tier-3)" }}>
              FROZEN
            </span>
          </>
        ) : isSystemInitiative ? (
          <>
            <div
              className="status-dot-pulse animate-initiative"
              style={{ background: "var(--accent-reason)" }}
            />
            <div className="flex flex-col">
              <span
                className="hud-label"
                style={{ color: "var(--accent-reason)" }}
                aria-live="assertive"
              >
                ● SYSTEM ACTIVE
              </span>
              <span className="mono-data-sm truncate max-w-[140px]" style={{ color: "var(--text-secondary)" }}>
                {state.activeInterruption?.description ??
                  state.systemEvents.find((e) => !e.acknowledged && e.priority === "critical")?.description ??
                  "Processing..."}
              </span>
            </div>
          </>
        ) : system.thinking ? (
          <>
            <div
              className="status-dot-pulse"
              style={{ background: "var(--accent-reason)" }}
            />
            <div className="flex flex-col">
              <span className="hud-label" style={{ color: "var(--accent-reason)" }}>
                THINKING...
              </span>
              {system.thinkingContext && (
                <span className="mono-data-sm truncate max-w-[140px]" style={{ color: "var(--text-ghost)" }}>
                  {system.thinkingContext}
                </span>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="status-dot" style={{ background: "var(--text-ghost)" }} />
            <span className="hud-label" style={{ color: "var(--text-ghost)" }}>
              IDLE
            </span>
          </>
        )}
      </div>
    </div>
  );
}
