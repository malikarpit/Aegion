"use client";

import React, { useState, useEffect } from "react";

/* ══════════════════════════════════════════════════════════════
   ONBOARDING OVERLAY — 3-Step Guided Tour
   
   First-time users see a glass overlay with spotlight cutouts.
   Persisted via localStorage.
   ══════════════════════════════════════════════════════════════ */

const STEPS = [
  {
    title: "System State",
    description:
      "Your session, risk level, and governance status. Always visible, always real-time.",
    target: "system-state-bar",
  },
  {
    title: "Lenses",
    description:
      "Different views into the same system. Council for reasoning. Timeline for memory. Proposals for governance.",
    target: "sidebar",
  },
  {
    title: "Every Decision is Traced",
    description:
      "Provenance, lineage, risk, cost. Click any decision to see why it exists.",
    target: "page-content",
  },
];

export function OnboardingOverlay() {
  const [step, setStep] = useState(0);
  const [show, setShow] = useState(false);

  useEffect(() => {
    const onboarded = localStorage.getItem("aegion:onboarded");
    if (!onboarded) {
      // Small delay to let the page render first
      const timer = setTimeout(() => setShow(true), 1000);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleComplete = () => {
    setShow(false);
    localStorage.setItem("aegion:onboarded", "true");
  };

  const handleNext = () => {
    if (step >= STEPS.length - 1) {
      handleComplete();
    } else {
      setStep((s) => s + 1);
    }
  };

  if (!show) return null;

  const currentStep = STEPS[step];

  return (
    <div className="fixed inset-0 z-[100]">
      {/* Backdrop */}
      <div
        className="absolute inset-0 animate-fade-in"
        style={{
          background: "hsla(222, 15%, 3%, 0.80)",
          backdropFilter: "blur(8px)",
        }}
      />

      {/* Content */}
      <div className="relative flex items-center justify-center h-full">
        <div className="glass-l3 p-6 max-w-[400px] w-full animate-slide-up">
          {/* Step indicator */}
          <div className="flex items-center gap-1.5 mb-4">
            {STEPS.map((_, i) => (
              <div
                key={i}
                className="w-2 h-2 rounded-full transition-colors"
                style={{
                  background:
                    i === step
                      ? "var(--accent-reason)"
                      : i < step
                        ? "var(--status-success)"
                        : "var(--surface-4)",
                }}
              />
            ))}
            <span className="ml-auto hud-label">
              {step + 1} / {STEPS.length}
            </span>
          </div>

          <h3 className="text-[18px] font-semibold mb-2">
            {currentStep.title}
          </h3>
          <p
            className="text-[14px] leading-relaxed mb-6"
            style={{ color: "var(--text-secondary)" }}
          >
            {currentStep.description}
          </p>

          <div className="flex items-center justify-between">
            <button
              onClick={handleComplete}
              className="text-[13px]"
              style={{ color: "var(--text-ghost)" }}
            >
              Skip
            </button>
            <button
              onClick={handleNext}
              className="px-4 py-2 rounded-lg text-[14px] font-medium"
              style={{
                background: "var(--tier-1-bg)",
                border: "1px solid var(--tier-1-border)",
                color: "var(--tier-1)",
              }}
            >
              {step >= STEPS.length - 1 ? "Get Started" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
