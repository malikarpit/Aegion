"use client";

import { useState, useEffect } from "react";
import { FileText, Plus, Search, Loader2, ChevronRight } from "lucide-react";
import api from "@/lib/api";

/* ══════════════════════════════════════════════════════════════
   ADRs PAGE — Architecture Decision Records
   ══════════════════════════════════════════════════════════════ */

interface ADR {
  id: string;
  title: string;
  status: "proposed" | "accepted" | "deprecated" | "superseded";
  date: string;
  context: string;
}

const STATUS_COLORS: Record<string, string> = {
  proposed: "var(--status-warning)",
  accepted: "var(--status-success)",
  deprecated: "var(--text-ghost)",
  superseded: "var(--accent-memory)",
};

export default function ADRsPage() {
  const [adrs, setAdrs] = useState<ADR[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedAdr, setSelectedAdr] = useState<ADR | null>(null);

  useEffect(() => {
    async function fetchADRs() {
      try {
        const res = await api.get("/adrs");
        const raw = res.data?.adrs || res.data || [];
        setAdrs(raw.map((a: Record<string, unknown>) => ({
          id: (a.id || a.adr_id) as string,
          title: (a.title || "Untitled") as string,
          status: (a.status || "proposed") as ADR["status"],
          date: (a.date || a.created_at || new Date().toISOString()) as string,
          context: (a.context || a.description || "") as string,
        })));
      } catch {
        setAdrs([
          { id: "ADR-001", title: "Use PostgreSQL for primary database", status: "accepted", date: "2026-03-15", context: "Need a robust relational database for complex queries and ACID compliance." },
          { id: "ADR-002", title: "Adopt Redis for session caching", status: "accepted", date: "2026-04-10", context: "In-memory caching needed for session state management to reduce latency." },
          { id: "ADR-003", title: "JWT + RBAC for authentication", status: "proposed", date: "2026-04-19", context: "Current auth system needs to support role-based access across services." },
          { id: "ADR-004", title: "Use in-memory cache", status: "superseded", date: "2026-02-20", context: "Original caching approach before Redis decision." },
        ]);
      } finally {
        setLoading(false);
      }
    }
    fetchADRs();
  }, []);

  const filtered = adrs.filter((a) =>
    !search || a.title.toLowerCase().includes(search.toLowerCase()) || a.id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-page-enter">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold" style={{ color: "var(--text-primary)" }}>Architecture Decision Records</h1>
          <p className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
            Documented architectural decisions with status tracking
          </p>
        </div>
        <button
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-all"
          style={{ background: "var(--accent-reason)", color: "white" }}
        >
          <Plus size={14} /> New ADR
        </button>
      </div>

      <div className="relative max-w-md">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-ghost)" }} />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search ADRs..." className="glass-input w-full pl-10 pr-4 py-2.5 text-[14px]" />
      </div>

      {loading ? (
        <div className="text-center py-12"><Loader2 size={24} className="animate-spin mx-auto" style={{ color: "var(--accent-reason)" }} /></div>
      ) : (
        <div className="space-y-2">
          {filtered.map((adr) => (
            <button
              key={adr.id}
              onClick={() => setSelectedAdr(selectedAdr?.id === adr.id ? null : adr)}
              className="w-full glass-l1 p-4 rounded-xl text-left card-lift"
              style={{ borderLeft: `3px solid ${STATUS_COLORS[adr.status]}` }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 min-w-0">
                  <FileText size={16} style={{ color: STATUS_COLORS[adr.status] }} />
                  <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>{adr.id}</span>
                  <span className="text-[14px] font-medium truncate" style={{ color: "var(--text-primary)" }}>{adr.title}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="hud-label px-1.5 py-[1px] rounded-[4px]" style={{
                    background: `color-mix(in srgb, ${STATUS_COLORS[adr.status]} 10%, transparent)`,
                    color: STATUS_COLORS[adr.status],
                  }}>
                    {adr.status.toUpperCase()}
                  </span>
                  <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>{adr.date}</span>
                  <ChevronRight size={14} style={{ color: "var(--text-ghost)" }} />
                </div>
              </div>
              {selectedAdr?.id === adr.id && (
                <div className="mt-3 pt-3 animate-slide-down" style={{ borderTop: "0.5px solid var(--border-subtle)" }}>
                  <p className="hud-label mb-1">CONTEXT</p>
                  <p className="text-[13px] leading-relaxed" style={{ color: "var(--text-secondary)" }}>{adr.context}</p>
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
