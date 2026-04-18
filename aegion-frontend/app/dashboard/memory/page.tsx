"use client";

import { useState, useCallback, useEffect } from "react";
import { Brain, Search, Trash2, Tag, Sparkles, Loader2, ArrowRight, MessageCircle } from "lucide-react";
import api from "@/lib/api";
import { TemporalMeta } from "@/components/cognitive/TemporalMeta";

/* ══════════════════════════════════════════════════════════════
   MEMORY PAGE — Episodic + Semantic memory browser with
   temporal metadata, search, CRUD operations.
   ══════════════════════════════════════════════════════════════ */

interface Memory {
  id: string;
  content: string;
  type: "episodic" | "semantic";
  tags: string[];
  createdAt: string;
  stability: "stable" | "settling" | "volatile";
}

export default function MemoryPage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | "episodic" | "semantic">("all");
  const [storeInput, setStoreInput] = useState("");
  const [storing, setStoring] = useState(false);

  useEffect(() => {
    async function fetchMemories() {
      try {
        const res = await api.get("/memory/search", { params: { query: "", limit: 50 } });
        const raw = res.data?.results || res.data || [];
        setMemories(raw.map((m: Record<string, unknown>) => ({
          id: m.id || String(Math.random()),
          content: (m.content || m.text || "") as string,
          type: ((m.type || "semantic") as string) === "episodic" ? "episodic" : "semantic",
          tags: (m.tags || (m.metadata as Record<string, unknown>)?.tags || []) as string[],
          createdAt: (m.created_at || m.createdAt || new Date().toISOString()) as string,
          stability: ((m.stability || "stable") as string) as Memory["stability"],
        })));
      } catch {
        setMemories([]);
      } finally {
        setLoading(false);
      }
    }
    fetchMemories();
  }, []);

  const handleStore = useCallback(async () => {
    if (!storeInput.trim()) return;
    setStoring(true);
    try {
      await api.post("/memory/store", { content: storeInput, metadata: { source: "manual" } });
      setStoreInput("");
      // Refresh
      const res = await api.get("/memory/search", { params: { query: "", limit: 50 } });
      const raw = res.data?.results || res.data || [];
      setMemories(raw.map((m: Record<string, unknown>) => ({
        id: m.id || String(Math.random()),
        content: (m.content || m.text || "") as string,
        type: "semantic" as const,
        tags: (m.tags || []) as string[],
        createdAt: (m.created_at || new Date().toISOString()) as string,
        stability: "volatile" as const,
      })));
    } catch { /* silent */ }
    finally { setStoring(false); }
  }, [storeInput]);

  const handleDelete = useCallback(async (id: string) => {
    try {
      await api.delete(`/memory/${id}`);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch {
      setMemories((prev) => prev.filter((m) => m.id !== id));
    }
  }, []);

  const filtered = memories
    .filter((m) => typeFilter === "all" || m.type === typeFilter)
    .filter((m) => !search || m.content.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-page-enter">
      <div>
        <h1 className="text-[22px] font-bold" style={{ color: "var(--text-primary)" }}>Memory</h1>
        <p className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
          Episodic & semantic memory — the system remembers everything
        </p>
      </div>

      {/* Store */}
      <div className="glass-l2 p-4 rounded-xl" style={{ borderLeft: "3px solid var(--accent-memory)" }}>
        <p className="hud-label mb-2">STORE NEW MEMORY</p>
        <div className="flex gap-2">
          <input
            value={storeInput}
            onChange={(e) => setStoreInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleStore()}
            placeholder="Enter a memory to store..."
            className="glass-input flex-1 px-3 py-2 text-[14px]"
          />
          <button
            onClick={handleStore}
            disabled={storing || !storeInput.trim()}
            className="px-4 py-2 rounded-lg text-[13px] font-medium disabled:opacity-30 transition-all"
            style={{ background: "var(--accent-memory)", color: "white" }}
          >
            {storing ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-ghost)" }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search memories..."
            className="glass-input w-full pl-10 pr-4 py-2.5 text-[14px]"
          />
        </div>
        <div className="flex gap-1">
          {(["all", "episodic", "semantic"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className="px-3 py-2 rounded-lg text-[12px] font-medium transition-all"
              style={{
                background: typeFilter === t ? "var(--surface-hover)" : "transparent",
                color: typeFilter === t ? "var(--text-primary)" : "var(--text-muted)",
                border: typeFilter === t ? "1px solid var(--border-default)" : "1px solid transparent",
              }}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Memory List */}
      <div className="space-y-2">
        {loading && (
          <div className="text-center py-12">
            <Loader2 size={24} className="animate-spin mx-auto" style={{ color: "var(--accent-memory)" }} />
          </div>
        )}

        {!loading && filtered.map((memory) => (
          <div key={memory.id} className="glass-l1 p-4 rounded-xl card-lift group">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3 min-w-0">
                <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0" style={{
                  background: memory.type === "episodic" ? "hsla(258,55%,58%,0.1)" : "hsla(217,85%,60%,0.08)",
                  border: "1px solid",
                  borderColor: memory.type === "episodic" ? "hsla(258,55%,58%,0.2)" : "hsla(217,85%,60%,0.15)",
                }}>
                  {memory.type === "episodic" ? (
                    <MessageCircle size={14} style={{ color: "var(--accent-memory)" }} />
                  ) : (
                    <Brain size={14} style={{ color: "var(--accent-reason)" }} />
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-[14px] leading-relaxed" style={{ color: "var(--text-primary)" }}>
                    {memory.content}
                  </p>
                  <div className="flex items-center gap-3 mt-2 flex-wrap">
                    <span className="hud-label px-1.5 py-[1px] rounded-[4px]" style={{
                      background: memory.type === "episodic" ? "hsla(258,55%,58%,0.08)" : "hsla(217,85%,60%,0.06)",
                      color: memory.type === "episodic" ? "var(--accent-memory)" : "var(--accent-reason)",
                    }}>
                      {memory.type.toUpperCase()}
                    </span>
                    {memory.tags.map((tag) => (
                      <span key={tag} className="flex items-center gap-0.5 mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                        <Tag size={9} /> {tag}
                      </span>
                    ))}
                    <TemporalMeta
                      createdAt={new Date(memory.createdAt).getTime()}
                      stability={memory.stability}
                      inline
                    />
                  </div>
                </div>
              </div>
              <button
                onClick={() => handleDelete(memory.id)}
                className="opacity-0 group-hover:opacity-50 hover:!opacity-100 transition-all p-1"
              >
                <Trash2 size={14} style={{ color: "var(--status-error)" }} />
              </button>
            </div>
          </div>
        ))}

        {!loading && filtered.length === 0 && (
          <div className="text-center py-16">
            <Brain size={32} className="mx-auto mb-3" style={{ color: "var(--text-ghost)", opacity: 0.3 }} />
            <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>No memories found</p>
          </div>
        )}
      </div>
    </div>
  );
}
