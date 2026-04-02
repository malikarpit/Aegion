"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { Save, AlertTriangle } from "lucide-react";

export function DoctrineEditor() {
    const [policy, setPolicy] = useState<string>("");
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        // Fetch initial policy
        api.get("/governance/policy")
            .then(res => setPolicy(JSON.stringify(res.data, null, 2)))
            .catch(err => console.error("Failed to load policy", err));
    }, []);

    const handleSave = async () => {
        setLoading(true);
        try {
            // TODO: Backend needs a SET policy endpoint (not currently in v1 spec but planned)
            // For now we just mock the save or call a hypothetical update endpoint
            // await api.put("/governance/policy", JSON.parse(policy));
            await new Promise(r => setTimeout(r, 1000)); // Mock delay
            alert("Policy updated (Simulation)");
        } catch (err) {
            alert("Invalid JSON or Backend Error");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="w-full h-full flex flex-col bg-white/5 border border-white/10 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-black/20">
                <h3 className="font-semibold text-white">Active Doctrine (JSON)</h3>
                <button
                    onClick={handleSave}
                    disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
                >
                    <Save size={16} />
                    {loading ? "Saving..." : "Update Doctrine"}
                </button>
            </div>

            <div className="relative flex-1">
                <textarea
                    className="w-full h-full bg-black/50 text-emerald-400 font-mono text-sm p-6 focus:outline-none resize-none"
                    value={policy}
                    onChange={(e) => setPolicy(e.target.value)}
                    spellCheck={false}
                />

                <div className="absolute bottom-4 right-6 flex items-center gap-2 text-xs text-yellow-400 bg-yellow-500/10 px-3 py-1.5 rounded-full border border-yellow-500/20">
                    <AlertTriangle size={12} />
                    <span>Changes apply immediately to all Agents</span>
                </div>
            </div>
        </div>
    );
}
