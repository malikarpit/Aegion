"use client";

import React from "react";
import type { StabilityLevel } from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   TEMPORAL META — Chronos Omnipresence
   
   Every entity everywhere shows: age, stability, references, amendments.
   Used in: DecisionCard, proposal items, timeline, memory, WhyPanel, 
   knowledge graph, activity feed.
   ══════════════════════════════════════════════════════════════ */

interface TemporalMetaProps {
  createdAt: number;
  lastReferencedAt?: number;
  amendmentCount?: number;
  stability?: StabilityLevel;
  inline?: boolean; // true = single line, false = stacked
}

function formatAge(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m`;
  if (hours < 24) return `${hours}h`;
  if (days === 1) return "1 day";
  return `${days} days`;
}

function formatLastRef(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(hours / 24);

  if (hours < 1) return "ref'd just now";
  if (hours < 24) return `ref'd ${hours}h ago`;
  if (days === 1) return "ref'd 1 day ago";
  return `ref'd ${days}d ago`;
}

const STABILITY_CONFIG: Record<
  StabilityLevel,
  { label: string; color: string }
> = {
  stable:   { label: "STABLE",   color: "var(--status-success)" },
  settling: { label: "SETTLING", color: "var(--status-warning)" },
  volatile: { label: "VOLATILE", color: "var(--status-error)" },
};

export function TemporalMeta({
  createdAt,
  lastReferencedAt,
  amendmentCount = 0,
  stability = "stable",
  inline = true,
}: TemporalMetaProps) {
  const stabConfig = STABILITY_CONFIG[stability];

  const items = [
    <span key="age" className="mono-data-sm" style={{ color: "var(--text-muted)" }}>
      {formatAge(createdAt)}
    </span>,
    <span
      key="stability"
      className="mono-data-sm font-medium"
      style={{ color: stabConfig.color }}
    >
      {stabConfig.label}
    </span>,
  ];

  if (lastReferencedAt) {
    items.push(
      <span key="ref" className="mono-data-sm" style={{ color: "var(--text-muted)" }}>
        {formatLastRef(lastReferencedAt)}
      </span>
    );
  }

  if (amendmentCount > 0) {
    items.push(
      <span
        key="amend"
        className="mono-data-sm"
        style={{ color: amendmentCount > 2 ? "var(--status-error)" : "var(--text-muted)" }}
      >
        amended {amendmentCount}×
      </span>
    );
  }

  if (inline) {
    return (
      <div className="flex items-center gap-1.5 flex-wrap" aria-label="Temporal information">
        {items.map((item, i) => (
          <React.Fragment key={i}>
            {i > 0 && (
              <span className="text-[8px]" style={{ color: "var(--text-ghost)" }}>
                ·
              </span>
            )}
            {item}
          </React.Fragment>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0.5" aria-label="Temporal information">
      {items}
    </div>
  );
}
