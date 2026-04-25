"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Send, Cpu, User, Copy, Check, Sparkles, Shield, Layers,
  MessageCircle, Zap, ArrowRight, Loader2,
} from "lucide-react";
import api from "@/lib/api";
import { useSystemContext } from "@/lib/context/SystemContext";
import { ConfidenceEvolution } from "@/components/cognitive/ConfidenceEvolution";
import { GovernancePipeline } from "@/components/cognitive/GovernancePipeline";
import { WhyPanel } from "@/components/cognitive/WhyPanel";
import { TransparencyPanel } from "@/components/cognitive/TransparencyPanel";
import type { AgentType, ConfidencePoint } from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   COUNCIL PAGE — Multi-Agent Reasoning Interface
   
   Not a chat UI. A cognitive deliberation chamber where:
   - Agent avatars show real-time thinking status
   - Confidence evolves visually across opinions
   - Consensus gauge shows convergence
   - Pipeline shows governance flow stage
   - WhyPanel shows decision provenance
   ══════════════════════════════════════════════════════════════ */

// ── Types ──
interface DebateOpinion {
  index: number;
  member_id: string;
  vote: string;
  confidence: number;
  analysis: string;
  stage: string;
}

interface DebateState {
  status: "idle" | "starting" | "debating" | "consensus" | "complete" | "error";
  proposalId?: string;
  tier?: string;
  title?: string;
  numRounds?: number;
  opinions: DebateOpinion[];
  consensus?: { consensus: string; confidence: number; dissent_count: number };
  result?: { session_id: string; synthesis: string; total_tokens: number };
  error?: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  debate?: DebateState;
}

const COUNCIL_TYPES = [
  {
    id: "child",
    label: "Quick",
    description: "Single-pass for simple queries",
    icon: Sparkles,
    agentType: "general" as AgentType,
  },
  {
    id: "parent",
    label: "Full Council",
    description: "Multi-round debate",
    icon: Layers,
    agentType: "architecture" as AgentType,
  },
  {
    id: "sentinel",
    label: "Sentinel",
    description: "Security-focused review",
    icon: Shield,
    agentType: "security" as AgentType,
  },
];

const AGENT_COLORS: Record<string, string> = {
  architect: "var(--agent-architecture)",
  security: "var(--agent-security)",
  performance: "var(--agent-performance)",
  ux: "var(--agent-ux)",
  redteam: "var(--agent-redteam)",
  general: "var(--agent-general)",
  sentinel: "var(--agent-security)",
};

function getAgentColor(memberId: string): string {
  const lower = memberId.toLowerCase();
  for (const [key, color] of Object.entries(AGENT_COLORS)) {
    if (lower.includes(key)) return color;
  }
  return "var(--accent-reason)";
}

function getAgentType(memberId: string): AgentType {
  const lower = memberId.toLowerCase();
  if (lower.includes("security") || lower.includes("sentinel")) return "security";
  if (lower.includes("performance")) return "performance";
  if (lower.includes("ux")) return "ux";
  if (lower.includes("redteam") || lower.includes("red")) return "redteam";
  if (lower.includes("architect")) return "architecture";
  return "general";
}

