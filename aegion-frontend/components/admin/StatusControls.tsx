"use client";

import { useState } from "react";
import api from "@/lib/api";
import { Shield, CloudOff, Power, RefreshCw } from "lucide-react";

export function StatusControls() {
    const [loading, setLoading] = useState(false);
    const [frozen, setFrozen] = useState(false);
    const [aiEnabled, setAiEnabled] = useState(true);

    // Toggle System Freeze
    const toggleFreeze = async () => {
        setLoading(true);
        try {
            if (frozen) {
                await api.post("/governance/unfreeze");
                setFrozen(false);
            } else {
                await api.post("/governance/freeze", { reason: "Admin Manual Action" });
                setFrozen(true);
            }
        } catch (err) {
            console.error("Failed to toggle freeze", err);
            alert("Failed to update freeze state. Check console/permissions.");
        } finally {
            setLoading(false);
        }
    };

    // Toggle Workspace AI
    const toggleAI = async () => {
        setLoading(true);
        try {
            await api.post("/governance/workspaces/default/ai-toggle", {
                enabled: !aiEnabled,
                reason: "Admin Component Toggle"
            });
            setAiEnabled(!aiEnabled);
        } catch (err) {
            console.error("Failed to toggle AI", err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            {/* Freeze Control */}
            <div
                className="p-6 rounded-2xl"
                style={{
                    background: frozen ? "hsla(350, 90%, 62%, 0.06)" : "hsla(260, 20%, 80%, 0.03)",
                    border: frozen ? "1px solid hsla(350, 90%, 62%, 0.30)" : "1px solid var(--border-default)",
                }}
            >
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-lg flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
                        <Shield style={{ color: frozen ? "var(--accent-risk)" : "var(--accent-trust)" }} />
                        System Integrity
                    </h3>
                    <span
                        className="text-xs px-2 py-1 rounded-full"
                        style={{
                            border: frozen ? "1px solid var(--accent-risk)" : "1px solid var(--accent-trust)",
                            color: frozen ? "var(--accent-risk)" : "var(--accent-trust)",
                        }}
                    >
                        {frozen ? "FROZEN" : "ACTIVE"}
                    </span>
                </div>
                <p className="text-sm mb-6 min-h-[40px]" style={{ color: "var(--text-secondary)" }}>
                    {frozen ? "All mutations blocked. System is in panic mode." : "System is writable. Governance checks active."}
                </p>
                <button
                    onClick={toggleFreeze}
                    disabled={loading}
                    className="w-full py-2 rounded-lg font-medium transition-colors"
                    style={{
                        background: frozen ? "var(--accent-risk)" : "hsla(260, 20%, 80%, 0.08)",
                        color: frozen ? "white" : "var(--text-primary)",
                    }}
                >
                    {frozen ? "Deactivate Freeze" : "Activate Freeze"}
                </button>
            </div>

            {/* AI Toggle */}
            <div
                className="p-6 rounded-2xl"
                style={{
                    background: !aiEnabled ? "hsla(42, 100%, 60%, 0.06)" : "hsla(260, 20%, 80%, 0.03)",
                    border: !aiEnabled ? "1px solid hsla(42, 100%, 60%, 0.30)" : "1px solid var(--border-default)",
                }}
            >
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-lg flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
                        <Power style={{ color: aiEnabled ? "var(--accent-reason)" : "var(--status-warning)" }} />
                        AI Council
                    </h3>
                    <span
                        className="text-xs px-2 py-1 rounded-full"
                        style={{
                            border: aiEnabled ? "1px solid var(--accent-reason)" : "1px solid var(--status-warning)",
                            color: aiEnabled ? "var(--accent-reason)" : "var(--status-warning)",
                        }}
                    >
                        {aiEnabled ? "ONLINE" : "OFFLINE"}
                    </span>
                </div>
                <p className="text-sm mb-6 min-h-[40px]" style={{ color: "var(--text-secondary)" }}>
                    {aiEnabled ? "AI is actively proposing and reviewing." : "AI assistance disabled for this workspace."}
                </p>
                <button
                    onClick={toggleAI}
                    disabled={loading}
                    className="w-full py-2 rounded-lg font-medium transition-colors"
                    style={{
                        background: aiEnabled ? "hsla(260, 20%, 80%, 0.08)" : "var(--status-warning)",
                        color: aiEnabled ? "var(--text-primary)" : "var(--text-inverse)",
                    }}
                >
                    {aiEnabled ? "Disable AI" : "Enable AI"}
                </button>
            </div>

            {/* Manual Rollback */}
            <div
                className="p-6 rounded-2xl"
                style={{ background: "hsla(260, 20%, 80%, 0.03)", border: "1px solid var(--border-default)" }}
            >
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-lg flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                        <RefreshCw />
                        Emergency Reset
                    </h3>
                </div>
                <p className="text-sm mb-6 min-h-[40px]" style={{ color: "var(--text-secondary)" }}>
                    Force rollback to last known stable checkpoint. DANGEROUS.
                </p>
                <button
                    className="w-full py-2 rounded-lg font-medium transition-all"
                    style={{
                        background: "hsla(260, 20%, 80%, 0.04)",
                        color: "var(--text-muted)",
                        border: "1px solid transparent",
                    }}
                >
                    Initiate Rollback...
                </button>
            </div>
        </div>
    );
}
