"use client";

import React, { useMemo, useState } from "react";
import type { ConfidencePoint } from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   CONFIDENCE EVOLUTION — Inline Sparkline
   
   Shows how confidence changed across agent contributions.
   Max 5 data points. Hover for attribution tooltip.
   ══════════════════════════════════════════════════════════════ */

interface ConfidenceEvolutionProps {
  points: ConfidencePoint[];
  size?: { width: number; height: number };
}

const AGENT_LABELS: Record<string, string> = {
  architecture: "Architect",
  security: "Security",
  performance: "Performance",
  ux: "UX",
  redteam: "Red Team",
  general: "General",
};

function getConfidenceColor(value: number): string {
  if (value > 0.7) return "var(--status-success)";
  if (value > 0.4) return "var(--status-warning)";
  return "var(--status-error)";
}

export function ConfidenceEvolution({
  points,
  size = { width: 60, height: 16 },
}: ConfidenceEvolutionProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  const displayPoints = useMemo(
    () => points.slice(-5), // cap at 5
    [points]
  );

  const currentValue = displayPoints[displayPoints.length - 1]?.value ?? 0;
  const initialValue = displayPoints[0]?.value ?? 0;
  const trend = currentValue > initialValue ? "↑" : currentValue < initialValue ? "↓" : "→";
  const color = getConfidenceColor(currentValue);

  // Build SVG path
  const pathData = useMemo(() => {
    if (displayPoints.length < 2) return "";
    const { width: w, height: h } = size;
    const padding = 2;
    const xStep = (w - padding * 2) / (displayPoints.length - 1);

    const pts = displayPoints.map((p, i) => ({
      x: padding + i * xStep,
      y: padding + (1 - p.value) * (h - padding * 2),
    }));

    return pts
      .map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`))
      .join(" ");
  }, [displayPoints, size]);

  if (displayPoints.length === 0) {
    return (
      <span className="mono-data" style={{ color: "var(--text-ghost)" }}>
        —
      </span>
    );
  }

  return (
    <div
      className="relative inline-flex items-center gap-1.5"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <span className="mono-data font-medium" style={{ color }}>
        {currentValue.toFixed(2)}
      </span>
      <span className="mono-data-sm" style={{ color }}>
        {trend}
      </span>

      {displayPoints.length >= 2 && (
        <svg
          width={size.width}
          height={size.height}
          viewBox={`0 0 ${size.width} ${size.height}`}
          className="ml-0.5"
          role="img"
          aria-label={`Confidence evolution: ${initialValue.toFixed(2)} to ${currentValue.toFixed(2)}`}
        >
          <path
            d={pathData}
            fill="none"
            stroke={color}
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{
              strokeDasharray: 1000,
              strokeDashoffset: 0,
              transition: "stroke-dashoffset 400ms linear",
            }}
          />
          {/* Current value dot */}
          <circle
            cx={displayPoints.length > 1 ? size.width - 2 : size.width / 2}
            cy={2 + (1 - currentValue) * (size.height - 4)}
            r={2}
            fill={color}
          />
        </svg>
      )}

      {/* Tooltip */}
      {showTooltip && displayPoints.length >= 2 && (
        <div
          className="absolute bottom-full left-0 mb-2 glass-l3 p-2.5 min-w-[200px] z-50 animate-fade-in"
          role="tooltip"
        >
          <p className="hud-label mb-1.5">Confidence Evolution</p>
          <div className="flex flex-col gap-1">
            {displayPoints.map((p, i) => {
              const delta = i > 0 ? p.value - displayPoints[i - 1].value : 0;
              return (
                <div key={i} className="flex items-center gap-2">
                  <span
                    className="mono-data-sm font-medium tabular-nums w-[36px]"
                    style={{ color: getConfidenceColor(p.value) }}
                  >
                    {p.value.toFixed(2)}
                  </span>
                  {i > 0 && (
                    <span
                      className="mono-data-sm"
                      style={{
                        color: delta >= 0 ? "var(--status-success)" : "var(--status-error)",
                      }}
                    >
                      {delta >= 0 ? "+" : ""}
                      {delta.toFixed(2)}
                    </span>
                  )}
                  <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                    {AGENT_LABELS[p.agentType] ?? p.agentType}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
