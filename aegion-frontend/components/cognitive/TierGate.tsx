"use client";

import React, { useState, useRef, useCallback } from "react";
import type { GovernanceTier } from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   TIER GATE — Governance Friction
   
   T0: No friction (auto-approve toast)
   T1: Tooltip (inline confirm)
   T2: Modal (checkbox + confirm)
   T3: Full overlay (hold-to-confirm 3s, red backdrop)
   ══════════════════════════════════════════════════════════════ */

interface TierGateProps {
  tier: GovernanceTier;
  onConfirm: () => void | Promise<void>;
  children: React.ReactNode;
  decisionTitle?: string;
  blastRadiusCount?: number;
  riskDelta?: number;
}

// ── T3 Hold-to-Confirm Button ──
function HoldToConfirm({
  onConfirm,
  children,
}: {
  onConfirm: () => void;
  children: React.ReactNode;
}) {
  const [progress, setProgress] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const handleStart = useCallback(() => {
    intervalRef.current = setInterval(() => {
      setProgress((p) => {
        if (p >= 100) {
          clearInterval(intervalRef.current!);
          onConfirm();
          return 100;
        }
        return p + 100 / 30; // 30 ticks over 3s (100ms interval)
      });
    }, 100);
  }, [onConfirm]);

  const handleEnd = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setProgress(0);
  }, []);

  return (
    <button
      onMouseDown={handleStart}
      onMouseUp={handleEnd}
      onMouseLeave={handleEnd}
      onTouchStart={handleStart}
      onTouchEnd={handleEnd}
      className="relative flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-medium text-[14px] select-none cursor-pointer overflow-hidden"
      style={{
        background: "var(--tier-3-bg)",
        border: "1px solid var(--tier-3-border)",
        color: "var(--tier-3)",
        boxShadow: progress > 0 ? "var(--tier-3-glow)" : "none",
        transition: "box-shadow 200ms",
      }}
      aria-label="Hold for 3 seconds to confirm"
    >
      {/* Progress fill */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `linear-gradient(90deg, hsla(348, 82%, 52%, 0.15) ${progress}%, transparent ${progress}%)`,
          transition: "none",
        }}
      />

      {/* Ring SVG */}
      <svg width="24" height="24" viewBox="0 0 24 24" className="shrink-0">
        <circle
          cx="12"
          cy="12"
          r="10"
          fill="none"
          stroke="var(--tier-3-border)"
          strokeWidth="2"
        />
        <circle
          cx="12"
          cy="12"
          r="10"
          fill="none"
          stroke="var(--tier-3)"
          strokeWidth="2"
          strokeDasharray="63"
          strokeDashoffset={63 - (63 * progress) / 100}
          strokeLinecap="round"
          style={{
            transform: "rotate(-90deg)",
            transformOrigin: "center",
            transition: "none",
          }}
        />
      </svg>

      <span className="relative z-10">{children}</span>

      {progress > 0 && (
        <span className="relative z-10 mono-data-sm" style={{ color: "var(--tier-3)" }}>
          {Math.ceil(3 - (progress * 3) / 100)}s
        </span>
      )}
    </button>
  );
}

