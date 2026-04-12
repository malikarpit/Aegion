"use client";

import React, { useState } from "react";
import type { TrustLevel, TrustValidation } from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   TRUST BADGE — Historical Validation (Trust ≠ Confidence)
   
   Confidence = internal model belief
   Trust = "has this kind of decision worked before?"
   ══════════════════════════════════════════════════════════════ */

interface TrustBadgeProps {
  level: TrustLevel;
  validatedBy?: TrustValidation[];
}

const TRUST_CONFIG: Record<
  TrustLevel,
  { icon: string; label: string; colorVar: string }
> = {
  validated: { icon: "✓", label: "VALIDATED", colorVar: "--trust-validated" },
  moderate:  { icon: "◐", label: "MODERATE",  colorVar: "--trust-moderate" },
  novel:     { icon: "◇", label: "NOVEL",     colorVar: "--trust-novel" },
  unproven:  { icon: "?", label: "UNPROVEN",  colorVar: "--trust-unproven" },
};

export function TrustBadge({ level, validatedBy = [] }: TrustBadgeProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const config = TRUST_CONFIG[level];

  return (
    <div className="relative inline-flex">
      <span
        className="mono-data-sm font-medium px-1.5 py-[1px] rounded-[4px] cursor-default"
        style={{
          color: `var(${config.colorVar})`,
          background: `color-mix(in srgb, var(${config.colorVar}) 10%, transparent)`,
        }}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        role="status"
        aria-label={`Trust level: ${config.label}`}
      >
        {config.icon} {config.label}
      </span>

      {/* Tooltip */}
      {showTooltip && validatedBy.length > 0 && (
        <div
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 glass-l3 p-3 min-w-[240px] z-50 animate-fade-in"
          role="tooltip"
        >
          <p className="hud-label mb-2">Validated by</p>
          <div className="flex flex-col gap-1.5">
            {validatedBy.map((v) => (
              <div key={v.decisionId} className="flex items-center gap-2">
                <span
                  className="text-[10px]"
                  style={{
                    color:
                      v.outcome === "succeeded"
                        ? "var(--status-success)"
                        : "var(--status-warning)",
                  }}
                >
                  {v.outcome === "succeeded" ? "✓" : "◐"}
                </span>
                <span className="text-[12px] truncate" style={{ color: "var(--text-secondary)" }}>
                  {v.title}
                </span>
                <span className="mono-data-sm ml-auto" style={{ color: "var(--text-ghost)" }}>
                  {v.age}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
