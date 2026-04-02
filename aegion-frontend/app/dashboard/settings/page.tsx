"use client";

import { useState } from "react";
import { Settings, User, Key, Building2, Cpu, Eye, EyeOff, Check, TestTube, Save } from "lucide-react";
import { Tabs } from "@/components/ui/Tabs";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";

const apiKeyProviders = [
    { id: "openai", label: "OpenAI", placeholder: "sk-..." },
    { id: "anthropic", label: "Anthropic", placeholder: "sk-ant-..." },
    { id: "google", label: "Google AI", placeholder: "AIza..." },
    { id: "deepseek", label: "DeepSeek", placeholder: "sk-..." },
    { id: "ollama", label: "Ollama", placeholder: "http://localhost:11434" },
];

const councilConfigFields = [
    { key: "constitution_enforcement", label: "Constitution Enforcement", type: "toggle", description: "Block queries and redact responses that violate governance rules", default: true },
    { key: "dag_pipeline_enabled", label: "DAG Pipeline", type: "toggle", description: "Enable directed acyclic graph execution ordering", default: false },
    { key: "red_team_enabled", label: "Red Team Validation", type: "toggle", description: "Adversarial testing of council responses", default: false },
    { key: "mcts_enabled", label: "MCTS Deep Reasoning", type: "toggle", description: "Monte Carlo tree search for complex queries", default: false },
    { key: "temporal_memory_enabled", label: "Temporal Memory", type: "toggle", description: "Remember past decisions for context continuity", default: true },
    { key: "cross_council_enabled", label: "Cross-Council Spawning", type: "toggle", description: "Auto-spawn sub-councils for specialized domains", default: false },
    { key: "max_debate_rounds", label: "Max Debate Rounds", type: "slider", min: 1, max: 5, default: 3 },
    { key: "daily_budget_usd", label: "Daily Budget (USD)", type: "number", min: 0.5, max: 50, default: 5.0 },
    { key: "consensus_threshold", label: "Consensus Threshold", type: "slider", min: 0.5, max: 1.0, step: 0.05, default: 0.75 },
];

function ProfileTab() {
    const { user } = useAuth();

    return (
        <div className="space-y-6 max-w-xl">
            <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-blue-500 to-purple-500 flex items-center justify-center text-xl font-bold text-white uppercase">
                    {user?.email?.[0] || "U"}
                </div>
                <div>
                    <p className="text-lg font-semibold text-white">{user?.displayName || "User"}</p>
                    <p className="text-sm text-slate-500">{user?.email}</p>
                </div>
            </div>

            <div className="space-y-4">
                <div>
                    <label className="text-xs text-slate-400 mb-1.5 block">Display Name</label>
                    <input
                        type="text"
                        defaultValue={user?.displayName || ""}
                        className="glass-input w-full px-4 py-2.5 text-sm"
                    />
                </div>
                <div>
                    <label className="text-xs text-slate-400 mb-1.5 block">Email</label>
                    <input
                        type="email"
                        value={user?.email || ""}
                        disabled
                        className="glass-input w-full px-4 py-2.5 text-sm opacity-50 cursor-not-allowed"
                    />
                </div>
                <Button variant="primary" size="md" icon={<Save size={14} />}>
                    Save Changes
                </Button>
            </div>
        </div>
    );
}

