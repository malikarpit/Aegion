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
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 mb-6">
                    <AlertTriangle className="w-8 h-8 text-red-400" />
                </div>
                <h2 className="text-xl font-bold text-white mb-2">Something went wrong</h2>
                <p className="text-sm text-slate-400 mb-6">
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
