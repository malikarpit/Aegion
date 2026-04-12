"use client";

import React, { useEffect, useState } from "react";
import type { SystemEvent } from "@/lib/types/system";
import { useActiveInterruption } from "@/lib/context/SystemContext";

/* ══════════════════════════════════════════════════════════════
   SYSTEM INTERRUPTION BANNER — Inline Non-Blocking Alerts
   
   When the system has something critical to say, it interrupts
   the current page — not just the activity feed.
   
   Not a modal — does NOT block interaction.
   Auto-dismiss: 60s if not interacted with.
   Max 1 visible at a time.
   ══════════════════════════════════════════════════════════════ */

interface SystemInterruptionAction {
  label: string;
  onClick: () => void;
  variant: "primary" | "secondary" | "ghost";
}

interface SystemInterruptionBannerProps {
  /** Override from context — if not provided, reads from SystemContext */
  event?: SystemEvent;
  actions?: SystemInterruptionAction[];
  onDismiss?: () => void;
  autoDismissMs?: number;
}

const TYPE_CONFIG: Record<string, { icon: string; accent: string }> = {
  risk:      { icon: "🛡", accent: "var(--accent-risk)" },
  proposal:  { icon: "🧠", accent: "var(--accent-reason)" },
  stability: { icon: "⏱",  accent: "var(--accent-memory)" },
  cost:      { icon: "💰", accent: "var(--accent-cost)" },
  memory:    { icon: "📚", accent: "var(--accent-memory)" },
  reeval:    { icon: "🔄", accent: "var(--accent-reason)" },
};

export function SystemInterruptionBanner({
  event: eventProp,
  actions = [],
  onDismiss: onDismissProp,
  autoDismissMs = 60000,
}: SystemInterruptionBannerProps) {
  const { event: contextEvent, dismiss: contextDismiss } = useActiveInterruption();
  const [visible, setVisible] = useState(false);

  const event = eventProp ?? contextEvent;
  const onDismiss = onDismissProp ?? contextDismiss;

  // Animate in
  useEffect(() => {
    if (event) {
      // Emotional calibration: gentle pulse before appearing
      const pulseTimeout = setTimeout(() => setVisible(true), 400);
      return () => clearTimeout(pulseTimeout);
    }
    setVisible(false);
  }, [event]);

  // Auto-dismiss
  useEffect(() => {
    if (!event || !visible) return;
    const timeout = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss?.(), 300);
    }, autoDismissMs);
    return () => clearTimeout(timeout);
  }, [event, visible, autoDismissMs, onDismiss]);

  if (!event || !visible) return null;

  const config = TYPE_CONFIG[event.type] ?? TYPE_CONFIG.risk;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="glass-l2 p-4 mx-4 mt-3 mb-1 rounded-lg animate-slide-down"
      style={{
        borderLeft: `4px solid ${config.accent}`,
        animation: "initiativePulse 2s ease-in-out, slideDown 300ms ease-out 400ms both",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <span className="text-[16px] mt-0.5">{config.icon}</span>
          <div>
            <p className="hud-label mb-1" style={{ color: config.accent }}>
              ⚠ SYSTEM INTERRUPTION
            </p>
            <p className="text-[14px]" style={{ color: "var(--text-primary)" }}>
              {event.title}
            </p>
            {event.description && (
              <p
                className="text-[13px] mt-1"
                style={{ color: "var(--text-secondary)" }}
              >
                {event.description}
              </p>
            )}
          </div>
        </div>

        {/* Dismiss */}
        <button
          onClick={() => {
            setVisible(false);
            setTimeout(() => onDismiss?.(), 300);
          }}
          className="text-[14px] shrink-0 opacity-50 hover:opacity-100 transition-opacity"
          style={{ color: "var(--text-muted)" }}
          aria-label="Dismiss interruption"
        >
          ✕
        </button>
      </div>

      {/* Actions */}
      {actions.length > 0 && (
        <div className="flex items-center gap-2 mt-3 ml-7">
          {actions.map((action, i) => (
            <button
              key={i}
              onClick={() => {
                action.onClick();
                setVisible(false);
                setTimeout(() => onDismiss?.(), 300);
              }}
              className={`px-3 py-1.5 rounded-md text-[13px] font-medium transition-colors ${
                action.variant === "primary"
                  ? ""
                  : action.variant === "ghost"
                    ? "btn-bracket"
                    : ""
              }`}
              style={
                action.variant === "primary"
                  ? {
                      background: `color-mix(in srgb, ${config.accent} 15%, transparent)`,
                      border: `0.5px solid color-mix(in srgb, ${config.accent} 30%, transparent)`,
                      color: config.accent,
                    }
                  : action.variant === "secondary"
                    ? {
                        background: "var(--surface-3)",
                        border: "0.5px solid var(--border-default)",
                        color: "var(--text-secondary)",
                      }
                    : undefined
              }
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
