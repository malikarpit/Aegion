"use client";

import React, { useState, useEffect } from "react";
import { TemporalMeta } from "./TemporalMeta";

/* ══════════════════════════════════════════════════════════════
   WHY PANEL — The Killer Differentiator
   
   On every decision: show WHY it exists, WHERE it came from,
   WHAT it superseded, WHAT memories were referenced.
   
   Three disclosure levels:
   L1 (collapsed, 1 line): origin + builds-on summary
   L2 (expanded): full provenance tree
   L3 (deep trace): raw JSON provenance chain
   ══════════════════════════════════════════════════════════════ */

interface ProvenanceOrigin {
  sessionId: string;
  sessionName: string;
  query?: string;
}

interface ProvenanceLink {
  id: string;
  title: string;
  tier: string;
  type: "builds_on" | "supersedes" | "triggered_by" | "references";
  createdAt: number;
  stability?: "stable" | "settling" | "volatile";
}

interface WhyPanelProps {
  decisionId: string;
  origin?: ProvenanceOrigin;
  lineage?: ProvenanceLink[];
  supersedes?: ProvenanceLink[];
  triggers?: ProvenanceLink[];
  memories?: ProvenanceLink[];
  rawProvenance?: Record<string, unknown>;
  defaultLevel?: 1 | 2 | 3;
  compact?: boolean;
}

export function WhyPanel({
  origin,
  lineage = [],
  supersedes = [],
  triggers = [],
  memories = [],
  rawProvenance,
  defaultLevel = 1,
  compact = false,
}: WhyPanelProps) {
  const [level, setLevel] = useState(defaultLevel);

  // Sync with external defaultLevel changes (e.g., mode switching)
  useEffect(() => {
    setLevel(defaultLevel);
  }, [defaultLevel]);

  const buildsOnSummary = lineage
    .slice(0, 2)
    .map((l) => `#${l.id}`)
    .join(", ");

  // ── L1: Collapsed single line ──
  if (level === 1) {
    return (
      <button
        onClick={() => setLevel(2)}
        className="flex items-center gap-2 w-full text-left py-1.5 hover:bg-[var(--surface-hover)] rounded-md px-2 transition-colors"
        aria-expanded="false"
        aria-label="Expand provenance details"
      >
        <span className="text-[12px]" style={{ color: "var(--text-ghost)" }}>▸</span>
        <span className="hud-label">WHY</span>
        <span className="text-[12px]" style={{ color: "var(--text-muted)" }}>
          {origin
            ? `Originated in ${origin.sessionName}`
            : "—"}
          {buildsOnSummary && `, builds on ${buildsOnSummary}`}
        </span>
      </button>
    );
  }

  // ── L2: Full provenance tree ──
  return (
    <div className="glass-l1 p-3 rounded-lg" role="region" aria-label="Decision provenance">
      {/* Header */}
      <button
        onClick={() => setLevel(1)}
        className="flex items-center gap-2 mb-3 w-full text-left"
        aria-expanded="true"
      >
        <span className="text-[12px]" style={{ color: "var(--text-ghost)" }}>▾</span>
        <span className="hud-label">WHY THIS EXISTS</span>
      </button>

      {/* Originated In */}
      {origin && (
        <div className="mb-3">
          <p className="hud-label mb-1">ORIGINATED IN</p>
          <div className="tree-line">
            <p className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
              Session &quot;{origin.sessionName}&quot;
            </p>
            {origin.query && (
              <p
                className="text-[12px] mt-0.5"
                style={{ color: "var(--text-muted)", fontStyle: "italic" }}
              >
                Query: &quot;{origin.query}&quot;
              </p>
            )}
          </div>
        </div>
      )}

      {/* Builds On */}
      {lineage.length > 0 && (
        <div className="mb-3">
          <p className="hud-label mb-1">BUILDS ON</p>
          <div className="tree-line">
            {lineage.map((l, i) => (
              <div
                key={l.id}
                className={`flex items-center gap-2 py-0.5 ${
                  i === lineage.length - 1 ? "tree-branch-last" : "tree-branch"
                }`}
              >
                <span className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
                  Decision #{l.id}: &quot;{l.title}&quot;
                </span>
                <span className="tier-badge text-[9px]" style={{
                  background: `var(--tier-${l.tier.replace("T", "")}-bg, var(--tier-0-bg))`,
                  color: `var(--tier-${l.tier.replace("T", "")}, var(--tier-0))`,
                }}>
                  {l.tier}
                </span>
                <TemporalMeta
                  createdAt={l.createdAt}
                  stability={l.stability}
                  inline
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Triggered By */}
      {triggers.length > 0 && (
        <div className="mb-3">
          <p className="hud-label mb-1">TRIGGERED BY</p>
          <div className="tree-line">
            {triggers.map((t, i) => (
              <div
                key={t.id}
                className={`flex items-center gap-2 py-0.5 ${
                  i === triggers.length - 1 ? "tree-branch-last" : "tree-branch"
                }`}
              >
                <span className="text-[12px]" style={{ color: "var(--accent-risk)" }}>
                  🛡
                </span>
                <span className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
                  {t.title}
                </span>
                <TemporalMeta createdAt={t.createdAt} inline />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Supersedes */}
      {supersedes.length > 0 && (
        <div className="mb-3">
          <p className="hud-label mb-1">SUPERSEDES</p>
          <div className="tree-line">
            {supersedes.map((s, i) => (
              <div
                key={s.id}
                className={`flex items-center gap-2 py-0.5 ${
                  i === supersedes.length - 1 ? "tree-branch-last" : "tree-branch"
                }`}
              >
                <span className="text-[13px] line-through" style={{ color: "var(--text-muted)" }}>
                  Decision #{s.id}: &quot;{s.title}&quot;
                </span>
                <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                  (deprecated)
                </span>
                <TemporalMeta createdAt={s.createdAt} inline />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Referenced Memories */}
      {memories.length > 0 && (
        <div className="mb-3">
          <p className="hud-label mb-1">REFERENCED MEMORIES</p>
          <div className="tree-line">
            {memories.map((m, i) => (
              <div
                key={m.id}
                className={`flex items-center gap-2 py-0.5 ${
                  i === memories.length - 1 ? "tree-branch-last" : "tree-branch"
                }`}
              >
                <span className="text-[12px]" style={{ color: "var(--accent-memory)" }}>
                  📚
                </span>
                <span className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
                  Memory #{m.id}: &quot;{m.title}&quot;
                </span>
                <TemporalMeta
                  createdAt={m.createdAt}
                  stability={m.stability}
                  inline
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* L3 toggle */}
      {!compact && rawProvenance && (
        <>
          {level === 3 ? (
            <div className="mt-3 pt-3 border-t" style={{ borderColor: "var(--border-subtle)" }}>
              <button
                onClick={() => setLevel(2)}
                className="hud-label mb-2 hover:opacity-70 transition-opacity"
              >
                ▾ RAW PROVENANCE CHAIN
              </button>
              <pre
                className="text-[11px] p-3 rounded-md overflow-x-auto smooth-scroll"
                style={{
                  fontFamily: "var(--font-mono)",
                  background: "var(--surface-0)",
                  color: "var(--text-muted)",
                  maxHeight: "200px",
                }}
              >
                {JSON.stringify(rawProvenance, null, 2)}
              </pre>
            </div>
          ) : (
            <button
              onClick={() => setLevel(3)}
              className="hud-label mt-2 hover:opacity-70 transition-opacity"
              style={{ color: "var(--text-ghost)" }}
            >
              ▸ Show raw provenance
            </button>
          )}
        </>
      )}
    </div>
  );
}
