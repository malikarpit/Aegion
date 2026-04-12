"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";

/* ══════════════════════════════════════════════════════════════
   TIME SLIDER — Chronos temporal navigation
   
   Drag through time → reconstruct past system state.
   Markers colored by governance tier. Keyboard ← → navigation.
   ══════════════════════════════════════════════════════════════ */

export interface TimeMarker {
  id: string;
  title: string;
  tier: string;
  timestamp: number;
}

interface TimeSliderProps {
  markers: TimeMarker[];
  selectedId?: string;
  onChange: (marker: TimeMarker) => void;
}

const TIER_COLORS: Record<string, string> = {
  T0: "var(--tier-0)",
  T1: "var(--tier-1)",
  T2: "var(--tier-2)",
  T3: "var(--tier-3)",
};

function formatAge(ts: number): string {
  const diff = Date.now() - ts;
  const days = Math.floor(diff / 86400000);
  if (days > 30) return `${Math.floor(days / 30)}mo ago`;
  if (days > 0) return `${days}d ago`;
  const hours = Math.floor(diff / 3600000);
  if (hours > 0) return `${hours}h ago`;
  return "now";
}

export function TimeSlider({ markers, selectedId, onChange }: TimeSliderProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const trackRef = useRef<HTMLDivElement>(null);

  const sorted = [...markers].sort((a, b) => a.timestamp - b.timestamp);
  const minTs = sorted[0]?.timestamp ?? Date.now();
  const maxTs = sorted[sorted.length - 1]?.timestamp ?? Date.now();
  const range = maxTs - minTs || 1;

  const selectedIdx = sorted.findIndex((m) => m.id === selectedId);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        const dir = e.key === "ArrowRight" ? 1 : -1;
        const newIdx = Math.max(0, Math.min(sorted.length - 1, selectedIdx + dir));
        onChange(sorted[newIdx]);
      } else if (e.key === "Home") {
        e.preventDefault();
        onChange(sorted[0]);
      } else if (e.key === "End") {
        e.preventDefault();
        onChange(sorted[sorted.length - 1]);
      }
    },
    [sorted, selectedIdx, onChange]
  );

  return (
    <div
      className="glass-l1 rounded-xl p-4"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      role="slider"
      aria-label="Time slider"
      aria-valuemin={minTs}
      aria-valuemax={maxTs}
      aria-valuenow={sorted[selectedIdx]?.timestamp}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="hud-label">TEMPORAL NAVIGATION</span>
        <button
          onClick={() => sorted.length && onChange(sorted[sorted.length - 1])}
          className="mono-data-sm px-2 py-0.5 rounded hover:bg-[var(--surface-hover)] transition-colors"
          style={{ color: "var(--accent-memory)" }}
        >
          → NOW
        </button>
      </div>

      {/* Track */}
      <div ref={trackRef} className="relative h-[48px] flex items-center">
        {/* Line */}
        <div
          className="absolute top-1/2 left-4 right-4 h-[2px] -translate-y-1/2"
          style={{ background: "var(--border-default)" }}
        />

        {/* Markers */}
        {sorted.map((marker, i) => {
          const pct = ((marker.timestamp - minTs) / range) * 100;
          const isSelected = marker.id === selectedId;
          const isHovered = hoveredIdx === i;
          const color = TIER_COLORS[marker.tier] || "var(--text-muted)";

          return (
            <button
              key={marker.id}
              onClick={() => onChange(marker)}
              onMouseEnter={() => setHoveredIdx(i)}
              onMouseLeave={() => setHoveredIdx(null)}
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 transition-transform"
              style={{
                left: `calc(16px + ${pct}% * (100% - 32px) / 100%)`,
                transform: `translate(-50%, -50%) scale(${isSelected ? 1.4 : isHovered ? 1.2 : 1})`,
                zIndex: isSelected ? 10 : isHovered ? 5 : 1,
              }}
            >
              <div
                className={`w-3 h-3 rounded-full border-2 transition-all ${isSelected ? "ring-2 ring-offset-1" : ""}`}
                style={{
                  background: isSelected ? color : `color-mix(in srgb, ${color} 40%, transparent)`,
                  borderColor: color,
                  boxShadow: isSelected ? `0 0 8px ${color}, 0 0 0 3px color-mix(in srgb, ${color} 30%, transparent)` : "none",
                }}
              />
              {/* Tooltip */}
              {(isHovered || isSelected) && (
                <div
                  className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 glass-l2 rounded-lg px-2.5 py-1.5 whitespace-nowrap z-20 animate-fade-in"
                  style={{ minWidth: 120 }}
                >
                  <p className="text-[12px] font-medium" style={{ color: "var(--text-primary)" }}>
                    {marker.title}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`tier-badge tier-badge-${marker.tier.toLowerCase()}`} style={{ fontSize: 9 }}>
                      {marker.tier}
                    </span>
                    <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                      {formatAge(marker.timestamp)}
                    </span>
                  </div>
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Labels */}
      <div className="flex items-center justify-between mt-1">
        <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
          {sorted[0] ? formatAge(sorted[0].timestamp) : "—"}
        </span>
        <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>Now</span>
      </div>
    </div>
  );
}