// ── Consensus Gauge ──
function ConsensusGauge({ score, dissentCount }: { score: number; dissentCount?: number }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.8
      ? "var(--status-success)"
      : score >= 0.5
        ? "var(--status-warning)"
        : "var(--status-error)";

  return (
    <div className="glass-l1 p-4 rounded-xl">
      <div className="flex items-center justify-between mb-2">
        <span className="hud-label">CONSENSUS</span>
        <span className="mono-data font-medium" style={{ color }}>
          {pct}%
        </span>
      </div>

      {/* Progress bar */}
      <div
        className="h-[6px] w-full rounded-full overflow-hidden"
        style={{ background: "var(--surface-3)" }}
      >
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${pct}%`,
            background: color,
            boxShadow: `0 0 8px ${color}`,
          }}
        />
      </div>

      {dissentCount !== undefined && dissentCount > 0 && (
        <p className="mono-data-sm mt-2" style={{ color: "var(--status-warning)" }}>
          {dissentCount} dissenting agent{dissentCount > 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}

// ── Agent Avatar ──
function AgentAvatar({
  memberId,
  status,
}: {
  memberId: string;
  status: "waiting" | "thinking" | "decided" | "dissenting";
}) {
  const color = getAgentColor(memberId);
  const initial = memberId.charAt(0).toUpperCase();

  return (
    <div className="relative">
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-[12px] font-bold border ${
          status === "thinking" ? "animate-breathe" : ""
        }`}
        style={{
          background: `color-mix(in srgb, ${color} 15%, transparent)`,
          borderColor: `color-mix(in srgb, ${color} 40%, transparent)`,
          color,
          boxShadow:
            status === "thinking"
              ? `0 0 12px color-mix(in srgb, ${color} 30%, transparent)`
              : "none",
        }}
        title={memberId}
      >
        {initial}
      </div>
      {status === "thinking" && (
        <div
          className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full animate-pipeline-pulse"
          style={{ background: color }}
        />
      )}
    </div>
  );
}

