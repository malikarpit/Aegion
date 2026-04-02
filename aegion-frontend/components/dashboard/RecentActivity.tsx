"use client";

import { formatDistanceToNow } from "date-fns";
import { CheckCircle2, XCircle, AlertTriangle, Clock, FileText, Brain, Zap, Activity } from "lucide-react";
import { MOCK_RECENT_ACTIVITY } from "@/lib/mock-data";

const eventIcons: Record<string, React.ReactNode> = {
    proposal_approved: <CheckCircle2 size={14} className="text-emerald-400" />,
    proposal_rejected: <XCircle size={14} className="text-red-400" />,
    proposal_created: <FileText size={14} className="text-blue-400" />,
    session_started: <Zap size={14} className="text-yellow-400" />,
    session_ended: <Clock size={14} className="text-slate-400" />,
    sentinel_alert: <AlertTriangle size={14} className="text-amber-400" />,
    adr_created: <FileText size={14} className="text-purple-400" />,
    adr_superseded: <FileText size={14} className="text-slate-500" />,
    decision_made: <CheckCircle2 size={14} className="text-cyan-400" />,
    cost_alert: <AlertTriangle size={14} className="text-red-400" />,
    memory_stored: <Brain size={14} className="text-indigo-400" />,
    skill_executed: <Zap size={14} className="text-teal-400" />,
};

const eventColors: Record<string, string> = {
    proposal_approved: "border-emerald-500/30",
    proposal_rejected: "border-red-500/30",
    proposal_created: "border-blue-500/30",
    session_started: "border-yellow-500/30",
    session_ended: "border-slate-500/30",
    sentinel_alert: "border-amber-500/30",
    adr_created: "border-purple-500/30",
    decision_made: "border-cyan-500/30",
    cost_alert: "border-red-500/30",
    memory_stored: "border-indigo-500/30",
    skill_executed: "border-teal-500/30",
};

export function RecentActivity() {
    return (
        <div className="glass-card-static p-6">
            <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                    <Activity size={18} className="text-blue-400" />
                    <h3 className="text-lg font-semibold text-white">Recent Activity</h3>
                </div>
                <span className="text-xs text-slate-500">Live</span>
            </div>

            <div className="space-y-1">
                {MOCK_RECENT_ACTIVITY.map((evt) => (
                    <div
                        key={evt.id}
                        className={`flex items-start gap-3 p-3 rounded-xl hover:bg-white/[0.02] transition-colors border-l-2 ${eventColors[evt.type] || "border-slate-500/30"}`}
                    >
                        <div className="mt-0.5">
                            {eventIcons[evt.type] || <Activity size={14} className="text-slate-500" />}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm text-slate-200 leading-snug">
                                {evt.title}
                            </p>
                            <p className="text-[11px] text-slate-500 mt-1">
                                {evt.actor} · {formatDistanceToNow(new Date(evt.timestamp), { addSuffix: true })}
                            </p>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
