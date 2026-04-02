"use client";

import {
    AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
    Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { DollarSign, TrendingUp, Zap, Database } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { MOCK_COST_OVER_TIME, MOCK_COST_MODELS, MOCK_STATS } from "@/lib/mock-data";

function MetricCard({ title, value, icon, subtitle, className = "" }: {
    title: string; value: string; icon: React.ReactNode; subtitle: string; className?: string;
}) {
    return (
        <div className={`glass-card p-5 ${className}`}>
            <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-500 uppercase tracking-wider">{title}</span>
                <div className="text-slate-400">{icon}</div>
            </div>
            <p className="text-2xl font-bold text-white">{value}</p>
            <p className="text-xs text-slate-500 mt-1">{subtitle}</p>
        </div>
    );
}

export default function CostPage() {
    const totalSpend = MOCK_COST_MODELS.reduce((s, m) => s + m.totalSpend, 0);
    const budget = 50;

    const barData = MOCK_COST_OVER_TIME.slice(-14).map((d) => ({
        date: d.date,
        total: +(d.openai + d.anthropic + d.google + d.deepseek).toFixed(2),
    }));

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div>
                <h1 className="text-2xl font-bold text-white">Cost Dashboard</h1>
                <p className="text-sm text-slate-500 mt-1">
                    Track spending, budget utilization, and model efficiency
                </p>
            </div>

            {/* KPI Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard
                    title="Total Spend (30d)"
                    value={`$${totalSpend.toFixed(2)}`}
                    icon={<DollarSign size={18} />}
                    subtitle={`${((totalSpend / budget) * 100).toFixed(0)}% of $${budget} budget`}
                />
                <MetricCard
                    title="Avg Daily"
                    value={`$${(totalSpend / 30).toFixed(2)}`}
                    icon={<TrendingUp size={18} />}
                    subtitle="Per day average"
                />
                <MetricCard
                    title="Cache Hit Rate"
                    value={`${MOCK_STATS.cacheHitRate}%`}
                    icon={<Zap size={18} />}
                    subtitle="Saving ~$12.40 / month"
                />
                <MetricCard
                    title="Cheapest Model"
                    value="DeepSeek"
                    icon={<Database size={18} />}
                    subtitle="$0.0008 / query avg"
                />
            </div>

            {/* Budget Burn Chart */}
            <div className="glass-card-static p-6">
                <h3 className="text-lg font-semibold text-white mb-1">Budget Burn</h3>
                <p className="text-xs text-slate-500 mb-6">Daily spend vs budget limit (last 14 days)</p>
                <div className="h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={barData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                            <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#64748b", fontSize: 11 }} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
                            <Tooltip
                                content={({ active, payload, label }) => {
                                    if (!active || !payload?.length) return null;
                                    return (
                                        <div className="bg-[#111118] border border-white/10 rounded-lg px-3 py-2 text-xs shadow-xl">
                                            <p className="text-slate-400 mb-1">{label}</p>
                                            <p className="text-white font-bold">${payload[0].value}</p>
                                        </div>
                                    );
                                }}
                            />
                            <ReferenceLine y={budget / 30} stroke="#ef4444" strokeDasharray="5 5" label={{ value: "Daily Budget", fill: "#ef4444", fontSize: 10 }} />
                            <Bar dataKey="total" radius={[4, 4, 0, 0]} fill="url(#barGradient)" />
                            <defs>
                                <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.8} />
                                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.2} />
                                </linearGradient>
                            </defs>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Model Leaderboard */}
            <div className="glass-card-static p-6">
                <h3 className="text-lg font-semibold text-white mb-1">Model Leaderboard</h3>
                <p className="text-xs text-slate-500 mb-4">Accuracy vs cost comparison</p>

                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-white/5">
                                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Model</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Provider</th>
                                <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">Accuracy</th>
                                <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">Avg Cost</th>
                                <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">Cache Rate</th>
                                <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">Total Spend</th>
                            </tr>
                        </thead>
                        <tbody>
                            {MOCK_COST_MODELS.sort((a, b) => b.accuracy - a.accuracy).map((m) => (
                                <tr key={m.model} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                                    <td className="px-4 py-3 font-medium text-white font-mono text-xs">{m.model}</td>
                                    <td className="px-4 py-3 text-slate-400">{m.provider}</td>
                                    <td className="px-4 py-3 text-right">
                                        <Badge variant={m.accuracy >= 90 ? "success" : m.accuracy >= 80 ? "info" : "warning"} size="sm">
                                            {m.accuracy}%
                                        </Badge>
                                    </td>
                                    <td className="px-4 py-3 text-right text-slate-300 font-mono">
                                        ${m.avgCost.toFixed(4)}
                                    </td>
                                    <td className="px-4 py-3 text-right text-slate-400">{m.cacheRate}%</td>
                                    <td className="px-4 py-3 text-right text-white font-medium">
                                        ${m.totalSpend.toFixed(2)}
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
