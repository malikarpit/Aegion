"use client";

import { useState, useEffect } from "react";
import { Cpu, Loader2, Check, X } from "lucide-react";
import api from "@/lib/api";

/* ══════════════════════════════════════════════════════════════
   MODELS PAGE — AI model configuration, grouped by provider
   ══════════════════════════════════════════════════════════════ */

interface Model {
  id: string;
  name: string;
  provider: string;
  type: string;
  active: boolean;
  contextWindow: number;
  costPer1k: number;
}

const PROVIDER_COLORS: Record<string, string> = {
  OpenAI: "var(--accent-reason)",
  Anthropic: "var(--accent-govern)",
  Google: "var(--accent-execute)",
};

export default function ModelsPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchModels() {
      try {
        const res = await api.get("/models");
        const raw = res.data?.models || res.data || [];
        setModels(raw.map((m: Record<string, unknown>) => ({
          id: (m.id || m.model_id) as string,
          name: (m.name || m.model_name) as string,
          provider: (m.provider || "Unknown") as string,
          type: (m.type || "chat") as string,
          active: m.active !== false,
          contextWindow: (m.context_window || 128000) as number,
          costPer1k: (m.cost_per_1k || 0.01) as number,
        })));
      } catch {
        setModels([
          { id: "gpt-4o", name: "GPT-4o", provider: "OpenAI", type: "chat", active: true, contextWindow: 128000, costPer1k: 0.005 },
          { id: "gpt-4o-mini", name: "GPT-4o Mini", provider: "OpenAI", type: "chat", active: true, contextWindow: 128000, costPer1k: 0.00015 },
          { id: "claude-sonnet-4", name: "Claude Sonnet 4", provider: "Anthropic", type: "chat", active: true, contextWindow: 200000, costPer1k: 0.003 },
          { id: "claude-haiku", name: "Claude Haiku", provider: "Anthropic", type: "chat", active: true, contextWindow: 200000, costPer1k: 0.00025 },
          { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro", provider: "Google", type: "chat", active: true, contextWindow: 1000000, costPer1k: 0.00125 },
          { id: "gemini-2.0-flash", name: "Gemini 2.0 Flash", provider: "Google", type: "chat", active: true, contextWindow: 1000000, costPer1k: 0.0001 },
        ]);
      } finally {
        setLoading(false);
      }
    }
    fetchModels();
  }, []);

  // Group by provider
  const grouped = models.reduce<Record<string, Model[]>>((acc, m) => {
    if (!acc[m.provider]) acc[m.provider] = [];
    acc[m.provider].push(m);
    return acc;
  }, {});

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-page-enter">
      <div>
        <h1 className="text-[22px] font-bold" style={{ color: "var(--text-primary)" }}>Models</h1>
        <p className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
          AI model configuration — providers, costs, context windows
        </p>
      </div>

      {loading ? (
        <div className="text-center py-12"><Loader2 size={24} className="animate-spin mx-auto" style={{ color: "var(--accent-reason)" }} /></div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([provider, providerModels]) => (
            <div key={provider}>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-3 h-3 rounded-full" style={{ background: PROVIDER_COLORS[provider] || "var(--text-muted)" }} />
                <p className="text-[15px] font-semibold" style={{ color: "var(--text-primary)" }}>{provider}</p>
                <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>{providerModels.length} models</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {providerModels.map((model) => (
                  <div key={model.id} className="glass-l1 p-4 rounded-xl card-lift" style={{
                    borderLeft: `3px solid ${PROVIDER_COLORS[provider] || "var(--text-muted)"}`,
                    opacity: model.active ? 1 : 0.5,
                  }}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Cpu size={14} style={{ color: PROVIDER_COLORS[provider] }} />
                        <span className="text-[14px] font-medium" style={{ color: "var(--text-primary)" }}>{model.name}</span>
                      </div>
                      {model.active ? (
                        <Check size={14} style={{ color: "var(--status-success)" }} />
                      ) : (
                        <X size={14} style={{ color: "var(--text-ghost)" }} />
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-2 mt-2">
                      <div>
                        <p className="hud-label">CONTEXT</p>
                        <p className="mono-data-sm" style={{ color: "var(--text-primary)" }}>
                          {(model.contextWindow / 1000).toFixed(0)}K
                        </p>
                      </div>
                      <div>
                        <p className="hud-label">COST/1K</p>
                        <p className="mono-data-sm" style={{ color: "var(--accent-cost)" }}>
                          ${model.costPer1k.toFixed(5)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
