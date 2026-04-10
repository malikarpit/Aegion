"use client";

import { useState } from "react";
import {
    DollarSign, TrendingUp, TrendingDown, Cpu, Zap, Database,
    BarChart3, Activity, Settings, Download, AlertTriangle, Check,
} from "lucide-react";
import { AnimatedCounter } from "@/components/ui/AnimatedCounter";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { Badge } from "@/components/ui/Badge";

// ──────────────────────────────────────────────────────────────────────────────
// Mock data
// ──────────────────────────────────────────────────────────────────────────────

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

// ──────────────────────────────────────────────────────────────────────────────
// Mini chart component
// ──────────────────────────────────────────────────────────────────────────────

function BarMiniChart({ data, color = "#3b82f6" }: { data: { day: string; cost: number }[]; color?: string }) {
    const max = Math.max(...data.map(d => d.cost));
    return (
        <div className="flex items-end gap-1.5 h-24">
            {data.map((d, i) => (
                <div key={d.day} className="flex-1 flex flex-col items-center gap-1">
                    <div
                        className="w-full rounded-t-md transition-all duration-500"
                        style={{
                            height: `${(d.cost / max) * 100}%`,
                            background: `linear-gradient(to top, ${color}40, ${color})`,
                        }}
                        data-delay={i * 80}
                    />
                    <span className="text-[9px] text-slate-600">{d.day.split(" ")[1]}</span>
                </div>
            ))}
        </div>
    );
}

function ProviderCard({ provider }: { provider: typeof PROVIDERS[0] }) {
    const statusColor = provider.status === "healthy" ? "green" : "red";
    return (
        <div className="glass-card card-lift p-5">
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <div className={`status-dot ${statusColor}`} />
                    <span className="text-sm font-semibold text-white">{provider.name}</span>
                </div>
                <Badge variant={provider.status === "healthy" ? "success" : "danger"}>
                    {provider.status}
                </Badge>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                    <div className="text-lg font-bold text-white">${provider.cost.toFixed(2)}</div>
                    <div className="text-[10px] text-slate-500">Total Cost</div>
                </div>
                <div>
                    <div className="text-lg font-bold text-white">{provider.calls}</div>
                    <div className="text-[10px] text-slate-500">API Calls</div>
                </div>
                <div>
                    <div className="text-lg font-bold text-white">{provider.avgLatency}ms</div>
                    <div className="text-[10px] text-slate-500">Avg Latency</div>
                </div>
            </div>
            <div className="mt-3 flex gap-1">
                {provider.models.map(m => (
                    <span key={m} className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.04] text-slate-400">
                        {m}
                    </span>
                ))}
            </div>
        </div>
    );
}

// ──────────────────────────────────────────────────────────────────────────────
// Main Page
// ──────────────────────────────────────────────────────────────────────────────

