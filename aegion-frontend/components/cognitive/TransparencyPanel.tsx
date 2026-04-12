"use client";

import React, { useState, useEffect } from "react";
import { ConfidenceEvolution } from "./ConfidenceEvolution";
import { TrustBadge } from "./TrustBadge";
import type { ConfidencePoint, TrustLevel, TrustValidation } from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   TRANSPARENCY PANEL — AI Attribution (L1/L2/L3)
   
   L1: "AI: GPT-4o + 2 models · $0.034 · 2.4s"
   L2: Full model breakdown, tokens, cost, consensus
   L3: Raw model responses, per-model breakdown
   ══════════════════════════════════════════════════════════════ */

interface ModelInfo {
  name: string;
  tokensIn: number;
  tokensOut: number;
  cost: number;
  latency: number; // seconds
}

interface TransparencyPanelProps {
  models: ModelInfo[];
  totalCost: number;
  totalLatency: number;
  confidenceEvolution: ConfidencePoint[];
  trust: TrustLevel;
  trustValidations?: TrustValidation[];
  consensusStrength?: number; // 0-1
  consensusLabel?: string;
  dissentingAgents?: string[];
  rawResponses?: Record<string, unknown>;
  defaultLevel?: 1 | 2 | 3;
}

export function TransparencyPanel({
  models,
  totalCost,
  totalLatency,
  confidenceEvolution,
  trust,
  trustValidations = [],
  consensusStrength,
  consensusLabel,
  dissentingAgents = [],
  rawResponses,
  defaultLevel = 1,
}: TransparencyPanelProps) {
  const [level, setLevel] = useState(defaultLevel);

  useEffect(() => {
    setLevel(defaultLevel);
  }, [defaultLevel]);

  const totalTokensIn = models.reduce((s, m) => s + m.tokensIn, 0);
  const totalTokensOut = models.reduce((s, m) => s + m.tokensOut, 0);
  const modelNames = models.map((m) => m.name).join(" · ");

  // ── L1: Single line summary ──
  if (level === 1) {
    return (
      <button
        onClick={() => setLevel(2)}
        className="flex items-center gap-2 w-full text-left py-1.5 hover:bg-[var(--surface-hover)] rounded-md px-2 transition-colors"
        aria-expanded="false"
        aria-label="Expand AI transparency details"
      >
        <span className="text-[12px]" style={{ color: "var(--text-ghost)" }}>▸</span>
        <span className="hud-label">AI</span>
        <span className="text-[12px]" style={{ color: "var(--text-muted)" }}>
          {modelNames} · ${totalCost.toFixed(3)} · {totalLatency.toFixed(1)}s
        </span>
      </button>
    );
  }

  // ── L2: Full breakdown ──
  return (
    <div className="glass-l1 p-3 rounded-lg" role="region" aria-label="AI transparency">
      <button
        onClick={() => setLevel(1)}
        className="flex items-center gap-2 mb-3 w-full text-left"
        aria-expanded="true"
      >
        <span className="text-[12px]" style={{ color: "var(--text-ghost)" }}>▾</span>
        <span className="hud-label">AI TRANSPARENCY</span>
      </button>

      <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[13px]">
        {/* Models */}
        <span className="hud-label self-center">MODELS</span>
        <span style={{ color: "var(--text-secondary)" }}>{modelNames}</span>

        {/* Tokens */}
        <span className="hud-label self-center">TOKENS</span>
        <span className="mono-data" style={{ color: "var(--text-secondary)" }}>
          {totalTokensIn.toLocaleString()} in / {totalTokensOut.toLocaleString()} out
        </span>

        {/* Cost */}
        <span className="hud-label self-center">COST</span>
        <span className="mono-data" style={{ color: "var(--accent-cost)" }}>
          ${totalCost.toFixed(3)}
        </span>

        {/* Latency */}
        <span className="hud-label self-center">LATENCY</span>
        <span className="mono-data" style={{ color: "var(--text-secondary)" }}>
          {totalLatency.toFixed(1)}s ({models.length > 1 ? "parallel" : "single"}, {models.length} agent{models.length > 1 ? "s" : ""})
        </span>

        {/* Consensus */}
        {consensusStrength !== undefined && (
          <>
            <span className="hud-label self-center">CONSENSUS</span>
            <span style={{ color: "var(--text-secondary)" }}>
              {consensusLabel ?? `${Math.round(consensusStrength * 100)}%`}
              {dissentingAgents.length > 0 && (
                <span className="ml-2 text-[12px]" style={{ color: "var(--status-warning)" }}>
                  ({dissentingAgents.length} dissent)
                </span>
              )}
            </span>
          </>
        )}

        {/* Confidence */}
        <span className="hud-label self-center">CONFIDENCE</span>
        <div>
          <ConfidenceEvolution points={confidenceEvolution} />
        </div>

        {/* Trust */}
        <span className="hud-label self-center">TRUST</span>
        <div>
          <TrustBadge level={trust} validatedBy={trustValidations} />
        </div>
      </div>

      {/* L3 Toggle */}
      {rawResponses && (
        <>
          {level === 3 ? (
            <div className="mt-3 pt-3 border-t" style={{ borderColor: "var(--border-subtle)" }}>
              <button
                onClick={() => setLevel(2)}
                className="hud-label mb-2 hover:opacity-70 transition-opacity"
              >
                ▾ RAW MODEL RESPONSES
              </button>

              {/* Per-model breakdown */}
              <div className="flex flex-col gap-2 mb-3">
                {models.map((m) => (
                  <div key={m.name} className="glass-static p-2 rounded-md">
                    <div className="flex items-center justify-between mb-1">
                      <span className="mono-data-sm font-medium">{m.name}</span>
                      <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                        {m.tokensIn}in/{m.tokensOut}out · ${m.cost.toFixed(4)} · {m.latency.toFixed(1)}s
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <pre
                className="text-[11px] p-3 rounded-md overflow-x-auto smooth-scroll"
                style={{
                  fontFamily: "var(--font-mono)",
                  background: "var(--surface-0)",
                  color: "var(--text-muted)",
                  maxHeight: "200px",
                }}
              >
                {JSON.stringify(rawResponses, null, 2)}
              </pre>
            </div>
          ) : (
            <button
              onClick={() => setLevel(3)}
              className="hud-label mt-3 hover:opacity-70 transition-opacity"
              style={{ color: "var(--text-ghost)" }}
            >
              ▸ Show raw responses
            </button>
          )}
        </>
      )}
    </div>
  );
}
