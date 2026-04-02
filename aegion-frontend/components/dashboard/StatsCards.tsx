"use client";

import { TrendingUp, TrendingDown, Layers, FileCheck, CheckCircle2, DollarSign } from "lucide-react";
import { MOCK_STATS } from "@/lib/mock-data";

interface StatCardProps {
    title: string;
    value: string | number;
    change: number;
    icon: React.ReactNode;
    prefix?: string;
}

function StatCard({ title, value, change, icon, prefix = "" }: StatCardProps) {
    const isPositive = change >= 0;

    return (
        <div className="glass-card p-5 group">
            <div className="flex items-start justify-between mb-3">
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                    {title}
                </span>
                <div className="p-2 rounded-lg bg-white/5 text-slate-400 group-hover:text-blue-400 transition-colors">
                    {icon}
                </div>
            </div>
            <div className="text-3xl font-bold text-white mb-1 animate-fade-in">
                {prefix}{value}
            </div>
            <div className={`flex items-center gap-1 text-xs ${isPositive ? "text-emerald-400" : "text-red-400"}`}>
                {isPositive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                <span>{Math.abs(change)}% vs yesterday</span>
            </div>
        </div>
    );
}

export function StatsCards() {
    const stats = MOCK_STATS;

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
                title="Active Sessions"
                value={stats.activeSessions}
                change={stats.sessionChange}
                icon={<Layers size={18} />}
            />
            <StatCard
                title="Pending Proposals"
                value={stats.pendingProposals}
                change={stats.proposalChange}
                icon={<FileCheck size={18} />}
            />
            <StatCard
                title="Total Decisions"
                value={stats.totalDecisions}
                change={stats.decisionChange}
                icon={<CheckCircle2 size={18} />}
            />
            <StatCard
                title="Cost (24h)"
                value={stats.costToday.toFixed(2)}
                change={stats.costChange}
                icon={<DollarSign size={18} />}
                prefix="$"
            />
        </div>
    );
}