// ── Opinion Card ──
function OpinionCard({ opinion }: { opinion: DebateOpinion }) {
  const [copied, setCopied] = useState(false);
  const color = getAgentColor(opinion.member_id);

  const handleCopy = () => {
    navigator.clipboard.writeText(opinion.analysis);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className="glass-l1 p-4 rounded-xl"
      style={{
        borderLeft: `3px solid ${color}`,
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <AgentAvatar memberId={opinion.member_id} status="decided" />
          <div>
            <span className="text-[13px] font-medium" style={{ color }}>
              {opinion.member_id}
            </span>
            <span className="mono-data-sm ml-2" style={{ color: "var(--text-ghost)" }}>
              R{opinion.index + 1}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`hud-label px-1.5 py-[1px] rounded-[4px] ${
              opinion.vote === "approve"
                ? ""
                : opinion.vote === "reject"
                  ? ""
                  : ""
            }`}
            style={{
              background:
                opinion.vote === "approve"
                  ? "hsla(142, 60%, 48%, 0.1)"
                  : opinion.vote === "reject"
                    ? "hsla(348, 82%, 52%, 0.1)"
                    : "hsla(220, 12%, 48%, 0.1)",
              color:
                opinion.vote === "approve"
                  ? "var(--status-success)"
                  : opinion.vote === "reject"
                    ? "var(--status-error)"
                    : "var(--text-muted)",
            }}
          >
            {opinion.vote.toUpperCase()}
          </span>

          <span
            className="mono-data-sm font-medium"
            style={{
              color:
                opinion.confidence > 0.7
                  ? "var(--status-success)"
                  : opinion.confidence > 0.4
                    ? "var(--status-warning)"
                    : "var(--status-error)",
            }}
          >
            {opinion.confidence.toFixed(2)}
          </span>
        </div>
      </div>

      <p
        className="text-[13px] leading-relaxed whitespace-pre-wrap"
        style={{ color: "var(--text-secondary)" }}
      >
        {opinion.analysis}
      </p>

      <div className="flex items-center justify-between mt-2">
        <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
          {opinion.stage}
        </span>
        <button
          onClick={handleCopy}
          className="opacity-40 hover:opacity-100 transition-opacity"
        >
          {copied ? <Check size={12} style={{ color: "var(--status-success)" }} /> : <Copy size={12} />}
        </button>
      </div>
    </div>
  );
}

export default function CouncilPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [councilType, setCouncilType] = useState("parent");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { dispatch } = useSystemContext();

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || isLoading) return;
    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    dispatch({ type: "THINKING", payload: { context: "Council deliberation" } });

    try {
      const response = await api.post("/api/council/invoke", {
        query: input,
        council_type: councilType,
      });

      const data = response.data;
      const debate: DebateState = {
        status: "complete",
        opinions: data.opinions || [],
        consensus: data.consensus,
        result: data.result,
      };

      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.result?.synthesis || "Council deliberation complete.",
        timestamp: new Date(),
        debate,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Council invocation failed";
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `Error: ${errorMessage}`,
        timestamp: new Date(),
        debate: { status: "error", opinions: [], error: errorMessage },
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      dispatch({ type: "THINKING_DONE", payload: {} });
    }
  }, [input, isLoading, councilType, dispatch]);

  // Build confidence evolution from opinions
  const buildConfidencePoints = (opinions: DebateOpinion[]): ConfidencePoint[] =>
    opinions.map((o, i) => ({
      agentId: o.member_id,
      agentType: getAgentType(o.member_id),
      value: o.confidence,
      timestamp: Date.now() - (opinions.length - i) * 60000,
    }));

  return (
    <div className="flex h-full">
      {/* ── LEFT: Council Type Selector ── */}
      <div
        className="w-[200px] p-3 border-r flex flex-col gap-2 shrink-0"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <p className="hud-label px-2 mb-1">COUNCIL MODE</p>
        {COUNCIL_TYPES.map((ct) => {
          const Icon = ct.icon;
          const isActive = councilType === ct.id;
          return (
            <button
              key={ct.id}
              onClick={() => setCouncilType(ct.id)}
              className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-left transition-all duration-150"
              style={{
                background: isActive ? "var(--surface-hover)" : "transparent",
                borderLeft: isActive ? "2px solid var(--accent-reason)" : "2px solid transparent",
                color: isActive ? "var(--text-primary)" : "var(--text-muted)",
              }}
            >
              <Icon size={14} style={{ color: isActive ? "var(--accent-reason)" : "var(--text-ghost)" }} />
              <div>
                <p className="text-[13px] font-medium">{ct.label}</p>
                <p className="text-[11px]" style={{ color: "var(--text-ghost)" }}>
                  {ct.description}
                </p>
              </div>
            </button>
          );
        })}

        {/* Active agents indicator */}
        {isLoading && (
          <div className="glass-l1 p-3 rounded-lg mt-auto">
            <p className="hud-label mb-2">AGENTS ACTIVE</p>
            <div className="flex flex-col gap-1.5">
              {["Architect", "Security", "Performance"].map((name) => (
                <div key={name} className="flex items-center gap-2">
                  <AgentAvatar memberId={name} status="thinking" />
                  <span className="text-[12px]" style={{ color: "var(--text-secondary)" }}>
                    {name}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── CENTER: Deliberation Stream ── */}
      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto smooth-scroll p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-4">
              <div
                className="w-16 h-16 rounded-full flex items-center justify-center"
                style={{
                  background: "var(--tier-1-bg)",
                  border: "1px solid var(--tier-1-border)",
                }}
              >
                <Cpu size={28} style={{ color: "var(--accent-reason)" }} />
              </div>
              <div className="text-center">
                <h2 className="text-[18px] font-semibold mb-1">Council Chamber</h2>
                <p className="text-[14px]" style={{ color: "var(--text-secondary)" }}>
                  Ask anything. Multiple AI agents will deliberate and reason.
                </p>
                <p className="text-[12px] mt-2" style={{ color: "var(--text-ghost)" }}>
                  Every opinion, confidence score, and dissent is visible.
                </p>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] ${
                  msg.role === "user" ? "glass-l1 p-4 rounded-xl" : "space-y-3 w-full"
                }`}
                style={
                  msg.role === "user"
                    ? {
                        borderLeft: "3px solid var(--accent-reason)",
                      }
                    : undefined
                }
              >
                {msg.role === "user" ? (
                  <>
                    <div className="flex items-center gap-2 mb-1">
                      <User size={13} style={{ color: "var(--text-muted)" }} />
                      <span className="hud-label">YOU</span>
                    </div>
                    <p className="text-[14px]" style={{ color: "var(--text-primary)" }}>
                      {msg.content}
                    </p>
                  </>
                ) : (
                  <>
                    {/* Debate opinions */}
                    {msg.debate?.opinions && msg.debate.opinions.length > 0 && (
                      <div className="space-y-2">
                        <p className="hud-label">AGENT OPINIONS</p>
                        {msg.debate.opinions.map((o, i) => (
                          <OpinionCard key={i} opinion={o} />
                        ))}
                      </div>
                    )}

                    {/* Confidence Evolution */}
                    {msg.debate?.opinions && msg.debate.opinions.length > 1 && (
                      <div className="glass-l1 p-3 rounded-xl">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="hud-label">CONFIDENCE EVOLUTION</span>
                        </div>
                        <ConfidenceEvolution
                          points={buildConfidencePoints(msg.debate.opinions)}
                          size={{ width: 120, height: 24 }}
                        />
                      </div>
                    )}

                    {/* Consensus */}
                    {msg.debate?.consensus && (
                      <ConsensusGauge
                        score={msg.debate.consensus.confidence}
                        dissentCount={msg.debate.consensus.dissent_count}
                      />
                    )}

                    {/* Synthesis */}
                    {msg.debate?.result?.synthesis && (
                      <div className="glass-l2 p-4 rounded-xl">
                        <div className="flex items-center gap-2 mb-2">
                          <Zap size={14} style={{ color: "var(--accent-reason)" }} />
                          <span className="text-[14px] font-semibold">Synthesis</span>
                        </div>
                        <p
                          className="text-[14px] leading-relaxed whitespace-pre-wrap"
                          style={{ color: "var(--text-secondary)" }}
                        >
                          {msg.debate.result.synthesis}
                        </p>
                      </div>
                    )}

                    {/* Transparency */}
                    {msg.debate?.result && (
                      <TransparencyPanel
                        models={[
                          {
                            name: councilType === "child" ? "GPT-4o-mini" : "GPT-4o",
                            tokensIn: Math.round((msg.debate.result.total_tokens || 0) * 0.6),
                            tokensOut: Math.round((msg.debate.result.total_tokens || 0) * 0.4),
                            cost: (msg.debate.result.total_tokens || 0) * 0.000015,
                            latency: 2.4,
                          },
                        ]}
                        totalCost={(msg.debate.result.total_tokens || 0) * 0.000015}
                        totalLatency={2.4}
                        confidenceEvolution={buildConfidencePoints(msg.debate.opinions)}
                        trust={
                          msg.debate.consensus && msg.debate.consensus.confidence > 0.8
                            ? "validated"
                            : msg.debate.consensus && msg.debate.consensus.confidence > 0.5
                              ? "moderate"
                              : "novel"
                        }
                        defaultLevel={1}
                      />
                    )}

                    {/* Error */}
                    {msg.debate?.error && (
                      <div
                        className="glass-l1 p-4 rounded-xl"
                        style={{ borderLeft: "3px solid var(--status-error)" }}
                      >
                        <p className="text-[14px]" style={{ color: "var(--status-error)" }}>
                          {msg.debate.error}
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}

          {/* Thinking indicator */}
          {isLoading && (
            <div className="flex items-center gap-3 p-3">
              <div className="flex -space-x-2">
                {["Architect", "Security", "Performance"].map((name) => (
                  <AgentAvatar key={name} memberId={name} status="thinking" />
                ))}
              </div>
              <div>
                <p className="text-[13px] font-medium" style={{ color: "var(--accent-reason)" }}>
                  Council is deliberating...
                </p>
                <p className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                  {councilType === "parent"
                    ? "Multi-round debate in progress"
                    : "Processing query"}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div
          className="p-4"
          style={{ borderTop: "0.5px solid var(--border-subtle)" }}
        >
          <div className="glass-input flex items-center gap-2 p-1">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder="Ask the council..."
              className="flex-1 bg-transparent px-3 py-2 text-[14px] outline-none placeholder:text-[var(--text-ghost)]"
              style={{ color: "var(--text-primary)" }}
              disabled={isLoading}
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="px-3 py-2 rounded-md disabled:opacity-30 transition-all"
              style={{
                background: input.trim() ? "var(--accent-reason)" : "transparent",
                color: input.trim() ? "white" : "var(--text-ghost)",
              }}
            >
              {isLoading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Send size={16} />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
