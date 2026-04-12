"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useSystemContext } from "@/lib/context/SystemContext";

/* ══════════════════════════════════════════════════════════════
   DEGRADED BANNER — Failure Mode Personality
   
   Law 6: "The System Is Honest When Struggling"
   
   Not "BACKEND UNREACHABLE" (cold/technical)
   But "CONNECTION UNSTABLE — Working with last known data" (honest)
   
   3 stages: degraded (0-5min) → extended (5-15min) → critical (>15min)
   Sets data-degraded="true" on root — triggers global personality shift.
   ══════════════════════════════════════════════════════════════ */

const STAGE_CONFIG = {
  degraded: {
    text: "Connection unstable — Working with last known data",
    bg: "hsla(38, 88%, 52%, 0.08)",
    border: "var(--tier-2-border)",
    color: "var(--tier-2)",
  },
  extended: {
    text: "Extended disconnection — Data may be significantly outdated",
    bg: "hsla(38, 70%, 45%, 0.10)",
    border: "var(--tier-2-border)",
    color: "var(--tier-2)",
  },
  critical: {
    text: "System offline — Please check backend connection",
    bg: "hsla(348, 82%, 52%, 0.08)",
    border: "var(--tier-3-border)",
    color: "var(--tier-3)",
  },
} as const;

function formatTimeSince(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 60) return "just now";
  const min = Math.floor(diff / 60);
  return `${min} min ago`;
}

export function DegradedBanner() {
  const { state, dispatch } = useSystemContext();
  const { system } = state;
  const [retryCountdown, setRetryCountdown] = useState(30);

  const isDegraded = system.backendStatus !== "connected";
  const stage = system.degradationStage;

  // Set data-degraded on root
  useEffect(() => {
    const root = document.documentElement;
    if (isDegraded) {
      root.setAttribute("data-degraded", "true");
    } else {
      root.removeAttribute("data-degraded");
    }
    return () => root.removeAttribute("data-degraded");
  }, [isDegraded]);

  // Retry countdown
  useEffect(() => {
    if (!isDegraded) return;
    setRetryCountdown(30);
    const interval = setInterval(() => {
      setRetryCountdown((c) => {
        if (c <= 1) {
          handleRetry();
          return 30;
        }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDegraded]);

  const handleRetry = useCallback(async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const res = await fetch(`${apiUrl}/health`, { signal: AbortSignal.timeout(5000) });
      if (res.ok) {
        // System "wakes up" — revert personality
        dispatch({ type: "BACKEND_STATUS", payload: { status: "connected" } });
      }
    } catch {
      // Still degraded
    }
  }, [dispatch]);

  if (!isDegraded || stage === "healthy") return null;

  const config = STAGE_CONFIG[stage as keyof typeof STAGE_CONFIG] ?? STAGE_CONFIG.degraded;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="flex items-center justify-between h-[36px] px-4 text-[12px] z-40"
      style={{
        background: config.bg,
        borderBottom: `0.5px solid ${config.border}`,
      }}
    >
      <div className="flex items-center gap-2">
        <span style={{ color: config.color }}>⚠</span>
        <span className="font-medium" style={{ color: config.color }}>
          {config.text}
        </span>
      </div>

      <div className="flex items-center gap-3">
        <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
          {system.lastSync ? formatTimeSince(system.lastSync) : "—"}
        </span>
        <button
          onClick={() => { setRetryCountdown(30); handleRetry(); }}
          className="px-2 py-0.5 rounded text-[11px] font-medium"
          style={{
            background: `color-mix(in srgb, ${config.color} 10%, transparent)`,
            color: config.color,
            border: `0.5px solid ${config.border}`,
          }}
          data-allow-degraded="true"
        >
          RETRY ({retryCountdown}s)
        </button>
      </div>
    </div>
  );
}
