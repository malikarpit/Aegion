"use client";

import { useState } from "react";
import {
  Shield, AlertTriangle, TrendingUp, TrendingDown,
  Activity, Eye, ChevronRight, ArrowUpRight, ArrowDownRight,
} from "lucide-react";
import { useSystemContext } from "@/lib/context/SystemContext";

/* ══════════════════════════════════════════════════════════════
   RISK & SENTINEL PAGE
   
   Sentinel risk overview: risk gauge, alert list, drift trend,
   risk contributors, active monitors.
   ══════════════════════════════════════════════════════════════ */

interface Alert {
  id: string;
  severity: "critical" | "high" | "medium" | "low";
  title: string;
  description: string;
  source: string;
  timestamp: number;
  acknowledged: boolean;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "var(--status-error)",
  high: "var(--accent-risk)",
  medium: "var(--status-warning)",
  low: "var(--text-muted)",
};

// Seed data
const SEED_ALERTS: Alert[] = [
  { id: "a-1", severity: "high", title: "Auth module velocity above threshold", description: "Rate of change in authentication module exceeds normal patterns. 14 modifications in 48h.", source: "Sentinel", timestamp: Date.now() - 900000, acknowledged: false },
  { id: "a-2", severity: "medium", title: "Decision #40 confidence drifting", description: "Rate Limiting decision confidence has decreased from 0.78 to 0.72 over 48 hours.", source: "Chronos", timestamp: Date.now() - 3600000, acknowledged: false },
  { id: "a-3", severity: "low", title: "Memory #91 stability degraded", description: "Infrastructure cost analysis memory marked as SHIFTING. Related decisions may need review.", source: "Memory", timestamp: Date.now() - 18000000, acknowledged: true },
];

const RISK_CONTRIBUTORS = [
  { area: "Authentication", score: 0.12, trend: "rising" as const, decisions: 3 },
  { area: "API Gateway", score: 0.08, trend: "stable" as const, decisions: 2 },
  { area: "Database", score: 0.05, trend: "falling" as const, decisions: 5 },
  { area: "Infrastructure", score: 0.03, trend: "stable" as const, decisions: 1 },
];

