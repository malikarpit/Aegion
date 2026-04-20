"use client";

import React, { useEffect, useRef } from "react";
import Link from "next/link";
import { ArrowRight, ChevronDown, Zap, Shield, Brain, Clock, GitBranch } from "lucide-react";
import { SplineHero } from "@/components/landing/SplineHero";
import { ArchitectureFlow } from "@/components/landing/ArchitectureFlow";
import { ProblemSection, FeatureGrid, ComparisonTable } from "@/components/landing/FeatureShowcase";

/* ══════════════════════════════════════════════════════════════
   LANDING PAGE v5 — Cinematic Technical Experience
   
   7 Sections:
   1. Hero (3D Spline + copy)
   2. Problem Statement (why this exists)
   3. Solution (what Aegion is + architecture flow)
   4. Features (bento grid)
   5. Comparison (why Aegion vs. others)
   6. Stats (system capabilities)
   7. CTA + Footer
   
   Smooth scroll with Lenis.
   Scroll-triggered reveals via IntersectionObserver.
   ══════════════════════════════════════════════════════════════ */

const STATS = [
  { value: "5", label: "AI Agents", icon: Brain },
  { value: "4", label: "Governance Tiers", icon: Shield },
  { value: "<2s", label: "Decision Trace", icon: Zap },
  { value: "∞", label: "Memory Depth", icon: Clock },
  { value: "100%", label: "Transparency", icon: GitBranch },
];

