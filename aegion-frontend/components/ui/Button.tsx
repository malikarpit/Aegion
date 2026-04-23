"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";
import { Loader2 } from "lucide-react";

/* ══════════════════════════════════════════════════════════════
   BUTTON — Design Token Variant System
   ══════════════════════════════════════════════════════════════ */

const variantStyles: Record<string, React.CSSProperties> = {
  primary: {
    background: "var(--gradient-primary)",
    color: "white",
    boxShadow: "0 4px 20px hsla(260, 100%, 50%, 0.2)",
  },
  secondary: {
    background: "hsla(260, 20%, 80%, 0.05)",
    color: "var(--text-primary)",
    border: "1px solid var(--border-default)",
  },
  ghost: {
    background: "transparent",
    color: "var(--text-secondary)",
  },
  danger: {
    background: "hsla(350, 90%, 62%, 0.08)",
    color: "var(--accent-risk)",
    border: "1px solid hsla(350, 90%, 62%, 0.20)",
  },
  success: {
    background: "hsla(150, 90%, 55%, 0.08)",
    color: "var(--accent-trust)",
    border: "1px solid hsla(150, 90%, 55%, 0.20)",
  },
};

const sizes = {
  sm: "px-3 py-1.5 text-xs rounded-lg gap-1.5",
  md: "px-4 py-2.5 text-sm rounded-xl gap-2",
  lg: "px-6 py-3 text-base rounded-xl gap-2.5",
} as const;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variantStyles;
  size?: keyof typeof sizes;
  loading?: boolean;
  icon?: React.ReactNode;
  iconRight?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      loading = false,
      icon,
      iconRight,
      children,
      className = "",
      disabled,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={`
          inline-flex items-center justify-center font-medium
          transition-all duration-200 active:scale-[0.97]
          disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100
          hover:brightness-110
          ${sizes[size]} ${className}
        `}
        style={variantStyles[variant] || variantStyles.primary}
        {...props}
      >
        {loading ? (
          <Loader2 size={size === "sm" ? 14 : 16} className="animate-spin" />
        ) : (
          icon
        )}
        {children}
        {iconRight}
      </button>
    );
  }
);

Button.displayName = "Button";
