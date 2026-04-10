"use client";

import { useState, useCallback } from "react";
import {
    Settings, Cpu, DollarSign, Shield, Brain, Zap, Database,
    Globe, Lock, Bell, Palette, ChevronRight, ChevronDown,
    Save, RotateCcw, Download, Upload, Check, AlertTriangle,
    Layers, GitBranch, Server, Eye, Code, RefreshCw,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";

// ──────────────────────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────────────────────

interface SettingSection {
    id: string;
    label: string;
    icon: any;
    description: string;
    settings: SettingItem[];
}

interface SettingItem {
    path: string;
    label: string;
    description: string;
    type: "toggle" | "select" | "number" | "text" | "slider";
    value: any;
    options?: { label: string; value: any }[];
    min?: number;
    max?: number;
    step?: number;
}

// ──────────────────────────────────────────────────────────────────────────────
// Settings Schema — every Aegion configuration exposed via UI
// ──────────────────────────────────────────────────────────────────────────────

const SECTIONS: SettingSection[] = [
    {
        id: "council",
        label: "Council Kernel",
        icon: Brain,
        description: "Configure the multi-model AI council pipeline",
        settings: [
            { path: "council.default_type", label: "Default Council Type", description: "Primary council for standard queries", type: "select", value: "child", options: [{ label: "Child (Fast)", value: "child" }, { label: "Parent (Deep)", value: "parent" }, { label: "Sentinel (Security)", value: "sentinel" }, { label: "Distillation (Cheap)", value: "distillation" }] },
            { path: "council.default_model_count", label: "Models per Council", description: "Number of models to query in parallel", type: "slider", value: 3, min: 1, max: 7, step: 1 },
            { path: "council.weighted_synthesis", label: "Weighted Synthesis", description: "Use LLM-backed multi-model merge instead of pick-best", type: "toggle", value: true },
            { path: "council.persona_debate", label: "Persona Debate", description: "Enable role-based persona perspectives in parent/sentinel councils", type: "toggle", value: true },
            { path: "council.rubric_scoring", label: "Rubric Scoring", description: "Score responses against quality rubrics", type: "toggle", value: true },
            { path: "council.constitution_enforcement", label: "Constitutional AI", description: "Enforce governance rules on all council outputs", type: "toggle", value: true },
            { path: "council.context_pruning", label: "Context Pruning", description: "Compress conversation history to save tokens", type: "toggle", value: true },
            { path: "council.context_keep_recent", label: "Keep Recent Turns", description: "Number of recent turns to keep verbatim", type: "number", value: 4, min: 1, max: 20 },
        ],
    },
    {
        id: "cascade",
        label: "FrugalGPT Cascade",
        icon: Layers,
        description: "Cost-optimized model fallback chain",
        settings: [
            { path: "cascade.confidence_threshold", label: "Confidence Threshold", description: "Min confidence to accept a tier response (skip to next tier below this)", type: "slider", value: 0.7, min: 0.1, max: 1.0, step: 0.05 },
            { path: "cascade.max_fallback_attempts", label: "Max Fallback Attempts", description: "How many tiers to try before giving up", type: "number", value: 3, min: 1, max: 10 },
            { path: "cascade.tier_0_model", label: "Tier 0 (Cheapest)", description: "First model tried — fastest and cheapest", type: "select", value: "gemini-2.0-flash", options: [{ label: "Gemini 2.0 Flash", value: "gemini-2.0-flash" }, { label: "GPT-4o Mini", value: "gpt-4o-mini" }, { label: "Claude 3.5 Haiku", value: "claude-haiku" }] },
            { path: "cascade.tier_1_model", label: "Tier 1 (Balanced)", description: "Second tier — balanced cost and quality", type: "select", value: "gpt-4o-mini", options: [{ label: "GPT-4o Mini", value: "gpt-4o-mini" }, { label: "Claude 3.5 Sonnet", value: "claude-sonnet-4" }, { label: "Gemini 2.5 Pro", value: "gemini-2.5-pro" }] },
            { path: "cascade.tier_2_model", label: "Tier 2 (Frontier)", description: "Top-tier model — highest quality, highest cost", type: "select", value: "gpt-4o", options: [{ label: "GPT-4o", value: "gpt-4o" }, { label: "Claude Sonnet 4", value: "claude-sonnet-4" }, { label: "Gemini 2.5 Pro", value: "gemini-2.5-pro" }] },
        ],
    },
    {
        id: "budget",
        label: "Budget & Limits",
        icon: DollarSign,
        description: "Control spending limits and auto-pause",
        settings: [
            { path: "budget.monthly_limit_usd", label: "Monthly Budget (USD)", description: "Maximum monthly spend before auto-pause", type: "number", value: 100, min: 0, max: 100000 },
            { path: "budget.daily_limit_usd", label: "Daily Budget (USD)", description: "Maximum daily spend", type: "number", value: 10, min: 0, max: 10000 },
            { path: "budget.auto_pause", label: "Auto-Pause on Limit", description: "Automatically stop API calls when budget is exceeded", type: "toggle", value: true },
            { path: "budget.warning_threshold", label: "Warning Threshold", description: "Alert when budget reaches this percentage", type: "slider", value: 80, min: 50, max: 95, step: 5 },
            { path: "budget.max_cost_per_query", label: "Max Cost per Query (USD)", description: "Hard cap on single query cost", type: "number", value: 0.50, min: 0.01, max: 10 },
        ],
    },
    {
        id: "sentinel",
        label: "Sentinel / Security",
        icon: Shield,
        description: "Security scanning and threat detection",
        settings: [
            { path: "sentinel.auto_scan", label: "Auto Security Scan", description: "Automatically scan all proposals for vulnerabilities", type: "toggle", value: true },
            { path: "sentinel.red_team_enabled", label: "Red Team Validation", description: "Enable adversarial testing of council outputs", type: "toggle", value: false },
            { path: "sentinel.red_team_min_score", label: "Red Team Min Score", description: "Minimum red team score to pass validation", type: "slider", value: 0.7, min: 0.1, max: 1.0, step: 0.05 },
            { path: "sentinel.risk_threshold", label: "Risk Alert Threshold", description: "Score above which to trigger risk alerts", type: "slider", value: 60, min: 10, max: 90, step: 5 },
            { path: "sentinel.block_sensitive_files", label: "Block Sensitive File Changes", description: "Require council approval for .env, auth, migration changes", type: "toggle", value: true },
        ],
    },
    {
        id: "governance",
        label: "Archon Governance",
        icon: Lock,
        description: "Tier system and decision-making rules",
        settings: [
            { path: "governance.auto_approve_t0", label: "Auto-Approve T0", description: "Automatically approve trivial (T0) decisions", type: "toggle", value: true },
            { path: "governance.require_quorum_t2", label: "Require Quorum for T2+", description: "Mandate multi-model consensus for T2 and T3 decisions", type: "toggle", value: true },
            { path: "governance.freeze_enabled", label: "Emergency Freeze", description: "Allow manual governance freeze via API", type: "toggle", value: true },
            { path: "governance.max_decisions_per_hour", label: "Max Decisions/Hour", description: "Rate limit on governance decisions", type: "number", value: 20, min: 1, max: 100 },
            { path: "governance.decision_retention_days", label: "Decision Retention (days)", description: "How long to keep decision history", type: "number", value: 90, min: 7, max: 365 },
        ],
    },
    {
        id: "ghost_text",
        label: "Ghost Text (Inline AI)",
        icon: Code,
        description: "VS Code inline code completion",
        settings: [
            { path: "ghost_text.enabled", label: "Enable Ghost Text", description: "Activate inline AI completions in VS Code", type: "toggle", value: true },
            { path: "ghost_text.max_tokens", label: "Max Completion Tokens", description: "Maximum length of generated completions", type: "number", value: 256, min: 32, max: 1024 },
            { path: "ghost_text.debounce_ms", label: "Debounce (ms)", description: "Wait time before triggering completion", type: "number", value: 300, min: 100, max: 2000 },
            { path: "ghost_text.max_cost_per_completion", label: "Max Cost/Completion", description: "Hard cap per completion request", type: "number", value: 0.01, min: 0.001, max: 0.10 },
            { path: "ghost_text.block_sensitive_files", label: "Block Sensitive Files", description: "Never auto-complete in .env, secret, credential files", type: "toggle", value: true },
        ],
    },
    {
        id: "memory",
        label: "Memory & Knowledge",
        icon: Database,
        description: "Persistent memory and workspace knowledge",
        settings: [
            { path: "memory.auto_learn", label: "Auto-Learn from Decisions", description: "Automatically store decision outcomes as memories", type: "toggle", value: true },
            { path: "memory.max_memories", label: "Max Memories", description: "Maximum memory entries per workspace", type: "number", value: 1000, min: 100, max: 10000 },
            { path: "memory.semantic_search", label: "Semantic Memory Search", description: "Use pgvector for semantic memory retrieval", type: "toggle", value: true },
            { path: "memory.evidence_auto_gather", label: "Auto-Gather Evidence", description: "Automatically gather evidence for council queries", type: "toggle", value: true },
        ],
    },
    {
        id: "notifications",
        label: "Notifications",
        icon: Bell,
        description: "Alert and notification preferences",
        settings: [
            { path: "notifications.budget_alerts", label: "Budget Alerts", description: "Notify on budget threshold events", type: "toggle", value: true },
            { path: "notifications.risk_alerts", label: "Risk Alerts", description: "Notify on high risk scores", type: "toggle", value: true },
            { path: "notifications.governance_alerts", label: "Governance Alerts", description: "Notify on T2/T3 decisions and freeze events", type: "toggle", value: true },
            { path: "notifications.channel", label: "Notification Channel", description: "Where to send alerts", type: "select", value: "vscode", options: [{ label: "VS Code Only", value: "vscode" }, { label: "Email", value: "email" }, { label: "Slack", value: "slack" }, { label: "All", value: "all" }] },
        ],
    },
];

// ──────────────────────────────────────────────────────────────────────────────
// Setting Controls
// ──────────────────────────────────────────────────────────────────────────────

function ToggleSwitch({ enabled, onChange, label }: { enabled: boolean; onChange: (v: boolean) => void; label?: string }) {
    return (
        <button
            onClick={() => onChange(!enabled)}
            aria-label={label || "Toggle setting"}
            aria-pressed={enabled}
            role="switch"
            className={`relative w-11 h-6 rounded-full transition-colors duration-200 ${
                enabled ? "bg-blue-600" : "bg-white/10"
            }`}
        >
            <div className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-lg transition-transform duration-200 ${
                enabled ? "translate-x-5" : "translate-x-0"
            }`} />
        </button>
    );
}

function SettingControl({ item, onChange }: { item: SettingItem; onChange: (path: string, value: any) => void }) {
    switch (item.type) {
        case "toggle":
            return <ToggleSwitch enabled={item.value} onChange={(v) => onChange(item.path, v)} label={item.label} />;
        case "select":
            return (
                <select
                    value={item.value}
                    onChange={(e) => onChange(item.path, e.target.value)}
                    aria-label={item.label}
                    title={item.label}
                    className="glass-input px-3 py-1.5 text-sm min-w-[180px]"
                >
                    {item.options?.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
            );
        case "number":
            return (
                <input
                    type="number"
                    value={item.value}
                    onChange={(e) => onChange(item.path, parseFloat(e.target.value))}
                    min={item.min}
                    max={item.max}
                    step={item.step || 1}
                    aria-label={item.label}
                    title={item.label}
                    className="glass-input px-3 py-1.5 text-sm w-24 text-right tabular-nums"
                />
            );
        case "slider":
            return (
                <div className="flex items-center gap-3">
                    <input
                        type="range"
                        value={item.value}
                        onChange={(e) => onChange(item.path, parseFloat(e.target.value))}
                        min={item.min}
                        max={item.max}
                        step={item.step || 1}
                        aria-label={item.label}
                        title={item.label}
                        className="w-32 accent-blue-500"
                    />
                    <span className="text-sm text-white tabular-nums w-12 text-right">
                        {item.value}{item.max === 1 ? "" : item.max === 100 ? "%" : ""}
                    </span>
                </div>
            );
        case "text":
            return (
                <input
                    type="text"
                    value={item.value}
                    onChange={(e) => onChange(item.path, e.target.value)}
                    aria-label={item.label}
                    title={item.label}
                    className="glass-input px-3 py-1.5 text-sm w-48"
                />
            );
        default:
            return null;
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// Preset Cards
// ──────────────────────────────────────────────────────────────────────────────

const PRESETS = [
    { id: "cost_saver", name: "Cost Saver", description: "Minimize spend with smallest models", icon: DollarSign, color: "text-emerald-400 bg-emerald-500/10" },
    { id: "balanced", name: "Balanced", description: "Good balance of cost and quality", icon: Layers, color: "text-blue-400 bg-blue-500/10" },
    { id: "quality_first", name: "Quality First", description: "Use frontier models for best results", icon: Zap, color: "text-purple-400 bg-purple-500/10" },
    { id: "privacy_first", name: "Privacy First", description: "Local-only models, no cloud APIs", icon: Lock, color: "text-orange-400 bg-orange-500/10" },
];

// ──────────────────────────────────────────────────────────────────────────────
// Main Settings Page
// ──────────────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
    const [activeSection, setActiveSection] = useState("council");
    const [settings, setSettings] = useState<Record<string, any>>(() => {
        const map: Record<string, any> = {};
        SECTIONS.forEach(s => s.settings.forEach(si => { map[si.path] = si.value; }));
        return map;
    });
    const [hasChanges, setHasChanges] = useState(false);
    const [saved, setSaved] = useState(false);

    const handleChange = useCallback((path: string, value: any) => {
        setSettings(prev => ({ ...prev, [path]: value }));
        setHasChanges(true);
        setSaved(false);
    }, []);

    const handleSave = useCallback(async () => {
        // In production: PATCH each changed setting via /model-settings/setting
        setSaved(true);
        setHasChanges(false);
        setTimeout(() => setSaved(false), 3000);
    }, [settings]);

    const handleReset = useCallback(() => {
        const map: Record<string, any> = {};
        SECTIONS.forEach(s => s.settings.forEach(si => { map[si.path] = si.value; }));
        setSettings(map);
        setHasChanges(false);
    }, []);

    const currentSection = SECTIONS.find(s => s.id === activeSection);

    return (
        <div className="p-6 lg:p-8 animate-fade-in">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Settings className="w-6 h-6 text-blue-400" />
                        Settings
                    </h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Configure every aspect of Aegion's behavior
                    </p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={handleReset}
                        disabled={!hasChanges}
                        className="px-4 py-2 rounded-xl text-sm font-medium bg-white/[0.04] text-slate-400 hover:text-white hover:bg-white/[0.08] transition-all disabled:opacity-30 flex items-center gap-2"
                    >
                        <RotateCcw className="w-3.5 h-3.5" />
                        Reset
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={!hasChanges}
                        className={`px-5 py-2 rounded-xl text-sm font-medium transition-all flex items-center gap-2 ${
                            saved
                                ? "bg-emerald-600 text-white"
                                : hasChanges
                                    ? "bg-blue-600 hover:bg-blue-500 text-white btn-glow"
                                    : "bg-white/[0.04] text-slate-500"
                        }`}
                    >
                        {saved ? <Check className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
                        {saved ? "Saved!" : "Save Changes"}
                    </button>
                </div>
            </div>

            {/* Presets Row */}
            <div className="mb-6">
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Quick Presets</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {PRESETS.map(p => (
                        <button
                            key={p.id}
                            className="glass-card card-lift p-4 text-left group"
                        >
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-2 ${p.color}`}>
                                <p.icon className="w-4 h-4" />
                            </div>
                            <div className="text-sm font-medium text-white group-hover:text-blue-300 transition-colors">
                                {p.name}
                            </div>
                            <div className="text-[11px] text-slate-500 mt-0.5">{p.description}</div>
                        </button>
                    ))}
                </div>
            </div>

            {/* Main Layout: Sidebar + Content */}
            <div className="flex flex-col lg:flex-row gap-6">
                {/* Section Navigation */}
                <div className="lg:w-64 flex-shrink-0">
                    <div className="glass-card-static overflow-hidden">
                        {SECTIONS.map(section => {
                            const Icon = section.icon;
                            const isActive = activeSection === section.id;
                            return (
                                <button
                                    key={section.id}
                                    onClick={() => setActiveSection(section.id)}
                                    className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-all ${
                                        isActive
                                            ? "bg-blue-600/10 text-blue-400 border-l-2 border-blue-500"
                                            : "text-slate-400 hover:text-white hover:bg-white/[0.02] border-l-2 border-transparent"
                                    }`}
                                >
                                    <Icon className="w-4 h-4 flex-shrink-0" />
                                    <span className="text-sm font-medium">{section.label}</span>
                                </button>
                            );
                        })}
                    </div>

                    {/* Import/Export */}
                    <div className="mt-4 space-y-2">
                        <button className="w-full px-4 py-2.5 rounded-xl text-sm font-medium bg-white/[0.04] text-slate-400 hover:text-white hover:bg-white/[0.08] transition-all flex items-center gap-2">
                            <Download className="w-3.5 h-3.5" />
                            Export Settings
                        </button>
                        <button className="w-full px-4 py-2.5 rounded-xl text-sm font-medium bg-white/[0.04] text-slate-400 hover:text-white hover:bg-white/[0.08] transition-all flex items-center gap-2">
                            <Upload className="w-3.5 h-3.5" />
                            Import Settings
                        </button>
                    </div>
                </div>

                {/* Settings Content */}
                <div className="flex-1">
                    {currentSection && (
                        <div className="glass-card-static overflow-hidden animate-fade-in" key={currentSection.id}>
                            <div className="px-6 py-5 border-b border-white/[0.05]">
                                <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                                    <currentSection.icon className="w-5 h-5 text-blue-400" />
                                    {currentSection.label}
                                </h2>
                                <p className="text-sm text-slate-500 mt-1">{currentSection.description}</p>
                            </div>
                            <div className="divide-y divide-white/[0.03]">
                                {currentSection.settings.map(item => (
                                    <div key={item.path} className="px-6 py-4 flex items-center justify-between gap-4 hover:bg-white/[0.01] transition-colors">
                                        <div className="flex-1 min-w-0">
                                            <div className="text-sm font-medium text-white">{item.label}</div>
                                            <div className="text-xs text-slate-500 mt-0.5">{item.description}</div>
                                        </div>
                                        <SettingControl
                                            item={{ ...item, value: settings[item.path] ?? item.value }}
                                            onChange={handleChange}
                                        />
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