export default function RiskPage() {
  const { state } = useSystemContext();
  const [alerts, setAlerts] = useState(SEED_ALERTS);

  const risk = state.risk;
  const riskColor =
    risk.score > 0.6 ? "var(--status-error)"
    : risk.score > 0.3 ? "var(--status-warning)"
    : "var(--status-success)";

  const handleAcknowledge = (id: string) => {
    setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, acknowledged: true } : a)));
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-page-enter">
      {/* Header */}
      <div>
        <h1 className="text-[22px] font-bold" style={{ color: "var(--text-primary)" }}>Risk & Sentinel</h1>
        <p className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
          System threat assessment and security monitoring
        </p>
      </div>

      {/* Risk Overview Cards */}
      <div className="grid grid-cols-4 gap-4">
        {/* Risk Score */}
        <div className="glass-l2 p-5 rounded-xl col-span-2">
          <p className="hud-label mb-3">RISK SCORE</p>
          <div className="flex items-end gap-4">
            <span className="text-[48px] font-bold leading-none" style={{ fontFamily: "var(--font-mono)", color: riskColor }}>
              {risk.score.toFixed(2)}
            </span>
            <div className="pb-2">
              <div className="flex items-center gap-1 mb-1">
                {risk.trend === "rising" ? (
                  <ArrowUpRight size={14} style={{ color: "var(--status-error)" }} />
                ) : risk.trend === "falling" ? (
                  <ArrowDownRight size={14} style={{ color: "var(--status-success)" }} />
                ) : (
                  <Activity size={14} style={{ color: "var(--text-muted)" }} />
                )}
                <span className="mono-data-sm" style={{
                  color: risk.trend === "rising" ? "var(--status-error)" : risk.trend === "falling" ? "var(--status-success)" : "var(--text-muted)",
                }}>
                  {risk.trendDelta > 0 ? "+" : ""}{risk.trendDelta.toFixed(2)} 24h
                </span>
              </div>
              <span className="hud-label" style={{ color: riskColor }}>
                {risk.level.toUpperCase()}
              </span>
            </div>
          </div>

          {/* Risk gauge bar */}
          <div className="mt-4 h-[6px] w-full rounded-full overflow-hidden" style={{ background: "var(--surface-3)" }}>
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${risk.score * 100}%`,
                background: `linear-gradient(90deg, var(--status-success), ${riskColor})`,
                boxShadow: `0 0 8px ${riskColor}`,
              }}
            />
          </div>
        </div>

        {/* Active Alerts */}
        <div className="glass-l1 p-5 rounded-xl">
          <p className="hud-label mb-2">ACTIVE ALERTS</p>
          <p className="text-[32px] font-bold" style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
            {alerts.filter((a) => !a.acknowledged).length}
          </p>
          <p className="mono-data-sm mt-1" style={{ color: "var(--text-ghost)" }}>
            {alerts.filter((a) => a.severity === "critical" || a.severity === "high").length} high priority
          </p>
        </div>

        {/* Monitors */}
        <div className="glass-l1 p-5 rounded-xl">
          <p className="hud-label mb-2">MONITORS</p>
          <p className="text-[32px] font-bold" style={{ fontFamily: "var(--font-mono)", color: "var(--status-success)" }}>
            4
          </p>
          <p className="mono-data-sm mt-1" style={{ color: "var(--text-ghost)" }}>
            All healthy
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Alerts List */}
        <div className="col-span-2 space-y-2">
          <div className="flex items-center justify-between mb-2">
            <p className="hud-label">ALERTS</p>
          </div>
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`glass-l1 p-4 rounded-xl ${alert.acknowledged ? "opacity-50" : ""}`}
              style={{ borderLeft: `3px solid ${SEVERITY_COLORS[alert.severity]}` }}
            >
              <div className="flex items-start justify-between mb-1">
                <div className="flex items-center gap-2">
                  <AlertTriangle size={14} style={{ color: SEVERITY_COLORS[alert.severity] }} />
                  <span className="text-[14px] font-medium" style={{ color: "var(--text-primary)" }}>
                    {alert.title}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className="hud-label px-1.5 py-[1px] rounded-[4px]"
                    style={{
                      color: SEVERITY_COLORS[alert.severity],
                      background: `color-mix(in srgb, ${SEVERITY_COLORS[alert.severity]} 10%, transparent)`,
                    }}
                  >
                    {alert.severity.toUpperCase()}
                  </span>
                  {!alert.acknowledged && (
                    <button
                      onClick={() => handleAcknowledge(alert.id)}
                      className="mono-data-sm px-2 py-0.5 rounded hover:bg-[var(--surface-hover)] transition-colors"
                      style={{ color: "var(--accent-reason)" }}
                    >
                      ACK
                    </button>
                  )}
                </div>
              </div>
              <p className="text-[13px] mb-1" style={{ color: "var(--text-secondary)" }}>
                {alert.description}
              </p>
              <div className="flex items-center gap-3">
                <span className="hud-label">{alert.source}</span>
                <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                  {Math.round((Date.now() - alert.timestamp) / 60000)}m ago
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Risk Contributors */}
        <div className="space-y-2">
          <p className="hud-label mb-2">RISK CONTRIBUTORS</p>
          {RISK_CONTRIBUTORS.map((rc) => (
            <div key={rc.area} className="glass-l1 p-3 rounded-lg">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[13px] font-medium" style={{ color: "var(--text-primary)" }}>
                  {rc.area}
                </span>
                <div className="flex items-center gap-1">
                  {rc.trend === "rising" ? (
                    <TrendingUp size={12} style={{ color: "var(--status-error)" }} />
                  ) : rc.trend === "falling" ? (
                    <TrendingDown size={12} style={{ color: "var(--status-success)" }} />
                  ) : null}
                  <span className="mono-data-sm font-medium" style={{
                    color: rc.score > 0.1 ? "var(--status-error)" : rc.score > 0.05 ? "var(--status-warning)" : "var(--text-muted)",
                  }}>
                    {rc.score.toFixed(2)}
                  </span>
                </div>
              </div>
              <div className="h-[3px] w-full rounded-full overflow-hidden" style={{ background: "var(--surface-3)" }}>
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.min(rc.score * 500, 100)}%`,
                    background: rc.score > 0.1 ? "var(--status-error)" : rc.score > 0.05 ? "var(--status-warning)" : "var(--status-success)",
                  }}
                />
              </div>
              <span className="mono-data-sm mt-1 block" style={{ color: "var(--text-ghost)" }}>
                {rc.decisions} related decisions
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
