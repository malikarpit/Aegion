"use client";

import { useState, useMemo, useEffect } from "react";
import { formatDistanceToNow, format } from "date-fns";
import {
  Clock, Search, Filter, CheckCircle2, XCircle,
  AlertTriangle, FileText, Brain, Zap, Activity,
  ChevronDown, ChevronRight, Shield,
} from "lucide-react";
import api from "@/lib/api";
import { TimeSlider, type TimeMarker } from "@/components/chronos/TimeSlider";
import { StateReconstruction, type HistoricalState } from "@/components/chronos/StateReconstruction";

/* ══════════════════════════════════════════════════════════════
   TIMELINE PAGE — Chronos Temporal View
   
   Features:
   - TimeSlider for temporal navigation
   - StateReconstruction panel for past state
   - Vertical timeline with grouped events
   - Design tokens throughout
   ══════════════════════════════════════════════════════════════ */

interface TimelineEvent {
  id: string;
  type: string;
  title: string;
  actor: string;
  timestamp: string;
  entityType: string;
}

const EVENT_ICONS: Record<string, { icon: React.ElementType; color: string }> = {
  proposal_approved: { icon: CheckCircle2, color: "var(--status-success)" },
  proposal_rejected: { icon: XCircle, color: "var(--status-error)" },
  proposal_created: { icon: FileText, color: "var(--accent-reason)" },
  session_started: { icon: Zap, color: "var(--accent-cost)" },
  session_ended: { icon: Clock, color: "var(--text-muted)" },
  sentinel_alert: { icon: Shield, color: "var(--accent-risk)" },
  adr_created: { icon: FileText, color: "var(--accent-govern)" },
  adr_superseded: { icon: FileText, color: "var(--text-ghost)" },
  decision_made: { icon: CheckCircle2, color: "var(--accent-execute)" },
  cost_alert: { icon: AlertTriangle, color: "var(--accent-risk)" },
  memory_stored: { icon: Brain, color: "var(--accent-memory)" },
  skill_executed: { icon: Zap, color: "var(--accent-execute)" },
};

const ENTITY_TYPES = ["all", "proposal", "session", "alert", "decision", "adr", "memory", "skill", "cost"];

// Seed data for TimeSlider when no API data
const SEED_MARKERS: TimeMarker[] = [
  { id: "d-34", title: "Migrate to PostgreSQL", tier: "T1", timestamp: Date.now() - 30 * 86400000 },
  { id: "d-38", title: "Add Connection Pooling", tier: "T0", timestamp: Date.now() - 18 * 86400000 },
  { id: "d-40", title: "Add Rate Limiting", tier: "T2", timestamp: Date.now() - 8 * 86400000 },
  { id: "d-42", title: "Use Redis for Session Caching", tier: "T1", timestamp: Date.now() - 2 * 86400000 },
  { id: "d-43", title: "Migrate Auth to JWT + RBAC", tier: "T3", timestamp: Date.now() - 1 * 86400000 },
];

const SEED_STATES: Record<string, HistoricalState> = {
  "d-34": {
    timestamp: Date.now() - 30 * 86400000,
    decisions: [
      { id: "d-34", title: "Migrate to PostgreSQL", tier: "T1", stability: "stable" },
    ],
    riskScore: 0.18,
    riskLevel: "Low",
    governance: "Normal",
    session: { name: "DB Migration Review", status: "closed" },
    diffVsNow: { newDecisions: 9, riskChange: 0.16, superseded: 2, newMemories: 23 },
  },
  "d-42": {
    timestamp: Date.now() - 2 * 86400000,
    decisions: [
      { id: "d-34", title: "Migrate to PostgreSQL", tier: "T1", stability: "stable" },
      { id: "d-38", title: "Add Connection Pooling", tier: "T0", stability: "stable" },
      { id: "d-40", title: "Add Rate Limiting", tier: "T2", stability: "settling" },
      { id: "d-42", title: "Use Redis for Session Caching", tier: "T1", stability: "settling" },
    ],
    riskScore: 0.28,
    riskLevel: "Low",
    governance: "Normal",
    session: { name: "API Performance Review", status: "closed" },
    diffVsNow: { newDecisions: 1, riskChange: 0.06, superseded: 0, newMemories: 6 },
  },
};

