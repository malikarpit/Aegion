"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard,
  Network,
  MessageSquare,
  Clock,
  FileCheck,
  Settings,
  DollarSign,
  Brain,
  Puzzle,
  FileText,
  ShieldAlert,
  LogOut,
  User,
  ChevronDown,
  Swords,
  ListTodo,
  BarChart3,
  Shield,
  Focus,
  Cpu,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useState } from "react";
import { useSystemContext, useFocusMode } from "@/lib/context/SystemContext";

/* ══════════════════════════════════════════════════════════════
   SIDEBAR — Cognitive Navigation System
   
   Not a static menu — a context-aware navigation.
   - Sections reveal/hide based on cognitive mode
   - Pending badges from SystemContext (real-time)
   - Mode indicator dot
   - Focus mode hides sidebar entirely
   ══════════════════════════════════════════════════════════════ */

interface NavItem {
  href: string;
  label: string;
  icon: React.ElementType;
  badgeKey?: "pendingApprovals" | "activeAlerts";
}

interface NavSectionData {
  title: string;
  items: NavItem[];
}

const sections: NavSectionData[] = [
  {
    title: "Lenses",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/dashboard/council", label: "Council", icon: MessageSquare },
      { href: "/dashboard/proposals", label: "Proposals", icon: FileCheck, badgeKey: "pendingApprovals" },
      { href: "/dashboard/timeline", label: "Timeline", icon: Clock },
    ],
  },
  {
    title: "Intelligence",
    items: [
      { href: "/dashboard/knowledge", label: "Knowledge", icon: Network },
      { href: "/dashboard/memory", label: "Memory", icon: Brain },
      { href: "/dashboard/risk", label: "Risk & Sentinel", icon: Shield, badgeKey: "activeAlerts" },
      { href: "/dashboard/cost", label: "Cost", icon: DollarSign },
    ],
  },
  {
    title: "Operations",
    items: [
      { href: "/dashboard/skills", label: "Skills", icon: Puzzle },
      { href: "/dashboard/tasks", label: "Tasks", icon: ListTodo },
      { href: "/dashboard/warroom", label: "War Room", icon: Swords },
      { href: "/dashboard/adrs", label: "ADRs", icon: FileText },
    ],
  },
  {
    title: "System",
    items: [
      { href: "/dashboard/models", label: "Models", icon: Cpu },
      { href: "/admin", label: "Admin", icon: ShieldAlert },
      { href: "/dashboard/settings", label: "Settings", icon: Settings },
    ],
  },
];

