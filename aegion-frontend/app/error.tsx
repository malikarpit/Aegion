"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";

export default function Error({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    return (
        <div className="flex items-center justify-center min-h-[60vh] p-8">
            <div className="text-center max-w-md">
                <div
                    className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-6"
                    style={{ background: "hsla(350, 90%, 62%, 0.08)", border: "1px solid hsla(350, 90%, 62%, 0.20)" }}
                >
                    <AlertTriangle className="w-8 h-8" style={{ color: "var(--accent-risk)" }} />
                </div>
                <h2 className="text-xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>Something went wrong</h2>
                <p className="text-sm mb-6" style={{ color: "var(--text-secondary)" }}>
                    {error.message || "An unexpected error occurred. Please try again."}
                </p>
                <Button
                    variant="primary"
                    onClick={reset}
                    icon={<RefreshCw size={14} />}
                >
                    Try Again
                </Button>
            </div>
        </div>
    );
}
