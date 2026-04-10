"use client";

import { useState, useEffect } from "react";
import {
    Zap, FileCheck, Brain, DollarSign, Shield, Clock,
    TrendingUp, AlertTriangle, Activity, ChevronRight,
    Play, Plus, Eye, RefreshCw,
} from "lucide-react";
import { AnimatedCounter } from "@/components/ui/AnimatedCounter";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { Badge } from "@/components/ui/Badge";

// ──────────────────────────────────────────────────────────────────────────────
// Mock data (replaced by API hooks in production)
// ──────────────────────────────────────────────────────────────────────────────

const MOCK_KPI = {
    activeSessions: 3,
    pendingProposals: 7,
    totalDecisions: 142,
    tokenSpendToday: 2.47,
    budgetRemaining: 72,
    riskScore: 28,
    cacheHitRate: 64,
    councilInvocations: 23,
};

const MOCK_ACTIVITY = [
    { id: "1", action: "Council invoked", entity: "Architecture review", user: "arpit", time: "2 min ago", type: "council" },
    { id: "2", action: "Proposal approved", entity: "Add Redis caching layer", user: "system", time: "15 min ago", type: "proposal" },
    { id: "3", action: "Decision recorded", entity: "Use pgvector for embeddings", user: "council", time: "1 hr ago", type: "decision" },
    { id: "4", action: "Risk alert", entity: "Velocity above threshold", user: "sentinel", time: "2 hr ago", type: "alert" },
    { id: "5", action: "Session started", entity: "Sprint 14 planning", user: "arpit", time: "3 hr ago", type: "session" },
    { id: "6", action: "Memory created", entity: "Prefer FastAPI over Flask", user: "system", time: "5 hr ago", type: "memory" },
];

const MOCK_COST_7D = [
    { day: "Mon", cost: 1.2 }, { day: "Tue", cost: 3.1 }, { day: "Wed", cost: 2.4 },
    { day: "Thu", cost: 1.8 }, { day: "Fri", cost: 4.2 }, { day: "Sat", cost: 0.9 },
    { day: "Sun", cost: 2.5 },
];

// ──────────────────────────────────────────────────────────────────────────────
// Components
// ──────────────────────────────────────────────────────────────────────────────

function KpiCard({
    icon: Icon, label, value, prefix, suffix, color, delay, trend,
}: {
    icon: any; label: string; value: number; prefix?: string; suffix?: string;
    color: string; delay: number; trend?: string;
}) {
    return (
        <div className={`glass-card card-lift p-5 stagger-${delay}`}>
            <div className="flex items-center justify-between mb-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
                    <Icon className="w-5 h-5" />
                </div>
                {trend && (
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        trend.startsWith("+") ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                    }`}>
                        {trend}
                    </span>
                )}
            </div>
            <div className="text-2xl font-bold text-white mb-1">
                <AnimatedCounter value={value} prefix={prefix} suffix={suffix} decimals={prefix === "$" ? 2 : 0} />
            </div>
            <div className="text-xs text-slate-500">{label}</div>
        </div>
    );
}

function SparkLine({ data, color = "#3b82f6" }: { data: number[]; color?: string }) {
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    const w = 100;
    const h = 32;

    const points = data.map((v, i) => {
        const x = (i / (data.length - 1)) * w;
        const y = h - ((v - min) / range) * h;
        return `${x},${y}`;
    }).join(" ");

    return (
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-8" preserveAspectRatio="none">
            <defs>
                <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity="0.3" />
                    <stop offset="100%" stopColor={color} stopOpacity="0" />
                </linearGradient>
            </defs>
            <polygon
                points={`0,${h} ${points} ${w},${h}`}
                fill="url(#sparkGrad)"
            />
            <polyline
                points={points}
                fill="none"
                stroke={color}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

function ActivityItem({ item, index }: { item: typeof MOCK_ACTIVITY[0]; index: number }) {
    const iconMap: Record<string, any> = {
        council: Brain, proposal: FileCheck, decision: Zap,
        alert: AlertTriangle, session: Play, memory: Activity,
    };
    const colorMap: Record<string, string> = {
        council: "text-purple-400 bg-purple-500/10",
        proposal: "text-blue-400 bg-blue-500/10",
        decision: "text-emerald-400 bg-emerald-500/10",
        alert: "text-yellow-400 bg-yellow-500/10",
        session: "text-cyan-400 bg-cyan-500/10",
        memory: "text-slate-400 bg-slate-500/10",
    };

    const Icon = iconMap[item.type] || Activity;
    const col = colorMap[item.type] || "text-slate-400 bg-slate-500/10";

    return (
        <div className={`flex items-center gap-3 py-3 px-4 rounded-xl hover:bg-white/[0.02] transition-colors stagger-${index + 1}`}>
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${col}`}>
                <Icon className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
                <div className="text-sm text-white truncate">
                    <span className="font-medium">{item.action}</span>
                    <span className="text-slate-400"> · </span>
                    <span className="text-slate-300">{item.entity}</span>
                </div>
                <div className="text-xs text-slate-500 mt-0.5">{item.user} · {item.time}</div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-600 flex-shrink-0" />
        </div>
    );
}

