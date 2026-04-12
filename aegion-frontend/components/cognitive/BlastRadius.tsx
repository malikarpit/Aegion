"use client";

import React, { useState } from "react";
import type { GovernanceTier } from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   BLAST RADIUS — SVG Concentric Impact Diagram
   
   Inner: Directly affected files
   Middle: Affected services  
   Outer: Downstream consumers
   Ring opacity proportional to item count.
   ══════════════════════════════════════════════════════════════ */

interface BlastRadiusProps {
  tier: GovernanceTier;
  directFiles?: string[];
  services?: string[];
  downstream?: string[];
  size?: number; // px, default 160
}

const RING_CONFIG = [
  { label: "Files", radiusFactor: 0.32, key: "directFiles" as const },
  { label: "Services", radiusFactor: 0.52, key: "services" as const },
  { label: "Downstream", radiusFactor: 0.72, key: "downstream" as const },
];

const TIER_COLORS: Record<GovernanceTier, string> = {
  T0: "var(--tier-0)",
  T1: "var(--tier-1)",
  T2: "var(--tier-2)",
  T3: "var(--tier-3)",
};

export function BlastRadius({
  tier,
  directFiles = [],
  services = [],
  downstream = [],
  size = 160,
}: BlastRadiusProps) {
  const [hoveredRing, setHoveredRing] = useState<string | null>(null);
  const center = size / 2;
  const color = TIER_COLORS[tier];

  const rings = [
    { ...RING_CONFIG[0], items: directFiles },
    { ...RING_CONFIG[1], items: services },
    { ...RING_CONFIG[2], items: downstream },
  ];

  const totalCount = directFiles.length + services.length + downstream.length;

  if (totalCount === 0) {
    return (
      <div
        className="flex items-center justify-center text-[12px]"
        style={{ color: "var(--text-ghost)", width: size, height: size }}
      >
        No impact data
      </div>
    );
  }

  return (
    <div className="relative inline-block" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Rings from outer to inner */}
        {[...rings].reverse().map((ring) => {
          const radius = center * ring.radiusFactor;
          const opacity = ring.items.length > 0
            ? Math.min(0.15 + ring.items.length * 0.05, 0.4)
            : 0.03;

          return (
            <g
              key={ring.key}
              onMouseEnter={() => setHoveredRing(ring.key)}
              onMouseLeave={() => setHoveredRing(null)}
              style={{ cursor: ring.items.length > 0 ? "pointer" : "default" }}
            >
              <circle
                cx={center}
                cy={center}
                r={radius}
                fill={`color-mix(in srgb, ${color} ${Math.round(opacity * 100)}%, transparent)`}
                stroke={color}
                strokeWidth={hoveredRing === ring.key ? 1.5 : 0.5}
                strokeOpacity={ring.items.length > 0 ? 0.4 : 0.1}
              />
              {/* Count label */}
              {ring.items.length > 0 && (
                <text
                  x={center}
                  y={center - radius + 12}
                  textAnchor="middle"
                  fill={color}
                  fontSize={9}
                  fontFamily="var(--font-mono)"
                  fontWeight={500}
                  opacity={0.7}
                >
                  {ring.items.length}
                </text>
              )}
            </g>
          );
        })}

        {/* Center dot */}
        <circle cx={center} cy={center} r={4} fill={color} />
      </svg>

      {/* Tooltip */}
      {hoveredRing && (
        <div
          className="absolute left-full ml-2 top-0 glass-l3 p-2.5 min-w-[160px] z-50 animate-fade-in"
          role="tooltip"
        >
          <p className="hud-label mb-1.5">
            {rings.find((r) => r.key === hoveredRing)?.label ?? ""}
          </p>
          <div className="flex flex-col gap-0.5">
            {(rings.find((r) => r.key === hoveredRing)?.items ?? []).map((item, i) => (
              <span
                key={i}
                className="mono-data-sm truncate"
                style={{ color: "var(--text-secondary)" }}
              >
                {item}
              </span>
            ))}
            {(rings.find((r) => r.key === hoveredRing)?.items.length ?? 0) === 0 && (
              <span className="text-[11px]" style={{ color: "var(--text-ghost)" }}>
                None
              </span>
            )}
          </div>
        </div>
      )}

      {/* Total count */}
      <div
        className="absolute bottom-0 left-1/2 -translate-x-1/2 text-center"
        style={{ marginBottom: -4 }}
      >
        <span className="mono-data-sm" style={{ color }}>
          {totalCount} affected
        </span>
      </div>
    </div>
  );
}
