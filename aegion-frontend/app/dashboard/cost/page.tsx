"use client";

import { useState } from "react";
import {
  DollarSign, TrendingDown, Cpu,
  BarChart3, Download, Check,
} from "lucide-react";
import { AnimatedCounter } from "@/components/ui/AnimatedCounter";
import { ProgressRing } from "@/components/ui/ProgressRing";

/* ══════════════════════════════════════════════════════════════
   COST DASHBOARD — Token spend, budget tracking, provider perf
   ══════════════════════════════════════════════════════════════ */

const BUDGET = { monthly: 100, spent: 47.30, daily: 10, spentToday: 2.47, autoPause: true };

const PROVIDERS = [
  { name: "OpenAI", models: ["gpt-4o", "gpt-4o-mini"], cost: 28.40, calls: 340, avgLatency: 820, status: "healthy" },
  { name: "Anthropic", models: ["claude-sonnet-4", "claude-haiku"], cost: 12.50, calls: 180, avgLatency: 650, status: "healthy" },
  { name: "Google", models: ["gemini-2.0-flash", "gemini-2.5-pro"], cost: 6.40, calls: 520, avgLatency: 340, status: "healthy" },
];

const MODEL_LEADERBOARD = [
  { model: "gemini-2.0-flash", provider: "Google", calls: 420, totalCost: 4.20, avgCost: 0.01, avgLatency: 280 },
  { model: "gpt-4o-mini", provider: "OpenAI", calls: 220, totalCost: 8.80, avgCost: 0.04, avgLatency: 520 },
  { model: "claude-haiku", provider: "Anthropic", calls: 140, totalCost: 4.20, avgCost: 0.03, avgLatency: 380 },
  { model: "gpt-4o", provider: "OpenAI", calls: 120, totalCost: 19.60, avgCost: 0.16, avgLatency: 1200 },
  { model: "claude-sonnet-4", provider: "Anthropic", calls: 40, totalCost: 8.30, avgCost: 0.21, avgLatency: 900 },
  { model: "gemini-2.5-pro", provider: "Google", calls: 20, totalCost: 2.20, avgCost: 0.11, avgLatency: 680 },
];

const DAILY_COSTS = [
  { day: "Apr 4", cost: 1.2 }, { day: "Apr 5", cost: 3.1 }, { day: "Apr 6", cost: 2.4 },
  { day: "Apr 7", cost: 1.8 }, { day: "Apr 8", cost: 4.2 }, { day: "Apr 9", cost: 0.9 },
  { day: "Apr 10", cost: 2.5 },
];

const CACHE_STATS = { hits: 640, misses: 360, savings: 12.80 };

