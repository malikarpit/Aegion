"use client";

import { useState, useCallback } from "react";
import {
  Settings, Cpu, DollarSign, Shield, Key,
  Save, Loader2, Eye, EyeOff, Check,
} from "lucide-react";
import api from "@/lib/api";

/* ══════════════════════════════════════════════════════════════
   SETTINGS PAGE — 4 tabs: Keys, Models, Governance, Budget
   ══════════════════════════════════════════════════════════════ */

const TABS = [
  { id: "keys", label: "API Keys", icon: Key },
  { id: "models", label: "Models", icon: Cpu },
  { id: "governance", label: "Governance", icon: Shield },
  { id: "budget", label: "Budget", icon: DollarSign },
];

interface ApiKey {
  provider: string;
  key: string;
  masked: string;
  set: boolean;
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("keys");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // API Keys state
  const [keys, setKeys] = useState<ApiKey[]>([
    { provider: "OpenAI", key: "", masked: "sk-...XXXX", set: true },
    { provider: "Anthropic", key: "", masked: "sk-ant-...XXXX", set: true },
    { provider: "Google", key: "", masked: "AIza...XXXX", set: true },
  ]);
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});

  // Governance state
  const [governance, setGovernance] = useState({
    autoApproveT0: true,
    autoApproveT1: false,
    requireSentinelT2: true,
    requireSentinelT3: true,
    maxParallelPipelines: 3,
    freezeThreshold: 0.8,
  });

  // Budget state
  const [budget, setBudget] = useState({
    monthlyLimit: 100,
    dailyLimit: 10,
    autoPause: true,
    alertAt: 80,
  });

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await api.post("/settings", { keys, governance, budget });
    } catch { /* silent */ }
    finally {
      setSaving(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
  }, [keys, governance, budget]);

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-page-enter">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
            <Settings size={20} style={{ color: "var(--text-muted)" }} />
            Settings
          </h1>
          <p className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
            System configuration and governance rules
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium disabled:opacity-30 transition-all"
          style={{ background: saved ? "var(--status-success)" : "var(--accent-reason)", color: "white" }}
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : saved ? <Check size={14} /> : <Save size={14} />}
          {saved ? "Saved" : "Save Changes"}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1" style={{ borderBottom: "0.5px solid var(--border-subtle)" }}>
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="flex items-center gap-2 px-4 py-2.5 -mb-[0.5px] transition-all text-[13px] font-medium"
              style={{
                color: isActive ? "var(--text-primary)" : "var(--text-muted)",
                borderBottom: isActive ? "2px solid var(--accent-reason)" : "2px solid transparent",
              }}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="animate-fade-in">
        {activeTab === "keys" && (
          <div className="space-y-4 max-w-2xl">
            <p className="text-[14px]" style={{ color: "var(--text-secondary)" }}>
              Configure API provider keys. Keys are encrypted at rest.
            </p>
            {keys.map((k, i) => (
              <div key={k.provider} className="glass-l1 p-4 rounded-xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[14px] font-medium" style={{ color: "var(--text-primary)" }}>{k.provider}</span>
                  {k.set && (
                    <span className="hud-label px-1.5 py-[1px] rounded-[4px]" style={{ background: "hsla(142,60%,48%,0.1)", color: "var(--status-success)" }}>
                      CONFIGURED
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <input
                      type={showKey[k.provider] ? "text" : "password"}
                      value={k.key || k.masked}
                      onChange={(e) => {
                        const newKeys = [...keys];
                        newKeys[i] = { ...k, key: e.target.value };
                        setKeys(newKeys);
                      }}
                      className="glass-input w-full px-3 py-2 text-[13px] pr-10"
                      style={{ fontFamily: "var(--font-mono)" }}
                    />
                    <button
                      onClick={() => setShowKey((s) => ({ ...s, [k.provider]: !s[k.provider] }))}
                      className="absolute right-3 top-1/2 -translate-y-1/2"
                    >
                      {showKey[k.provider] ? (
                        <EyeOff size={14} style={{ color: "var(--text-ghost)" }} />
                      ) : (
                        <Eye size={14} style={{ color: "var(--text-ghost)" }} />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === "governance" && (
          <div className="space-y-4 max-w-2xl">
            <p className="text-[14px]" style={{ color: "var(--text-secondary)" }}>
              Governance pipeline rules and tier configurations.
            </p>
            {[
              { key: "autoApproveT0", label: "Auto-approve T0 decisions", description: "Trivial decisions bypass governance" },
              { key: "autoApproveT1", label: "Auto-approve T1 decisions", description: "Low-impact decisions skip council review" },
              { key: "requireSentinelT2", label: "Require Sentinel for T2", description: "Moderate decisions must pass security review" },
              { key: "requireSentinelT3", label: "Require Sentinel for T3", description: "Critical decisions always require security review" },
            ].map((rule) => (
              <div key={rule.key} className="glass-l1 p-4 rounded-xl flex items-center justify-between">
                <div>
                  <p className="text-[14px] font-medium" style={{ color: "var(--text-primary)" }}>{rule.label}</p>
                  <p className="text-[12px] mt-0.5" style={{ color: "var(--text-muted)" }}>{rule.description}</p>
                </div>
                <button
                  onClick={() => setGovernance((g) => ({ ...g, [rule.key]: !g[rule.key as keyof typeof g] }))}
                  className="w-10 h-5 rounded-full transition-all relative"
                  style={{
                    background: governance[rule.key as keyof typeof governance] ? "var(--accent-execute)" : "var(--surface-3)",
                  }}
                >
                  <div
                    className="w-4 h-4 rounded-full absolute top-0.5 transition-all"
                    style={{
                      left: governance[rule.key as keyof typeof governance] ? 22 : 2,
                      background: "white",
                    }}
                  />
                </button>
              </div>
            ))}
            <div className="glass-l1 p-4 rounded-xl">
              <p className="text-[14px] font-medium mb-2" style={{ color: "var(--text-primary)" }}>Freeze Threshold</p>
              <p className="text-[12px] mb-2" style={{ color: "var(--text-muted)" }}>Risk score that triggers governance freeze</p>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="0.5" max="1.0" step="0.05"
                  value={governance.freezeThreshold}
                  onChange={(e) => setGovernance((g) => ({ ...g, freezeThreshold: parseFloat(e.target.value) }))}
                  className="flex-1"
                />
                <span className="mono-data font-medium" style={{
                  color: governance.freezeThreshold < 0.7 ? "var(--status-error)" : "var(--status-warning)",
                }}>
                  {governance.freezeThreshold.toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        )}

        {activeTab === "budget" && (
          <div className="space-y-4 max-w-2xl">
            <p className="text-[14px]" style={{ color: "var(--text-secondary)" }}>
              Budget limits and cost controls.
            </p>
            {[
              { key: "monthlyLimit", label: "Monthly Limit", prefix: "$" },
              { key: "dailyLimit", label: "Daily Limit", prefix: "$" },
              { key: "alertAt", label: "Alert at %", prefix: "" },
            ].map((field) => (
              <div key={field.key} className="glass-l1 p-4 rounded-xl">
                <p className="hud-label mb-2">{field.label.toUpperCase()}</p>
                <div className="flex items-center gap-2">
                  {field.prefix && <span className="mono-data" style={{ color: "var(--accent-cost)" }}>{field.prefix}</span>}
                  <input
                    type="number"
                    value={budget[field.key as keyof typeof budget] as number}
                    onChange={(e) => setBudget((b) => ({ ...b, [field.key]: parseFloat(e.target.value) }))}
                    className="glass-input px-3 py-2 text-[14px] w-32"
                    style={{ fontFamily: "var(--font-mono)" }}
                  />
                </div>
              </div>
            ))}
            <div className="glass-l1 p-4 rounded-xl flex items-center justify-between">
              <div>
                <p className="text-[14px] font-medium" style={{ color: "var(--text-primary)" }}>Auto-pause on exceed</p>
                <p className="text-[12px] mt-0.5" style={{ color: "var(--text-muted)" }}>Halt AI operations when budget exceeded</p>
              </div>
              <button
                onClick={() => setBudget((b) => ({ ...b, autoPause: !b.autoPause }))}
                className="w-10 h-5 rounded-full transition-all relative"
                style={{ background: budget.autoPause ? "var(--accent-execute)" : "var(--surface-3)" }}
              >
                <div className="w-4 h-4 rounded-full absolute top-0.5 transition-all" style={{
                  left: budget.autoPause ? 22 : 2, background: "white",
                }} />
              </button>
            </div>
          </div>
        )}

        {activeTab === "models" && (
          <div className="text-center py-12">
            <Cpu size={32} className="mx-auto mb-3" style={{ color: "var(--text-ghost)", opacity: 0.3 }} />
            <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
              Model configuration is available on the{" "}
              <a href="/dashboard/models" className="underline" style={{ color: "var(--accent-reason)" }}>Models page</a>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