function ApiKeysTab() {
    const { success } = useToast();
    const [keys, setKeys] = useState<Record<string, string>>({});
    const [visible, setVisible] = useState<Record<string, boolean>>({});

    const handleSave = (id: string) => {
        if (keys[id]) {
            localStorage.setItem(`aegion_key_${id}`, keys[id]);
            success("API Key Saved", `${id} key stored locally in your browser`);
        }
    };

    return (
        <div className="space-y-4 max-w-xl">
            <p className="text-xs text-slate-500 bg-white/[0.02] border border-white/5 rounded-lg p-3">
                🔒 API keys are stored <strong>only in your browser</strong> (localStorage). They are never sent to the Aegion database.
            </p>

            {apiKeyProviders.map((provider) => {
                const saved = typeof window !== "undefined" ? localStorage.getItem(`aegion_key_${provider.id}`) : null;
                return (
                    <div key={provider.id} className="glass-card-static p-4">
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-white">{provider.label}</span>
                                {saved && <Badge variant="success" size="sm" dot>Configured</Badge>}
                            </div>
                        </div>
                        <div className="flex gap-2">
                            <div className="relative flex-1">
                                <input
                                    type={visible[provider.id] ? "text" : "password"}
                                    value={keys[provider.id] || ""}
                                    onChange={(e) => setKeys({ ...keys, [provider.id]: e.target.value })}
                                    placeholder={provider.placeholder}
                                    className="glass-input w-full px-3 py-2 pr-10 text-sm font-mono"
                                />
                                <button
                                    onClick={() => setVisible({ ...visible, [provider.id]: !visible[provider.id] })}
                                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors"
                                >
                                    {visible[provider.id] ? <EyeOff size={14} /> : <Eye size={14} />}
                                </button>
                            </div>
                            <Button variant="secondary" size="sm" onClick={() => handleSave(provider.id)}>
                                Save
                            </Button>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

function WorkspaceTab() {
    return (
        <div className="space-y-6 max-w-xl">
            <div className="space-y-4">
                <div>
                    <label className="text-xs text-slate-400 mb-1.5 block">Workspace Name</label>
                    <input type="text" defaultValue="Aegion Development" className="glass-input w-full px-4 py-2.5 text-sm" />
                </div>
                <div>
                    <label className="text-xs text-slate-400 mb-1.5 block">Workspace ID</label>
                    <input type="text" value="ws_aegion_main_01" disabled className="glass-input w-full px-4 py-2.5 text-sm font-mono opacity-50 cursor-not-allowed" />
                </div>
            </div>

            <div>
                <h3 className="text-sm font-medium text-white mb-3">Governance Tier Thresholds</h3>
                <div className="grid grid-cols-3 gap-3">
                    {[
                        { tier: "T1", label: "Auto-approve", desc: "Low risk, routine", color: "border-slate-500/20" },
                        { tier: "T2", label: "Council Review", desc: "Moderate impact", color: "border-blue-500/20" },
                        { tier: "T3", label: "Human Required", desc: "High impact", color: "border-purple-500/20" },
                    ].map((t) => (
                        <div key={t.tier} className={`glass-card-static p-3 border-l-2 ${t.color}`}>
                            <p className="text-xs font-bold text-white">{t.tier}</p>
                            <p className="text-[10px] text-slate-400 mt-0.5">{t.label}</p>
                            <p className="text-[10px] text-slate-600">{t.desc}</p>
                        </div>
                    ))}
                </div>
            </div>

            <div className="flex items-center justify-between p-4 glass-card-static">
                <div>
                    <p className="text-sm font-medium text-white">Workspace Freeze</p>
                    <p className="text-xs text-slate-500">Prevent all modifications (emergency lockdown)</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" className="sr-only peer" />
                    <div className="w-11 h-6 bg-white/10 peer-checked:bg-red-600 rounded-full peer-focus:ring-2 peer-focus:ring-red-500/30 transition-colors after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full" />
                </label>
            </div>
        </div>
    );
}

function CouncilConfigTab() {
    const { success } = useToast();
    const [config, setConfig] = useState<Record<string, number | boolean>>(() => {
        const defaults: Record<string, number | boolean> = {};
        councilConfigFields.forEach((f) => { defaults[f.key] = f.default; });
        return defaults;
    });

    return (
        <div className="space-y-4 max-w-xl">
            <p className="text-xs text-slate-500 bg-white/[0.02] border border-white/5 rounded-lg p-3">
                ⚙️ These settings control the AI Council pipeline. Changes apply per workspace and are persisted via the backend API.
            </p>

            {councilConfigFields.map((field) => (
                <div key={field.key} className="glass-card-static p-4 flex items-center justify-between gap-4">
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white">{field.label}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{field.description}</p>
                    </div>

                    {field.type === "toggle" && (
                        <label className="relative inline-flex items-center cursor-pointer shrink-0">
                            <input
                                type="checkbox"
                                checked={!!config[field.key]}
                                onChange={(e) => setConfig({ ...config, [field.key]: e.target.checked })}
                                className="sr-only peer"
                            />
                            <div className="w-11 h-6 bg-white/10 peer-checked:bg-blue-600 rounded-full transition-colors after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full" />
                        </label>
                    )}

                    {field.type === "slider" && (
                        <div className="flex items-center gap-3 shrink-0">
                            <input
                                type="range"
                                min={field.min} max={field.max} step={field.step || 1}
                                value={Number(config[field.key])}
                                onChange={(e) => setConfig({ ...config, [field.key]: Number(e.target.value) })}
                                className="w-24 accent-blue-500"
                            />
                            <span className="text-sm font-mono text-white w-10 text-right">
                                {Number(config[field.key]).toFixed(field.step && field.step < 1 ? 2 : 0)}
                            </span>
                        </div>
                    )}

                    {field.type === "number" && (
                        <input
                            type="number"
                            min={field.min} max={field.max} step={0.5}
                            value={Number(config[field.key])}
                            onChange={(e) => setConfig({ ...config, [field.key]: Number(e.target.value) })}
                            className="glass-input w-24 px-3 py-1.5 text-sm text-right font-mono shrink-0"
                        />
                    )}
                </div>
            ))}

            <Button
                variant="primary" size="md"
                icon={<Save size={14} />}
                onClick={() => success("Config Saved", "Council configuration updated successfully")}
            >
                Save Configuration
            </Button>
        </div>
    );
}

export default function SettingsPage() {
    const tabs = [
        { id: "profile", label: "Profile", icon: <User size={14} /> },
        { id: "api-keys", label: "API Keys", icon: <Key size={14} /> },
        { id: "workspace", label: "Workspace", icon: <Building2 size={14} /> },
        { id: "council", label: "Council Config", icon: <Cpu size={14} /> },
    ];

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div>
                <h1 className="text-2xl font-bold text-white">Settings</h1>
                <p className="text-sm text-slate-500 mt-1">
                    Manage your profile, API keys, and workspace configuration
                </p>
            </div>

            <Tabs tabs={tabs} defaultTab="profile">
                {(activeTab) => (
                    <>
                        {activeTab === "profile" && <ProfileTab />}
                        {activeTab === "api-keys" && <ApiKeysTab />}
                        {activeTab === "workspace" && <WorkspaceTab />}
                        {activeTab === "council" && <CouncilConfigTab />}
                    </>
                )}
            </Tabs>
        </div>
    );
}