export default function LandingPage() {
  const lenisRef = useRef<any>(null);

  // Initialize Lenis smooth scroll
  useEffect(() => {
    let lenis: any;
    let raf: number;

    const init = async () => {
      try {
        const Lenis = (await import("lenis")).default;
        lenis = new Lenis({
          duration: 1.2,
          easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
          smoothWheel: true,
        });
        lenisRef.current = lenis;

        const animate = (time: number) => {
          lenis.raf(time);
          raf = requestAnimationFrame(animate);
        };
        raf = requestAnimationFrame(animate);
      } catch {
        // Lenis failed — native scroll is fine
      }
    };
    init();

    return () => {
      cancelAnimationFrame(raf);
      lenis?.destroy();
    };
  }, []);

  return (
    <div className="min-h-screen" style={{ background: "var(--surface-0)" }}>
      {/* ════════════════════════════════════════════
          SECTION 1: HERO
          ════════════════════════════════════════════ */}
      <section className="relative min-h-screen flex flex-col items-center justify-center px-6 overflow-hidden">
        {/* Ambient gradient background */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: `
              radial-gradient(ellipse at 50% 0%, hsla(260, 100%, 30%, 0.20), transparent 60%),
              radial-gradient(ellipse at 20% 80%, hsla(330, 100%, 25%, 0.10), transparent 50%),
              radial-gradient(ellipse at 80% 60%, hsla(260, 80%, 20%, 0.08), transparent 50%)
            `,
          }}
        />

        {/* 3D Scene */}
        <div className="relative z-10 w-full max-w-[800px] mx-auto mt-[-40px]">
          <SplineHero />
        </div>

        {/* Copy over the scene */}
        <div className="relative z-20 text-center max-w-[720px] mx-auto mt-[-80px]">
          {/* Badge */}
          <div className="flex items-center justify-center gap-2 mb-6 stagger-1">
            <span
              className="text-[11px] font-semibold tracking-[0.1em] uppercase px-4 py-1.5 rounded-full"
              style={{
                background: "hsla(260, 100%, 70%, 0.08)",
                border: "1px solid hsla(260, 100%, 70%, 0.15)",
                color: "var(--accent-reason)",
                fontFamily: "var(--font-mono)",
              }}
            >
              AI Governance Platform
            </span>
          </div>

          {/* Title */}
          <h1
            className="text-[48px] md:text-[64px] font-bold leading-[1.05] mb-6 tracking-tight stagger-2"
            style={{ color: "var(--text-primary)" }}
          >
            Your AI should{" "}
            <span className="gradient-text">prove</span>
            <br />
            every decision it makes.
          </h1>

          {/* Subtitle */}
          <p
            className="text-[17px] md:text-[19px] leading-[1.7] max-w-[580px] mx-auto mb-10 stagger-3"
            style={{ color: "var(--text-secondary)" }}
          >
            Aegion is the cognitive operating system for AI-governed software development.
            It reasons, remembers, and reveals — so you never have to trust blindly.
          </p>

          {/* CTAs */}
          <div className="flex items-center justify-center gap-4 stagger-4">
            <Link
              href="/dashboard"
              className="group px-7 py-3.5 rounded-xl text-[15px] font-semibold inline-flex items-center gap-2.5 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
              style={{
                background: "var(--gradient-primary)",
                color: "white",
                boxShadow: "0 4px 24px hsla(260, 100%, 50%, 0.3), 0 1px 3px hsla(0,0%,0%,0.2)",
              }}
            >
              Get Started
              <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="#solution"
              className="px-7 py-3.5 rounded-xl text-[15px] font-medium inline-flex items-center gap-2 transition-all duration-200"
              style={{
                background: "hsla(260, 20%, 80%, 0.06)",
                border: "1px solid var(--border-default)",
                color: "var(--text-secondary)",
              }}
            >
              See How It Works
              <ChevronDown size={14} />
            </Link>
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 animate-breathe">
          <span className="hud-label" style={{ color: "var(--text-ghost)" }}>SCROLL</span>
          <div className="w-[1px] h-[32px]" style={{ background: "var(--border-default)" }} />
        </div>
      </section>

      {/* ════════════════════════════════════════════
          SECTION 2: PROBLEM STATEMENT
          ════════════════════════════════════════════ */}
      <section className="px-6 py-24 md:py-32">
        <div className="text-center mb-14">
          <p className="hud-label mb-3" style={{ color: "var(--accent-risk)", opacity: 0.8 }}>
            THE PROBLEM
          </p>
          <h2
            className="text-[32px] md:text-[40px] font-bold leading-tight mb-4"
            style={{ color: "var(--text-primary)" }}
          >
            AI tools are black boxes.
            <br />
            <span style={{ color: "var(--text-secondary)" }}>Yours doesn&apos;t have to be.</span>
          </h2>
          <p
            className="text-[16px] max-w-[520px] mx-auto"
            style={{ color: "var(--text-muted)" }}
          >
            Most AI development tools generate code without accountability.
            No reasoning chain. No governance. No memory. That&apos;s not intelligence — it&apos;s improvisation.
          </p>
        </div>
        <ProblemSection />
      </section>

      {/* ════════════════════════════════════════════
          SECTION 3: SOLUTION (Architecture)
          ════════════════════════════════════════════ */}
      <section id="solution" className="px-6 py-24 md:py-32 relative">
        {/* Subtle accent gradient */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: "radial-gradient(ellipse at 50% 30%, hsla(260, 80%, 25%, 0.06), transparent 60%)",
          }}
        />

        <div className="relative z-10">
          <div className="text-center mb-14">
            <p className="hud-label mb-3" style={{ color: "var(--accent-reason)" }}>
              THE SOLUTION
            </p>
            <h2
              className="text-[32px] md:text-[40px] font-bold leading-tight mb-4"
              style={{ color: "var(--text-primary)" }}
            >
              A system that thinks
              <br />
              <span className="gradient-text">before it acts</span>
            </h2>
            <p
              className="text-[16px] max-w-[560px] mx-auto"
              style={{ color: "var(--text-secondary)" }}
            >
              Aegion wraps your AI development workflow in a governance layer that
              reasons, validates, and remembers — automatically. From developer intent
              to governed decision to persistent memory.
            </p>
          </div>

          {/* Architecture Flow Diagram */}
          <div className="mb-12">
            <ArchitectureFlow />
          </div>

          {/* Pipeline labels */}
          <div className="flex items-center justify-center gap-6 flex-wrap max-w-[800px] mx-auto">
            {[
              { label: "INTENT", color: "var(--text-secondary)" },
              { label: "→", color: "var(--text-ghost)" },
              { label: "REASONING", color: "var(--accent-govern)" },
              { label: "→", color: "var(--text-ghost)" },
              { label: "VALIDATION", color: "var(--accent-risk)" },
              { label: "→", color: "var(--text-ghost)" },
              { label: "EXECUTION", color: "var(--accent-execute)" },
              { label: "→", color: "var(--text-ghost)" },
              { label: "MEMORY", color: "var(--accent-memory)" },
            ].map((item, i) => (
              <span
                key={i}
                className="hud-label"
                style={{ color: item.color, fontSize: item.label === "→" ? "14px" : "10px" }}
              >
                {item.label}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════
          SECTION 4: FEATURES (Bento)
          ════════════════════════════════════════════ */}
      <section className="px-6 py-24 md:py-32">
        <div className="text-center mb-14">
          <p className="hud-label mb-3" style={{ color: "var(--accent-execute)" }}>
            CAPABILITIES
          </p>
          <h2
            className="text-[32px] md:text-[40px] font-bold leading-tight mb-4"
            style={{ color: "var(--text-primary)" }}
          >
            Not a dashboard.
            <br />
            <span className="gradient-text">A cognitive interface.</span>
          </h2>
          <p
            className="text-[16px] max-w-[520px] mx-auto"
            style={{ color: "var(--text-secondary)" }}
          >
            Six integrated systems that make AI decision-making visible, governed, and traceable.
          </p>
        </div>
        <FeatureGrid />
      </section>

      {/* ════════════════════════════════════════════
          SECTION 5: COMPARISON
          ════════════════════════════════════════════ */}
      <section className="px-6 py-24 md:py-32 relative">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: "radial-gradient(ellipse at 50% 50%, hsla(260, 60%, 20%, 0.05), transparent 50%)",
          }}
        />
        <div className="relative z-10">
          <div className="text-center mb-14">
            <p className="hud-label mb-3" style={{ color: "var(--accent-cost)" }}>
              WHY AEGION
            </p>
            <h2
              className="text-[32px] md:text-[40px] font-bold leading-tight mb-4"
              style={{ color: "var(--text-primary)" }}
            >
              The missing layer
              <br />
              <span style={{ color: "var(--text-secondary)" }}>in AI development.</span>
            </h2>
          </div>
          <ComparisonTable />
        </div>
      </section>

      {/* ════════════════════════════════════════════
          SECTION 6: STATS
          ════════════════════════════════════════════ */}
      <section className="px-6 py-20">
        <div className="flex items-center justify-center gap-8 md:gap-14 max-w-[900px] mx-auto flex-wrap">
          {STATS.map((stat, i) => (
            <div key={stat.label} className={`text-center stagger-${i + 1}`}>
              <div className="flex items-center justify-center mb-2">
                <stat.icon size={16} style={{ color: "var(--accent-reason)", opacity: 0.5 }} />
              </div>
              <p
                className="text-[36px] font-bold mb-1"
                style={{
                  fontFamily: "var(--font-mono)",
                  background: "var(--gradient-primary)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                {stat.value}
              </p>
              <p className="hud-label">{stat.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ════════════════════════════════════════════
          SECTION 7: CTA + FOOTER
          ════════════════════════════════════════════ */}
      <section className="px-6 py-28 md:py-36 relative">
        {/* Gradient atmosphere */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: `
              radial-gradient(ellipse at 50% 80%, hsla(260, 100%, 30%, 0.12), transparent 50%),
              radial-gradient(ellipse at 50% 100%, hsla(330, 100%, 25%, 0.06), transparent 40%)
            `,
          }}
        />

        <div className="relative z-10 text-center max-w-[640px] mx-auto">
          <h2
            className="text-[36px] md:text-[48px] font-bold leading-tight mb-5"
            style={{ color: "var(--text-primary)" }}
          >
            Ready to{" "}
            <span className="gradient-text">govern</span>
            {" "}your AI?
          </h2>
          <p
            className="text-[17px] leading-relaxed mb-10"
            style={{ color: "var(--text-secondary)" }}
          >
            Start building with the system that remembers why.
            Every decision traced. Every action governed. Every change remembered.
          </p>

          <div className="flex items-center justify-center gap-4">
            <Link
              href="/dashboard"
              className="group px-8 py-4 rounded-xl text-[16px] font-semibold inline-flex items-center gap-2.5 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
              style={{
                background: "var(--gradient-primary)",
                color: "white",
                boxShadow: "0 4px 32px hsla(260, 100%, 50%, 0.35), 0 1px 3px hsla(0,0%,0%,0.2)",
              }}
            >
              Enter Aegion
              <ArrowRight size={18} className="transition-transform group-hover:translate-x-1" />
            </Link>
            <Link
              href="/login"
              className="px-8 py-4 rounded-xl text-[16px] font-medium transition-all duration-200"
              style={{
                background: "hsla(260, 20%, 80%, 0.06)",
                border: "1px solid var(--border-default)",
                color: "var(--text-secondary)",
              }}
            >
              Sign In
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer
        className="px-6 py-10 text-center"
        style={{ borderTop: "1px solid var(--border-subtle)" }}
      >
        <p
          className="text-[13px] font-medium tracking-wide mb-1.5"
          style={{
            fontFamily: "var(--font-mono)",
            background: "var(--gradient-primary)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}
        >
          AEGION
        </p>
        <p className="text-[12px]" style={{ color: "var(--text-ghost)" }}>
          Cognitive Operating System · Built for developers who demand transparency from their AI.
        </p>
        <p className="text-[11px] mt-2" style={{ color: "var(--text-ghost)", opacity: 0.5 }}>
          © 2026 Aegion. All rights reserved.
        </p>
      </footer>
    </div>
  );
}
