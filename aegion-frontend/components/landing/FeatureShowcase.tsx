"use client";

import React, { useRef, useEffect, useState } from "react";
import {
  Brain, Shield, GitBranch, Clock, Layers, Eye,
  AlertTriangle, Target, Database,
} from "lucide-react";

/* ══════════════════════════════════════════════════════════════
   FEATURE SHOWCASE — Redesigned Bento Grid + Problem Cards
   
   Scroll-triggered reveals with intersection observer.
   Each card has a subtle accent glow and icon.
   ══════════════════════════════════════════════════════════════ */

// Hook for viewport detection
function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setInView(true); },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);

  return { ref, inView };
}

/* ── Problem Cards ── */

const PROBLEMS = [
  {
    icon: AlertTriangle,
    title: "AI makes decisions you can't trace",
    description: "Current AI dev tools generate code with zero accountability. No reasoning chain. No audit trail. You're trusting a black box.",
  },
  {
    icon: Target,
    title: "No governance between intent and execution",
    description: "There's no checkpoint between \"AI suggested this\" and \"it's in production.\" That gap is where failures happen.",
  },
  {
    icon: Database,
    title: "Systems forget what they learned",
    description: "Every session starts from zero. No memory of past decisions, patterns, or failures. Intelligence without continuity isn't intelligence.",
  },
];

export function ProblemSection() {
  const { ref, inView } = useInView();

  return (
    <div ref={ref} className="grid md:grid-cols-3 gap-5 max-w-[1060px] mx-auto">
      {PROBLEMS.map((p, i) => (
        <div
          key={p.title}
          className="glass-l1 p-6 rounded-xl"
          style={{
            opacity: inView ? 1 : 0,
            transform: inView ? "translateY(0)" : "translateY(24px)",
            transition: `all 600ms cubic-bezier(0.4, 0, 0.2, 1) ${i * 120}ms`,
            borderTop: "2px solid hsla(350, 90%, 62%, 0.2)",
          }}
        >
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center mb-4"
            style={{ background: "hsla(350, 90%, 62%, 0.08)" }}
          >
            <p.icon size={20} style={{ color: "var(--accent-risk)" }} />
          </div>
          <h3
            className="text-[16px] font-semibold mb-2"
            style={{ color: "var(--text-primary)" }}
          >
            {p.title}
          </h3>
          <p
            className="text-[14px] leading-relaxed"
            style={{ color: "var(--text-secondary)" }}
          >
            {p.description}
          </p>
        </div>
      ))}
    </div>
  );
}

/* ── Feature Bento Grid ── */

interface Feature {
  title: string;
  description: string;
  icon: React.ElementType;
  accent: string;
  accentBg: string;
  span?: string;
}

const FEATURES: Feature[] = [
  {
    title: "Reasoning Council",
    description: "Multi-agent debate with live argument graphs. Watch AI agents reason, agree, and dissent in real-time before any decision is made.",
    icon: Brain,
    accent: "var(--accent-govern)",
    accentBg: "hsla(280, 85%, 65%, 0.08)",
    span: "md:col-span-2",
  },
  {
    title: "Sentinel Guard",
    description: "Continuous risk monitoring. Catches drift before it becomes failure. Never silent, never sleeping.",
    icon: Shield,
    accent: "var(--accent-risk)",
    accentBg: "hsla(350, 90%, 62%, 0.08)",
  },
  {
    title: "Decision Lineage",
    description: "Every decision traces back to its origin, the memories that informed it, and the decisions it supersedes.",
    icon: GitBranch,
    accent: "var(--accent-reason)",
    accentBg: "hsla(260, 100%, 70%, 0.08)",
  },
  {
    title: "Temporal Memory",
    description: "The system remembers. Every entity has an age, stability rating, and amendment history. Built on Chronos.",
    icon: Clock,
    accent: "var(--accent-memory)",
    accentBg: "hsla(240, 90%, 72%, 0.08)",
    span: "md:col-span-2",
  },
  {
    title: "Governance Tiers",
    description: "4-tier friction system. T0 auto-approves. T3 requires hold-to-confirm with blast radius review and risk assessment.",
    icon: Layers,
    accent: "var(--accent-execute)",
    accentBg: "hsla(165, 85%, 55%, 0.08)",
  },
  {
    title: "Full Transparency",
    description: "See every model call, token count, latency, and cost behind every decision. Nothing hidden, nothing obscured.",
    icon: Eye,
    accent: "var(--accent-cost)",
    accentBg: "hsla(42, 100%, 60%, 0.08)",
  },
];

export function FeatureGrid() {
  const { ref, inView } = useInView();

  return (
    <div ref={ref} className="grid md:grid-cols-3 gap-4 max-w-[1060px] mx-auto">
      {FEATURES.map((f, i) => (
        <div
          key={f.title}
          className={`glass-l2 p-6 rounded-xl card-lift group ${f.span ?? ""}`}
          style={{
            opacity: inView ? 1 : 0,
            transform: inView ? "translateY(0) scale(1)" : "translateY(20px) scale(0.97)",
            transition: `all 500ms cubic-bezier(0.4, 0, 0.2, 1) ${i * 80}ms`,
          }}
        >
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center mb-4 transition-transform group-hover:scale-110"
            style={{ background: f.accentBg }}
          >
            <f.icon size={20} style={{ color: f.accent }} />
          </div>
          <h3
            className="text-[16px] font-semibold mb-2"
            style={{ color: "var(--text-primary)" }}
          >
            {f.title}
          </h3>
          <p
            className="text-[14px] leading-relaxed"
            style={{ color: "var(--text-secondary)" }}
          >
            {f.description}
          </p>
        </div>
      ))}
    </div>
  );
}

/* ── Comparison Table ── */

const COMPARISON_ROWS = [
  "Decision Traceability",
  "Multi-Agent Reasoning",
  "Governance Tiers",
  "Persistent Memory",
  "Risk Assessment",
  "Full Cost Transparency",
];

export function ComparisonTable() {
  const { ref, inView } = useInView(0.2);

  return (
    <div ref={ref} className="max-w-[640px] mx-auto">
      <div
        className="glass-l2 rounded-xl overflow-hidden"
        style={{
          opacity: inView ? 1 : 0,
          transform: inView ? "translateY(0)" : "translateY(16px)",
          transition: "all 600ms ease-out",
        }}
      >
        {/* Header */}
        <div
          className="grid grid-cols-3 gap-4 px-6 py-4"
          style={{ borderBottom: "1px solid var(--border-default)" }}
        >
          <div />
          <p className="hud-label text-center" style={{ color: "var(--text-ghost)" }}>
            OTHER TOOLS
          </p>
          <p className="hud-label text-center" style={{ color: "var(--accent-reason)" }}>
            AEGION
          </p>
        </div>

        {/* Rows */}
        {COMPARISON_ROWS.map((row, i) => (
          <div
            key={row}
            className="grid grid-cols-3 gap-4 px-6 py-3.5 items-center"
            style={{
              borderBottom: i < COMPARISON_ROWS.length - 1 ? "1px solid var(--border-subtle)" : "none",
              opacity: inView ? 1 : 0,
              transition: `opacity 400ms ease-out ${200 + i * 80}ms`,
            }}
          >
            <p className="text-[14px]" style={{ color: "var(--text-secondary)" }}>
              {row}
            </p>
            <p className="text-center text-[18px]" style={{ color: "var(--accent-risk)", opacity: 0.6 }}>
              ✕
            </p>
            <p className="text-center text-[18px]" style={{ color: "var(--accent-trust)" }}>
              ✓
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