function BarMiniChart({ data }: { data: { day: string; cost: number }[] }) {
  const max = Math.max(...data.map(d => d.cost));
  const svgH = 80;
  const barW = 12;
  const gap = 6;
  const totalW = data.length * (barW + gap) - gap;

  return (
    <svg viewBox={`0 0 ${totalW} ${svgH + 14}`} className="w-full" aria-label="Daily spend bar chart">
      <defs>
        <linearGradient id="barGrad" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stopColor="hsl(217,85%,60%)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="hsl(217,85%,60%)" stopOpacity="1" />
        </linearGradient>
      </defs>
      {data.map((d, i) => {
        const barH = max > 0 ? (d.cost / max) * svgH : 0;
        const x = i * (barW + gap);
        const y = svgH - barH;
        const label = d.day.split(" ")[1] ?? d.day;
        return (
          <g key={d.day}>
            <rect x={x} y={y} width={barW} height={barH} rx={2} ry={2} fill="url(#barGrad)" />
            <text x={x + barW / 2} y={svgH + 11} textAnchor="middle" fontSize={8} fill="hsl(220,12%,40%)">
              {label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function CostDashboardPage() {
  const [period, setPeriod] = useState<"7d" | "30d" | "90d">("7d");
  const budgetPercent = (BUDGET.spent / BUDGET.monthly) * 100;

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-page-enter">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-bold flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
            <DollarSign className="w-5 h-5" style={{ color: "var(--accent-cost)" }} />
            Cost Analytics
          </h1>
          <p className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
            Token spend, budget tracking, and provider performance
          </p>
        </div>
        <div className="flex gap-2">
          {(["7d", "30d", "90d"] as const).map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className="px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all"
              style={{
                background: period === p ? "var(--accent-reason)" : "var(--surface-3)",
                color: period === p ? "white" : "var(--text-muted)",
              }}
            >
              {p}
            </button>
          ))}
          <button
            className="px-3 py-1.5 rounded-lg text-[12px] font-medium flex items-center gap-1 transition-all hover:bg-[var(--surface-hover)]"
            style={{ background: "var(--surface-3)", color: "var(--text-muted)" }}
          >
            <Download className="w-3 h-3" /> Export
          </button>
        </div>
      </div>

      {/* Top Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Budget Ring */}
        <div className="glass-l1 p-6 rounded-xl flex flex-col items-center">
          <p className="hud-label mb-4">MONTHLY BUDGET</p>
          <ProgressRing value={100 - budgetPercent} size={140} strokeWidth={10} color="auto" label="Remaining" />
          <div className="mt-4 text-center space-y-1">
            <div className="flex items-center justify-center gap-2">
              <span className="text-[13px]" style={{ color: "var(--text-muted)" }}>Spent:</span>
              <span className="mono-data font-medium" style={{ color: "var(--text-primary)" }}>
                $<AnimatedCounter value={BUDGET.spent} decimals={2} />
              </span>
              <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>/ ${BUDGET.monthly}</span>
            </div>
            <div className="flex items-center justify-center gap-2">
              <span className="text-[13px]" style={{ color: "var(--text-muted)" }}>Today:</span>
              <span className="mono-data font-medium" style={{ color: "var(--text-primary)" }}>${BUDGET.spentToday}</span>
              <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>/ ${BUDGET.daily}</span>
            </div>
            {BUDGET.autoPause && (
              <div className="flex items-center justify-center gap-1">
                <Check className="w-3 h-3" style={{ color: "var(--status-success)" }} />
                <span className="mono-data-sm" style={{ color: "var(--status-success)" }}>Auto-pause on exceed</span>
              </div>
            )}
          </div>
        </div>

        {/* Daily Spend */}
        <div className="glass-l1 p-6 rounded-xl">
          <div className="flex items-center justify-between mb-4">
            <p className="hud-label">DAILY SPEND</p>
            <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>Last 7 days</span>
          </div>
          <BarMiniChart data={DAILY_COSTS} />
          <div className="mt-3 flex items-center justify-between">
            <span className="mono-data-sm" style={{ color: "var(--text-muted)" }}>Avg: $2.30/day</span>
            <span className="mono-data-sm flex items-center gap-1" style={{ color: "var(--status-success)" }}>
              <TrendingDown className="w-3 h-3" /> -12% vs last week
            </span>
          </div>
        </div>

        {/* Cache */}
        <div className="glass-l1 p-6 rounded-xl">
          <p className="hud-label mb-4">CACHE PERFORMANCE</p>
          <ProgressRing
            value={(CACHE_STATS.hits / (CACHE_STATS.hits + CACHE_STATS.misses)) * 100}
            size={100} color="stroke-cyan-400" label="Hit Rate" className="mx-auto"
          />
          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="mono-data font-medium" style={{ color: "var(--status-success)" }}>{CACHE_STATS.hits}</p>
              <p className="hud-label">Hits</p>
            </div>
            <div>
              <p className="mono-data font-medium" style={{ color: "var(--text-muted)" }}>{CACHE_STATS.misses}</p>
              <p className="hud-label">Misses</p>
            </div>
            <div>
              <p className="mono-data font-medium" style={{ color: "var(--accent-execute)" }}>${CACHE_STATS.savings}</p>
              <p className="hud-label">Saved</p>
            </div>
          </div>
        </div>
      </div>

      {/* Providers */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Cpu className="w-4 h-4" style={{ color: "var(--accent-govern)" }} />
          <p className="text-[14px] font-semibold" style={{ color: "var(--text-primary)" }}>Provider Performance</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {PROVIDERS.map((provider) => (
            <div key={provider.name} className="glass-l1 p-5 rounded-xl card-lift">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: "var(--status-success)" }} />
                  <span className="text-[14px] font-semibold" style={{ color: "var(--text-primary)" }}>{provider.name}</span>
                </div>
                <span className="hud-label px-1.5 py-[1px] rounded-[4px]" style={{ background: "hsla(142,60%,48%,0.1)", color: "var(--status-success)" }}>
                  {provider.status}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <p className="mono-data font-medium" style={{ color: "var(--text-primary)" }}>${provider.cost.toFixed(2)}</p>
                  <p className="hud-label">Cost</p>
                </div>
                <div>
                  <p className="mono-data font-medium" style={{ color: "var(--text-primary)" }}>{provider.calls}</p>
                  <p className="hud-label">Calls</p>
                </div>
                <div>
                  <p className="mono-data font-medium" style={{ color: "var(--text-primary)" }}>{provider.avgLatency}ms</p>
                  <p className="hud-label">Latency</p>
                </div>
              </div>
              <div className="mt-3 flex gap-1 flex-wrap">
                {provider.models.map(m => (
                  <span key={m} className="hud-label px-2 py-0.5 rounded-[4px]" style={{ background: "var(--surface-3)" }}>
                    {m}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Model Leaderboard */}
      <div className="glass-l1 rounded-xl overflow-hidden">
        <div className="px-5 py-4 flex items-center justify-between" style={{ borderBottom: "0.5px solid var(--border-subtle)" }}>
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4" style={{ color: "var(--accent-reason)" }} />
            <p className="text-[14px] font-semibold" style={{ color: "var(--text-primary)" }}>Model Leaderboard</p>
          </div>
          <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>Sorted by total cost</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr style={{ borderBottom: "0.5px solid var(--border-subtle)" }}>
                {["Model", "Provider", "Calls", "Total Cost", "Avg Cost", "Avg Latency"].map((h, i) => (
                  <th key={h} className={`px-5 py-3 hud-label ${i >= 2 ? "text-right" : "text-left"}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MODEL_LEADERBOARD.map((m) => (
                <tr key={m.model} className="hover:bg-[var(--surface-hover)] transition-colors" style={{ borderBottom: "0.5px solid var(--border-subtle)" }}>
                  <td className="px-5 py-3 text-[13px] font-medium" style={{ color: "var(--text-primary)" }}>{m.model}</td>
                  <td className="px-5 py-3 text-[13px]" style={{ color: "var(--text-secondary)" }}>{m.provider}</td>
                  <td className="px-5 py-3 text-right mono-data-sm" style={{ color: "var(--text-secondary)" }}>{m.calls}</td>
                  <td className="px-5 py-3 text-right mono-data font-medium" style={{ color: "var(--text-primary)" }}>${m.totalCost.toFixed(2)}</td>
                  <td className="px-5 py-3 text-right mono-data-sm" style={{ color: m.avgCost > 0.10 ? "var(--status-warning)" : "var(--status-success)" }}>${m.avgCost.toFixed(3)}</td>
                  <td className="px-5 py-3 text-right mono-data-sm" style={{ color: m.avgLatency > 1000 ? "var(--status-warning)" : "var(--text-secondary)" }}>{m.avgLatency}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
