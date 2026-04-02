import { Metadata } from "next";
import { StatsCards } from "@/components/dashboard/StatsCards";
import { CostChart } from "@/components/dashboard/CostChart";
import { DecisionPie } from "@/components/dashboard/DecisionPie";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { RiskGauge } from "@/components/dashboard/RiskGauge";

export const metadata: Metadata = {
    title: "Dashboard — Aegion",
    description: "Aegion AI Governance Dashboard - Real-time metrics and activity feed",
};

export default function DashboardPage() {
    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            {/* Page Header */}
            <div>
                <h1 className="text-2xl font-bold text-white">Dashboard</h1>
                <p className="text-sm text-slate-500 mt-1">
                    System overview and real-time governance metrics
                </p>
            </div>

            {/* KPI Cards */}
            <StatsCards />

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    <CostChart />
                </div>
                <div>
                    <DecisionPie />
                </div>
            </div>

            {/* Activity + Risk Row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    <RecentActivity />
                </div>
                <div>
                    <RiskGauge />
                </div>
            </div>
        </div>
    );
}