export default function TimelinePage() {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selectedMarker, setSelectedMarker] = useState<TimeMarker | null>(null);

  useEffect(() => {
    async function fetchTimeline() {
      try {
        const res = await api.get("/timeline/events", { params: { limit: 100 } });
        const raw = res.data?.events || res.data || [];
        setEvents(
          raw.map((e: Record<string, string>) => ({
            id: e.id || e.event_id || String(Math.random()),
            type: e.event_type || "decision_made",
            title: e.title || e.event_type || "Event",
            actor: e.actor || e.actor_id || "system",
            timestamp: e.created_at || e.timestamp || new Date().toISOString(),
            entityType: e.entity_type || e.event_type?.split("_")[0] || "decision",
          }))
        );
      } catch {
        setEvents([]);
      } finally {
        setLoading(false);
      }
    }
    fetchTimeline();
  }, []);

  const filtered = useMemo(() => {
    return events
      .filter((e) => typeFilter === "all" || e.entityType === typeFilter)
      .filter((e) => !search || e.title.toLowerCase().includes(search.toLowerCase()));
  }, [events, search, typeFilter]);

  const grouped = useMemo(() => {
    const groups: Record<string, typeof filtered> = {};
    filtered.forEach((evt) => {
      const day = format(new Date(evt.timestamp), "MMMM d, yyyy");
      if (!groups[day]) groups[day] = [];
      groups[day].push(evt);
    });
    return groups;
  }, [filtered]);

  const historicalState = selectedMarker ? SEED_STATES[selectedMarker.id] || null : null;

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-page-enter">
      {/* Header */}
      <div>
        <h1 className="text-[22px] font-bold" style={{ color: "var(--text-primary)" }}>Timeline</h1>
        <p className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
          Chronos — Temporal event log with state reconstruction
        </p>
      </div>

      {/* Time Slider */}
      <TimeSlider
        markers={SEED_MARKERS}
        selectedId={selectedMarker?.id}
        onChange={(m) => setSelectedMarker(m)}
      />

      <div className="flex gap-6">
        {/* Left: Timeline */}
        <div className="flex-1 space-y-4">
          {/* Filters */}
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-ghost)" }} />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search events..."
                className="glass-input w-full pl-10 pr-4 py-2.5 text-[14px]"
              />
            </div>
            <div className="relative">
              <Filter size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-ghost)" }} />
              <select
                title="Filter by event type"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="glass-input pl-9 pr-8 py-2.5 text-[14px] appearance-none cursor-pointer min-w-[160px]"
              >
                {ENTITY_TYPES.map((t) => (
                  <option key={t} value={t} style={{ background: "var(--surface-2)" }}>
                    {t === "all" ? "All Types" : t.charAt(0).toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Event list */}
          <div className="space-y-6">
            {Object.entries(grouped).map(([day, dayEvents]) => (
              <div key={day}>
                <div className="sticky top-0 z-10 py-2 mb-2" style={{ background: "hsla(222,15%,5%,0.8)", backdropFilter: "blur(8px)" }}>
                  <h2 className="hud-label">{day}</h2>
                </div>

                <div className="space-y-1 relative">
                  <div className="absolute left-[19px] top-2 bottom-2 w-px" style={{ background: "var(--border-subtle)" }} />

                  {dayEvents.map((evt) => {
                    const isExpanded = expandedId === evt.id;
                    const evtConfig = EVENT_ICONS[evt.type] || { icon: Activity, color: "var(--text-muted)" };
                    const Icon = evtConfig.icon;

                    return (
                      <div
                        key={evt.id}
                        onClick={() => setExpandedId(isExpanded ? null : evt.id)}
                        className="relative flex gap-4 p-3 pl-0 rounded-xl cursor-pointer group card-lift"
                      >
                        <div
                          className="relative z-10 flex items-center justify-center w-10 h-10 rounded-full shrink-0 transition-colors"
                          style={{
                            background: "var(--surface-2)",
                            border: "1px solid var(--border-default)",
                          }}
                        >
                          <Icon size={14} style={{ color: evtConfig.color }} />
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-4">
                            <p className="text-[14px] leading-snug" style={{ color: "var(--text-primary)" }}>
                              {evt.title}
                            </p>
                            <div className="flex items-center gap-2 shrink-0">
                              <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                                {format(new Date(evt.timestamp), "HH:mm")}
                              </span>
                              {isExpanded ? (
                                <ChevronDown size={14} style={{ color: "var(--text-ghost)" }} />
                              ) : (
                                <ChevronRight size={14} style={{ color: "var(--text-ghost)" }} />
                              )}
                            </div>
                          </div>

                          <div className="flex items-center gap-3 mt-1">
                            <span
                              className="hud-label px-2 py-[1px] rounded-[4px] capitalize"
                              style={{ background: "var(--surface-3)", color: "var(--text-muted)" }}
                            >
                              {evt.entityType}
                            </span>
                            <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                              by {evt.actor}
                            </span>
                            <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                              {formatDistanceToNow(new Date(evt.timestamp), { addSuffix: true })}
                            </span>
                          </div>

                          {isExpanded && (
                            <div
                              className="mt-3 p-3 rounded-lg glass-l1 text-[12px] space-y-1 animate-slide-down"
                            >
                              <p>
                                <span className="hud-label">Event ID:</span>{" "}
                                <code className="mono-data-sm" style={{ color: "var(--text-primary)" }}>{evt.id}</code>
                              </p>
                              <p>
                                <span className="hud-label">Type:</span>{" "}
                                <code className="mono-data-sm" style={{ color: "var(--text-primary)" }}>{evt.type}</code>
                              </p>
                              <p>
                                <span className="hud-label">Timestamp:</span>{" "}
                                <code className="mono-data-sm" style={{ color: "var(--text-primary)" }}>{evt.timestamp}</code>
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
              <div className="text-center py-16">
                <Clock size={32} className="mx-auto mb-3" style={{ color: "var(--text-ghost)", opacity: 0.3 }} />
                <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>No events match your filters</p>
              </div>
            )}
          </div>
        </div>

        {/* Right: State Reconstruction */}
        {selectedMarker && (
          <div className="w-[340px] shrink-0">
            <StateReconstruction state={historicalState} />
          </div>
        )}
      </div>
    </div>
  );
}