export function TierGate({
  tier,
  onConfirm,
  children,
  decisionTitle,
  blastRadiusCount = 0,
  riskDelta = 0,
}: TierGateProps) {
  const [showGate, setShowGate] = useState(false);
  const [accepted, setAccepted] = useState(false);

  const handleTrigger = useCallback(() => {
    if (tier === "T0") {
      onConfirm();
      return;
    }
    setShowGate(true);
  }, [tier, onConfirm]);

  const handleConfirm = useCallback(() => {
    setShowGate(false);
    setAccepted(false);
    onConfirm();
  }, [onConfirm]);

  const handleClose = useCallback(() => {
    setShowGate(false);
    setAccepted(false);
  }, []);

  return (
    <>
      {/* Trigger */}
      <div onClick={handleTrigger} className="cursor-pointer">
        {children}
      </div>

      {/* ── T1: Tooltip ── */}
      {tier === "T1" && showGate && (
        <div
          className="glass-l2 p-3 mt-2 animate-fade-in"
          role="dialog"
          aria-label="Tier 1 confirmation"
        >
          <p className="text-[13px] mb-2" style={{ color: "var(--text-secondary)" }}>
            This will be reviewed by the council.
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleConfirm}
              className="px-3 py-1.5 rounded-md text-[13px] font-medium"
              style={{
                background: "var(--tier-1-bg)",
                border: "0.5px solid var(--tier-1-border)",
                color: "var(--tier-1)",
              }}
            >
              Proceed
            </button>
            <button
              onClick={handleClose}
              className="px-3 py-1.5 rounded-md text-[13px] btn-bracket"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* ── T2: Modal ── */}
      {tier === "T2" && showGate && (
        <>
          <div className="backdrop-overlay animate-fade-in" onClick={handleClose} />
          <div
            className="fixed inset-0 flex items-center justify-center z-50"
            role="dialog"
            aria-label="Tier 2 approval"
          >
            <div
              className="glass-l3 p-6 max-w-[420px] w-full animate-slide-up"
              style={{
                border: "1px solid var(--tier-2-border)",
                // Emotional calibration: no delay for T2
              }}
            >
              <h3 className="text-[16px] font-semibold mb-3">
                Approve{" "}
                <span className="tier-badge tier-badge-t2 ml-1">T2</span>
              </h3>
              {decisionTitle && (
                <p className="text-[14px] mb-3" style={{ color: "var(--text-secondary)" }}>
                  &quot;{decisionTitle}&quot;
                </p>
              )}

              <div className="flex flex-col gap-2 mb-4">
                {blastRadiusCount > 0 && (
                  <div className="flex items-center gap-2 text-[13px]">
                    <span style={{ color: "var(--text-muted)" }}>Blast radius:</span>
                    <span className="mono-data" style={{ color: "var(--tier-2)" }}>
                      {blastRadiusCount} affected
                    </span>
                  </div>
                )}
                {riskDelta !== 0 && (
                  <div className="flex items-center gap-2 text-[13px]">
                    <span style={{ color: "var(--text-muted)" }}>Risk impact:</span>
                    <span
                      className="mono-data"
                      style={{
                        color:
                          riskDelta > 0 ? "var(--status-error)" : "var(--status-success)",
                      }}
                    >
                      {riskDelta > 0 ? "+" : ""}
                      {riskDelta.toFixed(2)}
                    </span>
                  </div>
                )}
              </div>

              <label className="flex items-center gap-2 mb-4 cursor-pointer">
                <input
                  type="checkbox"
                  checked={accepted}
                  onChange={(e) => setAccepted(e.target.checked)}
                  className="w-4 h-4 rounded accent-[var(--tier-2)]"
                />
                <span className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
                  I understand the impact of this decision
                </span>
              </label>

              <div className="flex gap-2">
                <button
                  disabled={!accepted}
                  onClick={handleConfirm}
                  className="px-4 py-2 rounded-lg text-[14px] font-medium disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{
                    background: "var(--tier-2-bg)",
                    border: "1px solid var(--tier-2-border)",
                    color: "var(--tier-2)",
                  }}
                >
                  Confirm
                </button>
                <button onClick={handleClose} className="px-4 py-2 text-[14px] btn-bracket">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── T3: Full Overlay + Hold-to-Confirm ── */}
      {tier === "T3" && showGate && (
        <>
          <div className="backdrop-t3 animate-fade-in" />
          <div
            className="fixed inset-0 flex items-center justify-center z-50"
            role="dialog"
            aria-label="Tier 3 critical approval"
          >
            <div
              className="glass-l3 p-8 max-w-[520px] w-full animate-slide-up"
              style={{
                border: "1px solid var(--tier-3-border)",
                boxShadow: "var(--tier-3-glow)",
                animationDelay: "200ms", // Law 5: deliberate weight
                animationFillMode: "both",
              }}
            >
              <div className="flex items-center gap-3 mb-4">
                <span className="tier-badge tier-badge-t3 text-[13px]">T3 CRITICAL</span>
                <span className="text-[16px] font-semibold">
                  Irreversible Decision
                </span>
              </div>

              {decisionTitle && (
                <p className="text-[15px] mb-4" style={{ color: "var(--text-secondary)" }}>
                  &quot;{decisionTitle}&quot;
                </p>
              )}

              <div className="glass-l1 p-3 mb-4 rounded-lg">
                <div className="flex flex-col gap-2">
                  {blastRadiusCount > 0 && (
                    <div className="flex items-center gap-2 text-[13px]">
                      <span style={{ color: "var(--text-muted)" }}>Blast radius:</span>
                      <span className="mono-data font-medium" style={{ color: "var(--tier-3)" }}>
                        {blastRadiusCount} entities affected
                      </span>
                    </div>
                  )}
                  {riskDelta !== 0 && (
                    <div className="flex items-center gap-2 text-[13px]">
                      <span style={{ color: "var(--text-muted)" }}>Risk delta:</span>
                      <span className="mono-data font-medium" style={{ color: "var(--tier-3)" }}>
                        {riskDelta > 0 ? "+" : ""}
                        {riskDelta.toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <p
                className="text-[13px] font-medium mb-6"
                style={{ color: "var(--tier-3)" }}
              >
                ⚠ This action cannot be undone. Hold the button for 3 seconds to confirm.
              </p>

              <div className="flex items-center gap-3">
                <HoldToConfirm onConfirm={handleConfirm}>
                  Confirm Irreversible Action
                </HoldToConfirm>
                <button onClick={handleClose} className="px-4 py-2 text-[14px] btn-bracket">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
