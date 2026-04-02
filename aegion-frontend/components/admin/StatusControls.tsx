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
            // Using default workspace for now
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
            <div className={`p-6 rounded-2xl border ${frozen ? "bg-red-500/10 border-red-500/50" : "bg-white/5 border-white/10"}`}>
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-lg flex items-center gap-2">
                        <Shield className={frozen ? "text-red-400" : "text-green-400"} />
                        System Integrity
                    </h3>
                    <span className={`text-xs px-2 py-1 rounded-full border ${frozen ? "border-red-500 text-red-400" : "border-green-500 text-green-400"}`}>
                        {frozen ? "FROZEN" : "ACTIVE"}
                    </span>
                </div>
                <p className="text-sm text-slate-400 mb-6 min-h-[40px]">
                    {frozen ? "All mutations blocked. System is in panic mode." : "System is writable. Governance checks active."}
                </p>
                <button
                    onClick={toggleFreeze}
                    disabled={loading}
                    className={`w-full py-2 rounded-lg font-medium transition-colors ${frozen ? "bg-red-500 hover:bg-red-600 text-white" : "bg-white/10 hover:bg-white/20 text-white"}`}
                >
                    {frozen ? "Deactivate Freeze" : "Activate Freeze"}
                </button>
            </div>

            {/* AI Toggle */}
            <div className={`p-6 rounded-2xl border ${!aiEnabled ? "bg-yellow-500/10 border-yellow-500/50" : "bg-white/5 border-white/10"}`}>
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-lg flex items-center gap-2">
                        <Power className={aiEnabled ? "text-blue-400" : "text-yellow-400"} />
                        AI Council
                    </h3>
                    <span className={`text-xs px-2 py-1 rounded-full border ${aiEnabled ? "border-blue-500 text-blue-400" : "border-yellow-500 text-yellow-400"}`}>
                        {aiEnabled ? "ONLINE" : "OFFLINE"}
                    </span>
                </div>
                <p className="text-sm text-slate-400 mb-6 min-h-[40px]">
                    {aiEnabled ? "AI is actively proposing and reviewing." : "AI assistance disabled for this workspace."}
                </p>
                <button
                    onClick={toggleAI}
                    disabled={loading}
                    className={`w-full py-2 rounded-lg font-medium transition-colors ${aiEnabled ? "bg-white/10 hover:bg-white/20" : "bg-yellow-500 hover:bg-yellow-600 text-black"}`}
                >
                    {aiEnabled ? "Disable AI" : "Enable AI"}
                </button>
            </div>

            {/* Manual Rollback */}
            <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-lg flex items-center gap-2 text-slate-300">
                        <RefreshCw />
                        Emergency Reset
                    </h3>
                </div>
                <p className="text-sm text-slate-400 mb-6 min-h-[40px]">
                    Force rollback to last known stable checkpoint. DANGEROUS.
                </p>
                <button
                    className="w-full py-2 rounded-lg font-medium bg-white/5 hover:bg-red-500/20 hover:text-red-400 border border-transparent hover:border-red-500/50 transition-all text-slate-400"
                >
                    Initiate Rollback...
                </button>
            </div>
        </div>
    );
}
