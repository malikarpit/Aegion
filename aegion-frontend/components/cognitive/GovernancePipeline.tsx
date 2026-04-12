"use client";

import React from "react";
import type { PipelineStage, PipelineStageStatus } from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   GOVERNANCE PIPELINE — 5-Stage Decision Flow
   
   Two variants:
   - Compact: single line for card/list embedding (32px)
   - Expanded: full layout with labels and durations (~100px)
   ══════════════════════════════════════════════════════════════ */

interface PipelineStageData {
  stage: PipelineStage;
  status: PipelineStageStatus;
  duration?: number; // seconds
  error?: string;
}

interface GovernancePipelineProps {
  stages: PipelineStageData[];
  variant?: "compact" | "expanded";
}

const STAGE_LABELS: Record<PipelineStage, string> = {
  session: "Session",
  distillation: "Distill",
  sentinel: "Sentinel",
  archon: "Archon",
  memory: "Memory",
};

const STATUS_STYLES: Record<
  PipelineStageStatus,
  { fill: string; border: string; icon: string; className: string }
> = {
  completed: {
    fill: "var(--status-success)",
    border: "var(--status-success)",
    icon: "✓",
    className: "",
  },
  active: {
    fill: "var(--accent-reason)",
    border: "var(--accent-reason)",
    icon: "",
    className: "animate-pipeline-pulse",
  },
  failed: {
    fill: "var(--status-error)",
    border: "var(--status-error)",
    icon: "✗",
    className: "",
  },
  waiting: {
    fill: "transparent",
    border: "var(--text-ghost)",
    icon: "",
    className: "",
  },
  skipped: {
    fill: "transparent",
    border: "var(--text-ghost)",
    icon: "–",
    className: "",
  },
};

function formatDuration(s: number): string {
  if (s < 1) return `${(s * 1000).toFixed(0)}ms`;
  return `${s.toFixed(1)}s`;
}

function CompactPipeline({ stages }: { stages: PipelineStageData[] }) {
  return (
    <div className="flex items-center gap-1" role="group" aria-label="Governance pipeline">
      {stages.map((s, i) => {
        const style = STATUS_STYLES[s.status];
        return (
          <React.Fragment key={s.stage}>
            {/* Stage dot */}
            <div
              className={`w-[10px] h-[10px] rounded-full border flex items-center justify-center ${style.className}`}
              style={{
                background: style.fill,
                borderColor: style.border,
                borderWidth: "1.5px",
                borderStyle: s.status === "skipped" ? "dashed" : "solid",
              }}
              title={`${STAGE_LABELS[s.stage]}: ${s.status}${s.duration ? ` (${formatDuration(s.duration)})` : ""}`}
              aria-label={`${STAGE_LABELS[s.stage]}: ${s.status}`}
            >
              {style.icon && (
                <span className="text-[6px] leading-none font-bold" style={{ color: "var(--surface-0)" }}>
                  {style.icon}
                </span>
              )}
            </div>
            {/* Connector line */}
            {i < stages.length - 1 && (
              <div
                className="h-[1.5px] w-[10px]"
                style={{
                  background:
                    s.status === "completed"
                      ? "var(--status-success)"
                      : "var(--text-ghost)",
                }}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function ExpandedPipeline({ stages }: { stages: PipelineStageData[] }) {
  return (
    <div className="flex items-start gap-2" role="group" aria-label="Governance pipeline">
      {stages.map((s, i) => {
        const style = STATUS_STYLES[s.status];
        return (
          <React.Fragment key={s.stage}>
            <div className="flex flex-col items-center gap-1 min-w-[64px]">
              {/* Stage circle */}
              <div
                className={`w-[28px] h-[28px] rounded-full border-2 flex items-center justify-center ${style.className}`}
                style={{
                  background: s.status === "active" ? `color-mix(in srgb, ${style.fill} 15%, transparent)` : style.fill === "transparent" ? "transparent" : `color-mix(in srgb, ${style.fill} 15%, transparent)`,
                  borderColor: style.border,
                  borderStyle: s.status === "skipped" ? "dashed" : "solid",
                }}
              >
                {style.icon ? (
                  <span className="text-[11px] font-bold" style={{ color: style.fill === "transparent" ? "var(--text-ghost)" : style.fill }}>
                    {style.icon}
                  </span>
                ) : s.status === "active" ? (
                  <div className="w-[8px] h-[8px] rounded-full shimmer" style={{ background: style.fill }} />
                ) : null}
              </div>
              {/* Label */}
              <span className="hud-label text-center">{STAGE_LABELS[s.stage]}</span>
              {/* Status */}
              <span className="mono-data-sm" style={{ color: style.fill === "transparent" ? "var(--text-ghost)" : style.fill }}>
                {s.status === "active" ? "..." : s.status.toUpperCase()}
              </span>
              {/* Duration */}
              {s.duration !== undefined && s.status === "completed" && (
                <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                  {formatDuration(s.duration)}
                </span>
              )}
            </div>
            {/* Connector */}
            {i < stages.length - 1 && (
              <div className="flex items-center self-center mt-[4px]">
                <div
                  className="w-[20px] h-[1.5px]"
                  style={{
                    background:
                      s.status === "completed"
                        ? "var(--status-success)"
                        : "var(--border-default)",
                  }}
                />
                <span className="text-[8px]" style={{ color: s.status === "completed" ? "var(--status-success)" : "var(--text-ghost)" }}>
                  ▸
                </span>
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

export function GovernancePipeline({
  stages,
  variant = "compact",
}: GovernancePipelineProps) {
  if (variant === "compact") {
    return <CompactPipeline stages={stages} />;
  }
  return <ExpandedPipeline stages={stages} />;
}
