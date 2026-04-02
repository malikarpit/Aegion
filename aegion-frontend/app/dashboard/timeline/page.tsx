"use client";

import { useState, useMemo } from "react";
import { formatDistanceToNow, format } from "date-fns";
import { Clock, Search, Filter, CheckCircle2, XCircle, AlertTriangle, FileText, Brain, Zap, Activity, ChevronDown, ChevronRight } from "lucide-react";
import { MOCK_TIMELINE_EVENTS } from "@/lib/mock-data";

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

const entityTypes = ["all", "proposal", "session", "alert", "decision", "adr", "memory", "skill", "cost"];

export default function TimelinePage() {
    const [search, setSearch] = useState("");
    const [typeFilter, setTypeFilter] = useState("all");
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const filtered = useMemo(() => {
        return MOCK_TIMELINE_EVENTS
            .filter((e) => typeFilter === "all" || e.entityType === typeFilter)
            .filter((e) => !search || e.title.toLowerCase().includes(search.toLowerCase()));
    }, [search, typeFilter]);

    // Group by day
    const grouped = useMemo(() => {
        const groups: Record<string, typeof filtered> = {};
        filtered.forEach((evt) => {
            const day = format(new Date(evt.timestamp), "MMMM d, yyyy");
            if (!groups[day]) groups[day] = [];
            groups[day].push(evt);
        });
        return groups;
    }, [filtered]);

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div>
                <h1 className="text-2xl font-bold text-white">Timeline</h1>
                <p className="text-sm text-slate-500 mt-1">
                    Chronological event log across all systems
                </p>
            </div>

            {/* Filters */}
            <div className="flex flex-col sm:flex-row gap-3">
                <div className="relative flex-1">
                    <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search events..."
                        className="glass-input w-full pl-10 pr-4 py-2.5 text-sm"
                    />
                </div>
                <div className="relative">
                    <Filter size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                    <select
                        value={typeFilter}
                        onChange={(e) => setTypeFilter(e.target.value)}
                        className="glass-input pl-9 pr-8 py-2.5 text-sm appearance-none cursor-pointer min-w-[160px]"
                    >
                        {entityTypes.map((t) => (
                            <option key={t} value={t} className="bg-[#111118]">
                                {t === "all" ? "All Types" : t.charAt(0).toUpperCase() + t.slice(1)}
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Timeline */}
            <div className="space-y-8">
                {Object.entries(grouped).map(([day, events]) => (
                    <div key={day}>
                        <div className="sticky top-0 z-10 bg-black/80 backdrop-blur-sm py-2 mb-3">
                            <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                {day}
                            </h2>
                        </div>

                        <div className="space-y-1 relative">
                            {/* Vertical timeline line */}
                            <div className="absolute left-[19px] top-2 bottom-2 w-px bg-white/5" />

                            {events.map((evt) => {
                                const isExpanded = expandedId === evt.id;
                                return (
                                    <div
                                        key={evt.id}
                                        onClick={() => setExpandedId(isExpanded ? null : evt.id)}
                                        className="relative flex gap-4 p-3 pl-0 rounded-xl hover:bg-white/[0.02] transition-colors cursor-pointer group"
                                    >
                                        {/* Icon dot */}
                                        <div className="relative z-10 flex items-center justify-center w-10 h-10 rounded-full bg-[#111118] border border-white/10 group-hover:border-white/20 transition-colors shrink-0">
                                            {eventIcons[evt.type] || <Activity size={14} className="text-slate-500" />}
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-start justify-between gap-4">
                                                <p className="text-sm text-slate-200 leading-snug">
                                                    {evt.title}
                                                </p>
                                                <div className="flex items-center gap-2 shrink-0">
                                                    <span className="text-[11px] text-slate-500">
                                                        {format(new Date(evt.timestamp), "HH:mm")}
                                                    </span>
                                                    {isExpanded ? (
                                                        <ChevronDown size={14} className="text-slate-500" />
                                                    ) : (
                                                        <ChevronRight size={14} className="text-slate-600" />
                                                    )}
                                                </div>
                                            </div>

                                            <div className="flex items-center gap-3 mt-1">
                                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-slate-500 capitalize">
                                                    {evt.entityType}
                                                </span>
                                                <span className="text-[11px] text-slate-600">
                                                    by {evt.actor}
                                                </span>
                                                <span className="text-[11px] text-slate-600">
                                                    {formatDistanceToNow(new Date(evt.timestamp), { addSuffix: true })}
                                                </span>
                                            </div>

                                            {/* Expanded detail */}
                                            {isExpanded && (
                                                <div className="mt-3 p-3 rounded-lg bg-white/[0.02] border border-white/5 text-xs text-slate-400 animate-slide-down">
                                                    <p className="mb-2">
                                                        <span className="text-slate-500">Event ID:</span>{" "}
                                                        <code className="text-slate-300">{evt.id}</code>
                                                    </p>
                                                    <p className="mb-2">
                                                        <span className="text-slate-500">Type:</span>{" "}
                                                        <code className="text-slate-300">{evt.type}</code>
                                                    </p>
                                                    <p>
                                                        <span className="text-slate-500">Timestamp:</span>{" "}
                                                        <code className="text-slate-300">{evt.timestamp}</code>
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                ))}

                {filtered.length === 0 && (
                    <div className="text-center py-16 text-slate-500">
                        <Clock size={32} className="mx-auto mb-3 opacity-30" />
                        <p className="text-sm">No events match your filters</p>
                    </div>
                )}
            </div>
        </div>
    );
}
