"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useSession } from "@/lib/context/SystemContext";
import { TemporalMeta } from "./TemporalMeta";

/* ══════════════════════════════════════════════════════════════
   ENTRY EXPERIENCE LOOP — First 30 Seconds Orchestrated
   
   After onboarding (or for returning users with no active session),
   the first 30 seconds demonstrate system intelligence.
   
   T+0s: "Start by reviewing your last decision"
   T+3s: "Here's what changed since"
   T+6s: "Sentinel has a new risk signal"
   
   Not shown if user has active session or recently dismissed.
   Any click anywhere dismisses immediately.
   ══════════════════════════════════════════════════════════════ */

interface LastDecision {
  id: string;
  title: string;
  tier: string;
  createdAt: number;
  stability: "stable" | "settling" | "volatile";
  trust: "validated" | "moderate" | "novel" | "unproven";
}

interface EntryExperienceLoopProps {
  lastDecision?: LastDecision | null;
  changesSince?: { newDecisions: number; riskDelta: number } | null;
  riskSignal?: { alertText: string } | null;
  onOpenDecision?: (decisionId: string) => void;
}

export function EntryExperienceLoop({
  lastDecision,
  changesSince,
  riskSignal,
  onOpenDecision,
}: EntryExperienceLoopProps) {
  const session = useSession();
  const [visible, setVisible] = useState(false);
  const [phase, setPhase] = useState(0); // 0=suggestion, 1=changes, 2=risk

  // Check if we should show
  useEffect(() => {
    if (session) return; // Don't show if active session

    const lastShown = localStorage.getItem("aegion:lastEntryExperience");
    if (lastShown) {
      const elapsed = Date.now() - parseInt(lastShown, 10);
      if (elapsed < 24 * 60 * 60 * 1000) return; // Only once per 24h
    }

    if (!lastDecision) return;

    // Show after a brief delay
    const timer = setTimeout(() => setVisible(true), 500);
    return () => clearTimeout(timer);
  }, [session, lastDecision]);

  // Phase progression
  useEffect(() => {
    if (!visible) return;

    const timers: NodeJS.Timeout[] = [];

    if (changesSince) {
      timers.push(setTimeout(() => setPhase(1), 3000));
    }
    if (riskSignal) {
      timers.push(setTimeout(() => setPhase(2), 6000));
    }

    return () => timers.forEach(clearTimeout);
  }, [visible, changesSince, riskSignal]);

  const dismiss = useCallback(() => {
    setVisible(false);
    localStorage.setItem("aegion:lastEntryExperience", String(Date.now()));
  }, []);

  // Dismiss on any click outside
  useEffect(() => {
    if (!visible) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest("[data-entry-experience]")) {
        dismiss();
      }
    };
    // Delay listener to avoid immediate dismiss
    const timer = setTimeout(() => {
      window.addEventListener("click", handler);
    }, 100);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("click", handler);
    };
  }, [visible, dismiss]);

  if (!visible || !lastDecision) return null;

  const TRUST_ICONS: Record<string, string> = {
    validated: "✓",
    moderate: "◐",
    novel: "◇",
    unproven: "?",
  };

  return (
    <div
      data-entry-experience="true"
      className="glass-l2 p-5 max-w-[480px] mx-auto mt-8 animate-slide-up"
      role="region"
      aria-label="System suggestion"
    >
      <p className="hud-label mb-3" style={{ color: "var(--accent-reason)" }}>
        🧠 SYSTEM SUGGESTION
      </p>

      <p className="text-[14px] mb-3" style={{ color: "var(--text-secondary)" }}>
        Start by reviewing your last decision
      </p>

      <div className="glass-l1 p-3 rounded-lg mb-3">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[14px] font-medium">
            Decision #{lastDecision.id}: &quot;{lastDecision.title}&quot;
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="tier-badge text-[9px]"
            style={{
              background: `var(--tier-${lastDecision.tier.replace("T", "")}-bg, var(--tier-0-bg))`,
              color: `var(--tier-${lastDecision.tier.replace("T", "")}, var(--tier-0))`,
            }}
          >
            {lastDecision.tier}
          </span>
          <TemporalMeta
            createdAt={lastDecision.createdAt}
            stability={lastDecision.stability}
            inline
          />
          <span
            className="mono-data-sm"
            style={{
              color: `var(--trust-${lastDecision.trust})`,
            }}
          >
            {TRUST_ICONS[lastDecision.trust] || "?"} {lastDecision.trust.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Phase 1: Changes since */}
      {phase >= 1 && changesSince && (
        <div className="animate-fade-in mb-3">
          <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
            → Here&apos;s what changed since this decision was made
          </p>
          <p className="mono-data-sm mt-1" style={{ color: "var(--text-secondary)" }}>
            {changesSince.newDecisions} new related decisions, risk{" "}
            <span
              style={{
                color:
                  changesSince.riskDelta > 0
                    ? "var(--status-error)"
                    : "var(--status-success)",
              }}
            >
              {changesSince.riskDelta > 0 ? "+" : ""}
              {changesSince.riskDelta.toFixed(2)}
            </span>
          </p>
        </div>
      )}

      {/* Phase 2: Risk signal */}
      {phase >= 2 && riskSignal && (
        <div className="animate-fade-in mb-3">
          <p className="text-[13px]" style={{ color: "var(--accent-risk)" }}>
            → Sentinel has a new risk signal related to this area
          </p>
          <p className="mono-data-sm mt-1" style={{ color: "var(--text-secondary)" }}>
            {riskSignal.alertText}
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4">
        <button
          onClick={() => {
            onOpenDecision?.(lastDecision.id);
            dismiss();
          }}
          className="px-3 py-1.5 rounded-md text-[13px] font-medium"
          style={{
            background: "var(--tier-1-bg)",
            border: "0.5px solid var(--tier-1-border)",
            color: "var(--tier-1)",
          }}
        >
          Open Decision
        </button>
        <button
          onClick={dismiss}
          className="btn-bracket text-[13px] px-3 py-1.5"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
