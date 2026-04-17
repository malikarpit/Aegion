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
            await new Promise(r => setTimeout(r, 1000)); // Mock delay
            alert("Policy updated (Simulation)");
        } catch (err) {
            alert("Invalid JSON or Backend Error");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div
            className="w-full h-full flex flex-col rounded-xl overflow-hidden"
            style={{ background: "hsla(260, 20%, 80%, 0.03)", border: "1px solid var(--border-default)" }}
        >
            <div
                className="flex items-center justify-between px-6 py-4"
                style={{ borderBottom: "1px solid var(--border-default)", background: "hsla(248, 10%, 3%, 0.3)" }}
            >
                <h3 className="font-semibold" style={{ color: "var(--text-primary)" }}>Active Doctrine (JSON)</h3>
                <button
                    onClick={handleSave}
                    disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                    style={{
                        background: "var(--gradient-primary)",
                        color: "white",
                        boxShadow: "0 4px 16px hsla(260, 100%, 50%, 0.15)",
                    }}
                >
                    <Save size={16} />
                    {loading ? "Saving..." : "Update Doctrine"}
                </button>
            </div>

            <div className="relative flex-1">
                <textarea
                    className="w-full h-full font-mono text-sm p-6 focus:outline-none resize-none"
                    style={{
                        background: "hsla(248, 10%, 3%, 0.4)",
                        color: "var(--accent-trust)",
                    }}
                    value={policy}
                    onChange={(e) => setPolicy(e.target.value)}
                    spellCheck={false}
                />

                <div
                    className="absolute bottom-4 right-6 flex items-center gap-2 text-xs px-3 py-1.5 rounded-full"
                    style={{
                        color: "var(--status-warning)",
                        background: "hsla(42, 100%, 60%, 0.06)",
                        border: "1px solid hsla(42, 100%, 60%, 0.15)",
                    }}
                >
                    <AlertTriangle size={12} />
                    <span>Changes apply immediately to all Agents</span>
                </div>
            </div>
        </div>
    );
}
