"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Search, ArrowRight, Command, Settings, Shield,
  LayoutDashboard, MessageSquare, FileCheck, Clock,
  Network, Brain, DollarSign, Puzzle, FileText,
  Focus, Moon, Eye, Zap,
} from "lucide-react";

/* ══════════════════════════════════════════════════════════════
   COMMAND PALETTE — ⌘K Interface
   
   System queries, navigation, actions, mode switching.
   Uses native HTML dialog for accessibility.
   ══════════════════════════════════════════════════════════════ */

interface PaletteItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ElementType;
  action: () => void;
  category: "navigation" | "action" | "mode" | "system";
  keywords?: string[];
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const items: PaletteItem[] = [
    // Navigation
    { id: "nav-dashboard", label: "Dashboard", icon: LayoutDashboard, action: () => router.push("/dashboard"), category: "navigation", keywords: ["home", "overview"] },
    { id: "nav-council", label: "Council", icon: MessageSquare, action: () => router.push("/dashboard/council"), category: "navigation", keywords: ["chat", "debate", "agents"] },
    { id: "nav-proposals", label: "Proposals", icon: FileCheck, action: () => router.push("/dashboard/proposals"), category: "navigation", keywords: ["decisions", "approve"] },
    { id: "nav-timeline", label: "Timeline", icon: Clock, action: () => router.push("/dashboard/timeline"), category: "navigation", keywords: ["history", "chronos"] },
    { id: "nav-knowledge", label: "Knowledge Graph", icon: Network, action: () => router.push("/dashboard/knowledge"), category: "navigation", keywords: ["graph", "nodes"] },
    { id: "nav-memory", label: "Memory", icon: Brain, action: () => router.push("/dashboard/memory"), category: "navigation", keywords: ["remember", "episodic"] },
    { id: "nav-risk", label: "Risk & Sentinel", icon: Shield, action: () => router.push("/dashboard/risk"), category: "navigation", keywords: ["sentinel", "security", "alerts"] },
    { id: "nav-cost", label: "Cost", icon: DollarSign, action: () => router.push("/dashboard/cost"), category: "navigation", keywords: ["budget", "tokens", "spend"] },
    { id: "nav-skills", label: "Skills", icon: Puzzle, action: () => router.push("/dashboard/skills"), category: "navigation", keywords: ["tools", "plugins"] },
    { id: "nav-adrs", label: "ADRs", icon: FileText, action: () => router.push("/dashboard/adrs"), category: "navigation", keywords: ["architecture", "decision records"] },
    { id: "nav-settings", label: "Settings", icon: Settings, action: () => router.push("/dashboard/settings"), category: "navigation", keywords: ["config", "api keys"] },
    // Actions
    { id: "act-new-session", label: "Start New Session", icon: Zap, action: () => { router.push("/dashboard/council"); }, category: "action", keywords: ["create", "begin"] },
    { id: "act-new-proposal", label: "Create Proposal", icon: FileCheck, action: () => { router.push("/dashboard/proposals"); }, category: "action", keywords: ["propose", "new"] },
    // Modes
    { id: "mode-focus", label: "Toggle Focus Mode", description: "⌘.", icon: Focus, action: () => { document.dispatchEvent(new CustomEvent("aegion:toggle-focus")); }, category: "mode", keywords: ["distraction", "minimal"] },
    // System
    { id: "sys-view-risk", label: "View Current Risk", icon: Shield, action: () => router.push("/dashboard/risk"), category: "system", keywords: ["sentinel", "threat"] },
    { id: "sys-view-cost", label: "View Cost Report", icon: DollarSign, action: () => router.push("/dashboard/cost"), category: "system", keywords: ["budget", "spend"] },
  ];

  const filtered = query.trim()
    ? items.filter((item) => {
        const q = query.toLowerCase();
        return (
          item.label.toLowerCase().includes(q) ||
          item.description?.toLowerCase().includes(q) ||
          item.keywords?.some((k) => k.includes(q))
        );
      })
    : items;

  // Group by category
  const grouped = filtered.reduce<Record<string, PaletteItem[]>>((acc, item) => {
    if (!acc[item.category]) acc[item.category] = [];
    acc[item.category].push(item);
    return acc;
  }, {});

  const flatFiltered = Object.values(grouped).flat();

  // Keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open]);

  // Focus input on open
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, flatFiltered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const item = flatFiltered[selectedIndex];
        if (item) {
          item.action();
          setOpen(false);
        }
      }
    },
    [flatFiltered, selectedIndex]
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  if (!open) return null;

  const categoryLabels: Record<string, string> = {
    navigation: "NAVIGATION",
    action: "ACTIONS",
    mode: "MODES",
    system: "SYSTEM",
  };

  let globalIndex = 0;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[100] animate-fade-in"
        style={{ background: "hsla(222,15%,5%,0.6)", backdropFilter: "blur(4px)" }}
        onClick={() => setOpen(false)}
      />

      {/* Palette */}
      <div
        className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-[560px] z-[101] glass-l3 rounded-xl overflow-hidden animate-scale-in"
        role="dialog"
        aria-label="Command palette"
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3" style={{ borderBottom: "0.5px solid var(--border-default)" }}>
          <Search size={16} style={{ color: "var(--text-ghost)" }} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            className="flex-1 bg-transparent text-[15px] outline-none"
            style={{ color: "var(--text-primary)" }}
          />
          <span className="hud-label px-1.5 py-0.5 rounded" style={{ background: "var(--surface-3)", color: "var(--text-ghost)" }}>
            ESC
          </span>
        </div>

        {/* Results */}
        <div className="max-h-[360px] overflow-y-auto smooth-scroll py-2">
          {Object.entries(grouped).map(([category, categoryItems]) => (
            <div key={category}>
              <p className="hud-label px-4 py-1.5">{categoryLabels[category] || category.toUpperCase()}</p>
              {categoryItems.map((item) => {
                const idx = globalIndex++;
                const Icon = item.icon;
                const isSelected = idx === selectedIndex;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      item.action();
                      setOpen(false);
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors"
                    style={{
                      background: isSelected ? "var(--surface-hover)" : "transparent",
                      color: isSelected ? "var(--text-primary)" : "var(--text-secondary)",
                    }}
                    onMouseEnter={() => setSelectedIndex(idx)}
                  >
                    <Icon size={16} style={{ color: isSelected ? "var(--accent-reason)" : "var(--text-ghost)" }} />
                    <div className="flex-1 min-w-0">
                      <span className="text-[14px]">{item.label}</span>
                      {item.description && (
                        <span className="ml-2 mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                          {item.description}
                        </span>
                      )}
                    </div>
                    {isSelected && <ArrowRight size={12} style={{ color: "var(--text-ghost)" }} />}
                  </button>
                );
              })}
            </div>
          ))}

          {flatFiltered.length === 0 && (
            <div className="text-center py-8">
              <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>No results for &quot;{query}&quot;</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center gap-4 px-4 py-2"
          style={{ borderTop: "0.5px solid var(--border-subtle)" }}
        >
          <span className="mono-data-sm flex items-center gap-1" style={{ color: "var(--text-ghost)" }}>
            <Command size={10} />K to toggle
          </span>
          <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>↑↓ navigate</span>
          <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>↵ select</span>
        </div>
      </div>
    </>
  );
}
