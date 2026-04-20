"use client";

import { useEffect } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[Aegion] Dashboard error:", error);
  }, [error]);

  return (
    <div className="flex items-center justify-center min-h-[60vh] px-6">
      <div className="glass-l2 p-8 rounded-xl max-w-md text-center">
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4"
          style={{ background: "hsla(350, 90%, 62%, 0.1)" }}
        >
          <AlertTriangle size={24} style={{ color: "var(--accent-risk)" }} />
        </div>
        <h2
          className="text-[18px] font-semibold mb-2"
          style={{ color: "var(--text-primary)" }}
        >
          System Disruption
        </h2>
        <p
          className="text-[14px] mb-6 leading-relaxed"
          style={{ color: "var(--text-secondary)" }}
        >
          {error.message || "An unexpected error occurred in the dashboard."}
        </p>
        <button
          onClick={reset}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-[14px] font-medium transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
          style={{
            background: "var(--gradient-primary)",
            color: "white",
          }}
        >
          <RotateCcw size={14} />
          Retry
        </button>
        {error.digest && (
          <p className="mono-data-sm mt-4" style={{ color: "var(--text-ghost)" }}>
            Digest: {error.digest}
          </p>
        )}
      </div>
    </div>
  );
}
