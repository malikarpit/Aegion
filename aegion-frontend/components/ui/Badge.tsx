"use client";

import { ReactNode } from "react";

/* ══════════════════════════════════════════════════════════════
   BADGE — Design Token Variant System
   ══════════════════════════════════════════════════════════════ */

const variants: Record<string, React.CSSProperties> = {
  success: { background: "hsla(150, 90%, 55%, 0.08)", color: "var(--status-success)", borderColor: "hsla(150, 90%, 55%, 0.20)" },
  warning: { background: "hsla(42, 100%, 60%, 0.08)", color: "var(--status-warning)", borderColor: "hsla(42, 100%, 60%, 0.20)" },
  danger:  { background: "hsla(350, 90%, 62%, 0.08)", color: "var(--status-error)", borderColor: "hsla(350, 90%, 62%, 0.20)" },
  info:    { background: "hsla(260, 100%, 70%, 0.08)", color: "var(--status-info)", borderColor: "hsla(260, 100%, 70%, 0.20)" },
  neutral: { background: "hsla(250, 10%, 80%, 0.05)", color: "var(--text-secondary)", borderColor: "var(--border-default)" },
  purple:  { background: "hsla(280, 85%, 65%, 0.08)", color: "var(--accent-govern)", borderColor: "hsla(280, 85%, 65%, 0.20)" },
};

const sizes = {
  sm: "px-2 py-0.5 text-[10px]",
  md: "px-2.5 py-1 text-xs",
  lg: "px-3 py-1.5 text-sm",
} as const;

interface BadgeProps {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
  dot?: boolean;
  pulse?: boolean;
  children: ReactNode;
  className?: string;
}

export function Badge({
  variant = "neutral",
  size = "md",
  dot = false,
  pulse = false,
  children,
  className = "",
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${sizes[size]} ${className}`}
      style={variants[variant] || variants.neutral}
    >
      {dot && (
        <span className="relative flex h-1.5 w-1.5">
          {pulse && (
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-40 bg-current" />
          )}
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-current" />
        </span>
      )}
      {children}
    </span>
  );
}