function QuickAction({
    icon: Icon, label, color, onClick,
}: {
    icon: any; label: string; color: string; onClick?: () => void;
}) {
    return (
        <button
            onClick={onClick}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border transition-all text-sm font-medium btn-glow ${color}`}
        >
            <Icon className="w-4 h-4" />
            {label}
        </button>
    );
}

// ──────────────────────────────────────────────────────────────────────────────
// Main Dashboard
// ──────────────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
    const [kpi] = useState(MOCK_KPI);
    const [isFrozen] = useState(false);

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            {/* Freeze Banner */}
            {isFrozen && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-5 py-3 flex items-center gap-3 animate-slide-down">
                    <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0" />
                    <div>
                        <span className="text-sm font-semibold text-red-300">Governance Frozen</span>
                        <span className="text-sm text-red-400/80 ml-2">
                            All proposals are paused by Archon. Contact admin to unfreeze.
                        </span>
                    </div>
                </div>
            )}

            {/* Header + Quick Actions */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-white">Dashboard</h1>
                    <p className="text-sm text-slate-500 mt-1">
                        System overview and real-time governance metrics
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <QuickAction
                        icon={Plus}
                        label="New Session"
                        color="bg-blue-600/10 border-blue-500/20 text-blue-400 hover:bg-blue-600/20"
                    />
                    <QuickAction
                        icon={Brain}
                        label="Invoke Council"
                        color="bg-purple-600/10 border-purple-500/20 text-purple-400 hover:bg-purple-600/20"
                    />
                    <QuickAction
                        icon={Eye}
                        label="View Timeline"
                        color="bg-cyan-600/10 border-cyan-500/20 text-cyan-400 hover:bg-cyan-600/20"
                    />
                </div>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <KpiCard
                    icon={Zap} label="Active Sessions" value={kpi.activeSessions}
                    color="bg-blue-500/10 text-blue-400" delay={1} trend="+2"
                />
                <KpiCard
                    icon={FileCheck} label="Pending Proposals" value={kpi.pendingProposals}
                    color="bg-purple-500/10 text-purple-400" delay={2}
                />
                <KpiCard
                    icon={DollarSign} label="Spend Today" value={kpi.tokenSpendToday}
                    prefix="$" color="bg-emerald-500/10 text-emerald-400" delay={3}
                />
                <KpiCard
                    icon={Brain} label="Council Invocations" value={kpi.councilInvocations}
                    color="bg-cyan-500/10 text-cyan-400" delay={4} trend="+5"
                />
            </div>

            {/* Charts + Gauges Row */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                {/* Cost Sparkline */}
                <div className="lg:col-span-2 glass-card p-5 stagger-5">
                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <h3 className="text-sm font-semibold text-white">Token Spend (7 days)</h3>
                            <span className="text-xs text-slate-500">Daily cost trend</span>
                        </div>
                        <span className="text-lg font-bold text-white tabular-nums">
                            $<AnimatedCounter value={16.1} decimals={2} />
                        </span>
                    </div>
                    <SparkLine data={MOCK_COST_7D.map(d => d.cost)} color="#3b82f6" />
                    <div className="flex justify-between mt-2 text-[10px] text-slate-600">
                        {MOCK_COST_7D.map(d => <span key={d.day}>{d.day}</span>)}
                    </div>
                </div>

                {/* Budget Ring */}
                <div className="glass-card p-5 flex flex-col items-center justify-center stagger-6">
                    <ProgressRing
                        value={kpi.budgetRemaining}
                        size={100}
                        color="auto"
                        label="Budget Left"
                    />
                    <div className="text-xs text-slate-500 mt-3">$72 of $100 remaining</div>
                </div>

                {/* Cache Hit Rate */}
                <div className="glass-card p-5 flex flex-col items-center justify-center stagger-7">
                    <ProgressRing
                        value={kpi.cacheHitRate}
                        size={100}
                        color="stroke-cyan-400"
                        label="Cache Hits"
                    />
                    <div className="text-xs text-slate-500 mt-3">
                        <AnimatedCounter value={kpi.cacheHitRate} suffix="%" /> savings
                    </div>
                </div>
            </div>

            {/* Activity Feed + Risk */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Activity Feed */}
                <div className="lg:col-span-2 glass-card-static overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.05]">
                        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                            <Activity className="w-4 h-4 text-blue-400" />
                            Recent Activity
                        </h3>
                        <button className="text-xs text-blue-400 hover:text-blue-300 transition-colors flex items-center gap-1">
                            <RefreshCw className="w-3 h-3" />
                            Refresh
                        </button>
                    </div>
                    <div className="divide-y divide-white/[0.03]">
                        {MOCK_ACTIVITY.map((item, i) => (
                            <ActivityItem key={item.id} item={item} index={i} />
                        ))}
                    </div>
                    <div className="p-3 border-t border-white/[0.05]">
                        <button className="w-full text-xs text-slate-400 hover:text-blue-400 transition-colors py-2 rounded-lg hover:bg-white/[0.02]">
                            View full timeline →
                        </button>
                    </div>
                </div>

                {/* Risk Overview */}
                <div className="glass-card-static overflow-hidden">
                    <div className="px-5 py-4 border-b border-white/[0.05]">
                        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                            <Shield className="w-4 h-4 text-emerald-400" />
                            System Health
                        </h3>
                    </div>
                    <div className="p-5 space-y-4">
                        {/* Risk Score */}
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-slate-400">Risk Score</span>
                            <div className="flex items-center gap-2">
                                <div className="status-dot green" />
                                <span className="text-sm font-medium text-emerald-400">Low ({kpi.riskScore})</span>
                            </div>
                        </div>

                        {/* Governance Status */}
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-slate-400">Governance</span>
                            <Badge variant="success">Active</Badge>
                        </div>

                        {/* API Status */}
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-slate-400">API Health</span>
                            <div className="flex items-center gap-2">
                                <div className="status-dot green" />
                                <span className="text-xs text-slate-300">All systems operational</span>
                            </div>
                        </div>

                        {/* Decision Velocity */}
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-slate-400">Decision Velocity</span>
                            <span className="text-sm text-slate-300">3.2/hr</span>
                        </div>

                        {/* Total Decisions */}
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-slate-400">Total Decisions</span>
                            <span className="text-sm font-medium text-white">
                                <AnimatedCounter value={kpi.totalDecisions} />
                            </span>
                        </div>

                        {/* Risk Tier Distribution */}
                        <div className="pt-2 border-t border-white/[0.05]">
                            <span className="text-xs text-slate-500 block mb-2">Risk Tier Distribution</span>
                            <div className="flex gap-1 h-2 rounded-full overflow-hidden">
                                <div className="bg-emerald-500 flex-[6]" title="T0: 60%" />
                                <div className="bg-blue-500 flex-[2.5]" title="T1: 25%" />
                                <div className="bg-yellow-500 flex-[1]" title="T2: 10%" />
                                <div className="bg-red-500 flex-[0.5]" title="T3: 5%" />
                            </div>
                            <div className="flex justify-between mt-1 text-[10px] text-slate-600">
                                <span>T0 (60%)</span>
                                <span>T1 (25%)</span>
                                <span>T2 (10%)</span>
                                <span>T3 (5%)</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
