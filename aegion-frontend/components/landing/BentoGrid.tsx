"use client";

import React from "react";

/* ══════════════════════════════════════════════════════════════
   BENTO GRID — Feature Showcase Cards
   ══════════════════════════════════════════════════════════════ */

interface BentoCard {
  title: string;
  description: string;
  icon: string;
  accent: string;
  span?: string; // grid span class
}

const FEATURES: BentoCard[] = [
  {
    title: "Reasoning Council",
    description:
      "Multi-agent debate with live argument graphs. Watch AI agents reason, agree, and dissent in real-time.",
    icon: "⚙",
    accent: "var(--accent-govern)",
    span: "col-span-2",
  },
  {
    title: "Sentinel Guard",
    description:
      "Continuous risk monitoring. Catches drift before it becomes failure. Never silent.",
    icon: "🛡",
    accent: "var(--accent-risk)",
  },
  {
    title: "Decision Traceability",
    description:
      "Every decision traces to its origin, lineage, and reasoning. Know why everything exists.",
    icon: "◆",
    accent: "var(--accent-reason)",
  },
  {
    title: "Chronos Memory",
    description:
      "Temporal awareness on every entity. Age, stability, amendments. The system remembers.",
    icon: "⏳",
    accent: "var(--accent-memory)",
    span: "col-span-2",
  },
  {
    title: "Governance Tiers",
    description:
      "4-tier friction system. T0 auto-approves. T3 requires hold-to-confirm with blast radius review.",
    icon: "△",
    accent: "var(--accent-execute)",
  },
];

export function BentoGrid() {
  return (
    <div className="grid grid-cols-3 gap-4 max-w-[960px] mx-auto">
      {FEATURES.map((feature, i) => (
        <div
          key={feature.title}
          className={`glass-l2 p-6 rounded-xl card-lift ${feature.span ?? ""} stagger-${i + 1}`}
          style={{
            borderLeft: `3px solid color-mix(in srgb, ${feature.accent} 40%, transparent)`,
          }}
        >
          <div className="flex items-center gap-2.5 mb-3">
            <span className="text-[20px]">{feature.icon}</span>
            <h3
              className="text-[16px] font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              {feature.title}
            </h3>
          </div>
          <p
            className="text-[14px] leading-relaxed"
            style={{ color: "var(--text-secondary)" }}
          >
            {feature.description}
          </p>
        </div>
      ))}
    </div>
  );
}
