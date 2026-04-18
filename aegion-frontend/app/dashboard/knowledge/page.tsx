"use client";

import { useState, useCallback, useMemo } from "react";
import { Search, ZoomIn, ZoomOut, Maximize2, X, Network } from "lucide-react";
import { TemporalMeta } from "@/components/cognitive/TemporalMeta";

/* ══════════════════════════════════════════════════════════════
   KNOWLEDGE GRAPH — Interactive node visualization
   Cognitive treatment: each node shows temporal metadata,
   edges show relationship type. Design token colors.
   ══════════════════════════════════════════════════════════════ */

interface KnowledgeNode {
  id: string;
  label: string;
  type: "decision" | "memory" | "session" | "skill" | "agent";
  tier?: string;
  createdAt: number;
  stability: "stable" | "settling" | "volatile";
  connections: number;
}

const NODE_COLORS: Record<string, string> = {
  decision: "var(--accent-reason)",
  memory: "var(--accent-memory)",
  session: "var(--accent-execute)",
  skill: "var(--accent-govern)",
  agent: "var(--accent-cost)",
};

// Seed nodes
const SEED_NODES: KnowledgeNode[] = [
  { id: "d-42", label: "Use Redis for Session Caching", type: "decision", tier: "T1", createdAt: Date.now() - 2 * 86400000, stability: "settling", connections: 5 },
  { id: "d-40", label: "Add Rate Limiting to API Gateway", type: "decision", tier: "T2", createdAt: Date.now() - 8 * 86400000, stability: "settling", connections: 3 },
  { id: "d-34", label: "Migrate to PostgreSQL", type: "decision", tier: "T1", createdAt: Date.now() - 30 * 86400000, stability: "stable", connections: 7 },
  { id: "m-88", label: "Redis benchmark results", type: "memory", createdAt: Date.now() - 5 * 86400000, stability: "stable", connections: 2 },
  { id: "m-91", label: "Infrastructure cost analysis", type: "memory", createdAt: Date.now() - 10 * 86400000, stability: "volatile", connections: 4 },
  { id: "s-12", label: "API Performance Review", type: "session", createdAt: Date.now() - 3 * 86400000, stability: "stable", connections: 6 },
  { id: "sk-1", label: "Code Analysis", type: "skill", createdAt: Date.now() - 60 * 86400000, stability: "stable", connections: 12 },
  { id: "a-1", label: "Architecture Agent", type: "agent", createdAt: Date.now() - 90 * 86400000, stability: "stable", connections: 20 },
];

export default function KnowledgePage() {
  const [search, setSearch] = useState("");
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);
  const [zoom, setZoom] = useState(1);

  const filtered = useMemo(() =>
    SEED_NODES.filter((n) => !search || n.label.toLowerCase().includes(search.toLowerCase())),
    [search]
  );

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-page-enter">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold" style={{ color: "var(--text-primary)" }}>Knowledge Graph</h1>
          <p className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
            System knowledge topology — decisions, memories, sessions, skills
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setZoom((z) => Math.max(0.5, z - 0.1))} className="p-2 glass-l1 rounded-lg" title="Zoom out">
            <ZoomOut size={14} style={{ color: "var(--text-muted)" }} />
          </button>
          <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom((z) => Math.min(2, z + 0.1))} className="p-2 glass-l1 rounded-lg" title="Zoom in">
            <ZoomIn size={14} style={{ color: "var(--text-muted)" }} />
          </button>
          <button onClick={() => setZoom(1)} className="p-2 glass-l1 rounded-lg" title="Reset">
            <Maximize2 size={14} style={{ color: "var(--text-muted)" }} />
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative w-full max-w-md">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-ghost)" }} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search nodes..."
          className="glass-input w-full pl-10 pr-4 py-2.5 text-[14px]"
        />
      </div>

      <div className="flex gap-6">
        {/* Graph Area */}
        <div
          className="flex-1 glass-l1 rounded-xl p-6 min-h-[500px] relative overflow-hidden"
          style={{ transform: `scale(${zoom})`, transformOrigin: "top left" }}
        >
          {/* Node visualization (grid layout as placeholder for @xyflow/react) */}
          <div className="grid grid-cols-3 gap-4">
            {filtered.map((node) => {
              const color = NODE_COLORS[node.type] || "var(--text-muted)";
              const isSelected = selectedNode?.id === node.id;
              return (
                <button
                  key={node.id}
                  onClick={() => setSelectedNode(isSelected ? null : node)}
                  className="glass-l1 p-4 rounded-xl text-left transition-all card-lift"
                  style={{
                    borderLeft: `3px solid ${color}`,
                    outline: isSelected ? `2px solid ${color}` : "none",
                    outlineOffset: 2,
                  }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-3 h-3 rounded-full" style={{ background: color }} />
                    <span className="hud-label" style={{ color }}>{node.type.toUpperCase()}</span>
                    {node.tier && <span className={`tier-badge tier-badge-${node.tier.toLowerCase()}`}>{node.tier}</span>}
                  </div>
                  <p className="text-[13px] font-medium mb-2" style={{ color: "var(--text-primary)" }}>
                    {node.label}
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                      {node.connections} connections
                    </span>
                    <TemporalMeta createdAt={node.createdAt} stability={node.stability} inline />
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Detail Panel */}
        {selectedNode && (
          <div className="w-[300px] shrink-0 glass-l2 rounded-xl p-4 space-y-3 animate-slide-right">
            <div className="flex items-center justify-between">
              <span className="hud-label" style={{ color: NODE_COLORS[selectedNode.type] }}>
                {selectedNode.type.toUpperCase()} DETAIL
              </span>
              <button onClick={() => setSelectedNode(null)}>
                <X size={14} style={{ color: "var(--text-ghost)" }} />
              </button>
            </div>
            <h3 className="text-[16px] font-semibold" style={{ color: "var(--text-primary)" }}>
              {selectedNode.label}
            </h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="hud-label">ID</span>
                <span className="mono-data-sm" style={{ color: "var(--text-secondary)" }}>{selectedNode.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="hud-label">CONNECTIONS</span>
                <span className="mono-data-sm" style={{ color: "var(--text-primary)" }}>{selectedNode.connections}</span>
              </div>
              <div className="flex justify-between">
                <span className="hud-label">STABILITY</span>
                <span className="mono-data-sm" style={{
                  color: selectedNode.stability === "stable" ? "var(--status-success)" : selectedNode.stability === "settling" ? "var(--status-warning)" : "var(--status-error)",
                }}>{selectedNode.stability.toUpperCase()}</span>
              </div>
            </div>
            <TemporalMeta createdAt={selectedNode.createdAt} stability={selectedNode.stability} />
          </div>
        )}
      </div>
    </div>
  );
}