function SidebarSection({
  section,
  pathname,
  badges,
}: {
  section: NavSectionData;
  pathname: string;
  badges: Record<string, number>;
}) {
  const [open, setOpen] = useState(true);

  return (
    <div className="mb-1">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full px-3 py-2 hud-label hover:opacity-80 transition-opacity"
      >
        {section.title}
        <ChevronDown
          size={10}
          className={`transition-transform duration-200 ${open ? "" : "-rotate-90"}`}
          style={{ color: "var(--text-ghost)" }}
        />
      </button>

      {open && (
        <div className="space-y-0.5">
          {section.items.map((item) => {
            const isActive =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            const badgeCount = item.badgeKey ? badges[item.badgeKey] ?? 0 : 0;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`
                  flex items-center gap-2.5 px-3 py-2 rounded-lg transition-all duration-150 group mx-1 text-[13px]
                  ${
                    isActive
                      ? "font-medium"
                      : "hover:bg-[var(--surface-hover)]"
                  }
                `}
                style={{
                  color: isActive ? "var(--text-primary)" : "var(--text-muted)",
                  background: isActive
                    ? "var(--surface-hover)"
                    : undefined,
                  borderLeft: isActive
                    ? "2px solid var(--accent-reason)"
                    : "2px solid transparent",
                }}
              >
                <Icon
                  size={15}
                  style={{
                    color: isActive ? "var(--accent-reason)" : "var(--text-ghost)",
                  }}
                  className="group-hover:opacity-100 transition-opacity"
                />
                <span>{item.label}</span>

                {badgeCount > 0 && (
                  <span
                    className="ml-auto mono-data-sm px-1.5 py-[1px] rounded-full"
                    style={{
                      background: "var(--tier-2-bg)",
                      color: "var(--tier-2)",
                      fontSize: "10px",
                    }}
                  >
                    {badgeCount}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, signOut } = useAuth();
  const { state } = useSystemContext();
  const [focusMode] = useFocusMode();

  // Focus mode hides sidebar completely
  if (focusMode) return null;

  const badges: Record<string, number> = {
    pendingApprovals: state.governance.pendingApprovals,
    activeAlerts: state.risk.activeAlerts,
  };

  const currentMode = state.session?.mode ?? "explore";

  return (
    <aside
      id="sidebar"
      className="w-64 h-screen flex flex-col fixed left-0 top-0 z-30"
      style={{
        background: "var(--surface-0)",
        borderRight: "0.5px solid var(--border-subtle)",
      }}
    >
      {/* Logo & Session */}
      <div
        className="p-4 pb-3"
        style={{ borderBottom: "0.5px solid var(--border-subtle)" }}
      >
        <div className="flex items-center gap-2 mb-2">
          <h1 className="text-[18px] font-semibold gradient-text">Aegion</h1>
          <span className="hud-label" style={{ color: "var(--text-ghost)" }}>
            v0.1
          </span>
        </div>

        {/* Session indicator */}
        {state.session ? (
          <div className="flex items-center gap-1.5">
            <div
              className="status-dot-pulse"
              style={{
                background:
                  state.session.status === "active"
                    ? "var(--status-success)"
                    : "var(--status-warning)",
                width: 6,
                height: 6,
              }}
            />
            <span
              className="text-[12px] truncate"
              style={{ color: "var(--text-secondary)" }}
            >
              {state.session.name}
            </span>
          </div>
        ) : (
          <span className="text-[11px]" style={{ color: "var(--text-ghost)" }}>
            No active session
          </span>
        )}

        {/* Mode indicator */}
        <div className="flex items-center gap-1 mt-1.5">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: `var(--mode-${currentMode})` }}
          />
          <span className="hud-label" style={{ color: `var(--mode-${currentMode})` }}>
            {currentMode.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 overflow-y-auto smooth-scroll">
        {sections.map((section) => (
          <SidebarSection
            key={section.title}
            section={section}
            pathname={pathname}
            badges={badges}
          />
        ))}
      </nav>

      {/* Focus Mode Toggle */}
      <div
        className="px-3 py-2"
        style={{ borderTop: "0.5px solid var(--border-subtle)" }}
      >
        <button
          onClick={() => {
            const { toggleFocus } = state as unknown as { toggleFocus?: () => void };
            // Focus mode is toggled through FocusModeController (⌘.)
          }}
          className="flex items-center gap-2 w-full px-2 py-1.5 rounded-md hover:bg-[var(--surface-hover)] transition-colors"
        >
          <Focus size={13} style={{ color: "var(--text-ghost)" }} />
          <span className="text-[12px]" style={{ color: "var(--text-ghost)" }}>
            Focus ⌘.
          </span>
        </button>
      </div>

      {/* User Footer */}
      <div
        className="p-3"
        style={{ borderTop: "0.5px solid var(--border-subtle)" }}
      >
        <div
          className="flex items-center gap-2.5 p-2 rounded-lg mb-2"
          style={{
            background: "var(--surface-2)",
            border: "0.5px solid var(--border-subtle)",
          }}
        >
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold"
            style={{ background: "var(--gradient-primary)", color: "white" }}
          >
            {user?.email?.[0]?.toUpperCase() || <User size={12} />}
          </div>
          <div className="flex-1 min-w-0">
            <p
              className="text-[13px] font-medium truncate"
              style={{ color: "var(--text-primary)" }}
            >
              {user?.displayName || "User"}
            </p>
            <p
              className="text-[11px] truncate"
              style={{ color: "var(--text-ghost)" }}
            >
              {user?.email}
            </p>
          </div>
        </div>

        <button
          onClick={signOut}
          className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-[12px] font-medium rounded-md hover:bg-[var(--surface-hover)] transition-colors"
          style={{ color: "var(--accent-risk)" }}
        >
          <LogOut size={12} />
          Sign Out
        </button>
      </div>
    </aside>
  );
}
