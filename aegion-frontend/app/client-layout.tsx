"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { ToastProvider } from "@/components/ui/Toast";
import { SystemContextProvider, useSystemContext } from "@/lib/context/SystemContext";
import { SystemStateBar } from "@/components/cognitive/SystemStateBar";
import { DegradedBanner } from "@/components/cognitive/DegradedBanner";
import { CommandPalette } from "@/components/ui/CommandPalette";

/* ══════════════════════════════════════════════════════════════
   CLIENT LAYOUT — State-aware shell
   
   Sets data-page, data-mode, data-density on content container.
   Renders SystemStateBar + DegradedBanner above all page content.
   Wraps everything in SystemContextProvider.
   ══════════════════════════════════════════════════════════════ */

const PAGE_DENSITY: Record<string, string> = {
  "/dashboard": "wide",
  "/dashboard/council": "focused",
  "/dashboard/proposals": "wide",
  "/dashboard/timeline": "wide",
  "/dashboard/cost": "wide",
  "/dashboard/knowledge": "wide",
  "/dashboard/memory": "wide",
  "/dashboard/settings": "dense",
  "/dashboard/skills": "wide",
  "/dashboard/tasks": "wide",
  "/dashboard/adrs": "dense",
  "/dashboard/models": "dense",
  "/dashboard/warroom": "focused",
  "/dashboard/risk": "wide",
  "/admin": "dense",
};

function extractPageName(pathname: string): string {
  // /dashboard/council → council, /dashboard → dashboard, / → landing
  if (pathname === "/") return "landing";
  const segments = pathname.split("/").filter(Boolean);
  return segments[segments.length - 1] || "dashboard";
}

function LayoutInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { state } = useSystemContext();

  const isAuthPage = pathname === "/login" || pathname === "/signup";
  const isLanding = pathname === "/";
  const showChrome = !isAuthPage && !isLanding;

  const pageName = extractPageName(pathname);
  const currentMode = state.session?.mode ?? "explore";
  const density = state.focusMode
    ? "minimal"
    : PAGE_DENSITY[pathname] ?? "wide";

  return (
    <div className="flex h-screen overflow-hidden">
      {showChrome && <Sidebar />}
      <div
        className={`flex-1 flex flex-col overflow-hidden ${showChrome ? "pl-64" : ""}`}
        data-page={pageName}
        data-mode={currentMode}
        data-density={density}
      >
        {/* Degraded banner (conditional) */}
        {showChrome && <DegradedBanner />}

        {/* System state bar (always visible on app pages) */}
        {showChrome && <SystemStateBar />}

        {/* Page content with background gradient */}
        <main
          className={`flex-1 overflow-auto relative page-background ${
            showChrome ? "" : ""
          }`}
        >
          <div className="relative z-10 animate-page-enter">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

export function ClientLayout({ children }: { children: React.ReactNode }) {
  return (
    <SystemContextProvider>
      <ToastProvider>
        <CommandPalette />
        <LayoutInner>{children}</LayoutInner>
      </ToastProvider>
    </SystemContextProvider>
  );
}