export default function CostDashboardPage() {
    const [period, setPeriod] = useState<"7d" | "30d" | "90d">("7d");
    const budgetPercent = (BUDGET.spent / BUDGET.monthly) * 100;

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <DollarSign className="w-6 h-6 text-emerald-400" />
                        Cost Analytics
                    </h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Token spend, budget tracking, and provider performance
                    </p>
                </div>
                <div className="flex gap-2">
                    {(["7d", "30d", "90d"] as const).map(p => (
                        <button
                            key={p}
                            onClick={() => setPeriod(p)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                                period === p
                                    ? "bg-blue-600 text-white"
                                    : "bg-white/[0.04] text-slate-400 hover:text-white hover:bg-white/[0.08]"
                            }`}
                        >
                            {p}
                        </button>
                    ))}
                    <button className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/[0.04] text-slate-400 hover:text-white hover:bg-white/[0.08] transition-all flex items-center gap-1">
                        <Download className="w-3 h-3" />
                        Export
                    </button>
                </div>
            </div>

            {/* Top Row: Budget Ring + Daily Chart + Cache */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Budget Ring */}
                <div className="glass-card p-6 flex flex-col items-center stagger-1">
                    <h3 className="text-sm font-semibold text-white mb-4">Monthly Budget</h3>
                    <ProgressRing
                        value={100 - budgetPercent}
                        size={140}
                        strokeWidth={10}
                        color="auto"
                        label="Remaining"
                    />
                    <div className="mt-4 text-center space-y-1">
                        <div className="flex items-center justify-center gap-2">
                            <span className="text-sm text-slate-400">Spent:</span>
                            <span className="text-sm font-bold text-white">
                                $<AnimatedCounter value={BUDGET.spent} decimals={2} />
                            </span>
                            <span className="text-sm text-slate-500">/ ${BUDGET.monthly}</span>
                        </div>
                        <div className="flex items-center justify-center gap-2">
                            <span className="text-sm text-slate-400">Today:</span>
                            <span className="text-sm font-medium text-white">${BUDGET.spentToday}</span>
                            <span className="text-sm text-slate-500">/ ${BUDGET.daily}</span>
                        </div>
                        {BUDGET.autoPause && (
                            <div className="flex items-center justify-center gap-1 text-xs text-emerald-400">
                                <Check className="w-3 h-3" />
                                Auto-pause on budget exceeded
                            </div>
                        )}
                    </div>
                </div>

                {/* Daily Spend Bar Chart */}
                <div className="glass-card p-6 stagger-2">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-sm font-semibold text-white">Daily Spend</h3>
                        <span className="text-xs text-slate-500">Last 7 days</span>
                    </div>
                    <BarMiniChart data={DAILY_COSTS} />
                    <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                        <span>Avg: $2.30/day</span>
                        <span className="text-emerald-400 flex items-center gap-1">
                            <TrendingDown className="w-3 h-3" /> -12% vs last week
                        </span>
                    </div>
                </div>

                {/* Cache Performance */}
                <div className="glass-card p-6 stagger-3">
                    <h3 className="text-sm font-semibold text-white mb-4">Cache Performance</h3>
                    <ProgressRing
                        value={(CACHE_STATS.hits / (CACHE_STATS.hits + CACHE_STATS.misses)) * 100}
                        size={100}
                        color="stroke-cyan-400"
                        label="Hit Rate"
                        className="mx-auto"
                    />
                    <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                        <div>
                            <div className="text-sm font-bold text-emerald-400">{CACHE_STATS.hits}</div>
                            <div className="text-[10px] text-slate-500">Hits</div>
                        </div>
                        <div>
                            <div className="text-sm font-bold text-slate-400">{CACHE_STATS.misses}</div>
                            <div className="text-[10px] text-slate-500">Misses</div>
                        </div>
                        <div>
                            <div className="text-sm font-bold text-cyan-400">${CACHE_STATS.savings}</div>
                            <div className="text-[10px] text-slate-500">Saved</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Provider Cards */}
            <div>
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-purple-400" />
                    Provider Performance
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {PROVIDERS.map((p, i) => (
                        <ProviderCard key={p.name} provider={p} />
                    ))}
                </div>
            </div>

            {/* Model Leaderboard */}
            <div className="glass-card-static overflow-hidden">
                <div className="px-5 py-4 border-b border-white/[0.05] flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-blue-400" />
                        Model Leaderboard
                    </h3>
                    <span className="text-xs text-slate-500">Sorted by total cost</span>
                </div>
                <div className="overflow-x-auto">
                    <table className="data-table w-full">
                        <thead>
                            <tr>
                                <th className="text-left">Model</th>
                                <th className="text-left">Provider</th>
                                <th className="text-right">Calls</th>
                                <th className="text-right">Total Cost</th>
                                <th className="text-right">Avg Cost/Call</th>
                                <th className="text-right">Avg Latency</th>
                            </tr>
                        </thead>
                        <tbody>
                            {MODEL_LEADERBOARD.map((m, i) => (
                                <tr key={m.model}>
                                    <td className="text-left">
                                        <span className="text-sm font-medium text-white">{m.model}</span>
                                    </td>
                                    <td className="text-left">
                                        <span className="text-sm text-slate-400">{m.provider}</span>
                                    </td>
                                    <td className="text-right">
                                        <span className="text-sm tabular-nums text-slate-300">{m.calls}</span>
                                    </td>
                                    <td className="text-right">
                                        <span className="text-sm tabular-nums font-medium text-white">${m.totalCost.toFixed(2)}</span>
                                    </td>
                                    <td className="text-right">
                                        <span className={`text-sm tabular-nums ${m.avgCost > 0.10 ? "text-yellow-400" : "text-emerald-400"}`}>
                                            ${m.avgCost.toFixed(3)}
                                        </span>
                                    </td>
                                    <td className="text-right">
                                        <span className={`text-sm tabular-nums ${m.avgLatency > 1000 ? "text-yellow-400" : "text-slate-300"}`}>
                                            {m.avgLatency}ms
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
