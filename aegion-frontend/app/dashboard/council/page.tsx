"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Cpu, User, ChevronDown, Copy, Check, Sparkles, Shield, Layers } from "lucide-react";
import { Badge } from "@/components/ui/Badge";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
    metadata?: {
        models?: Array<{ name: string; provider: string; confidence: number; cost: number; response: string }>;
        consensus?: number;
        dissent?: string[];
        totalCost?: number;
        councilType?: string;
    };
}

const councilTypes = [
    { id: "child", label: "Child Council", description: "Fast, single-pass for simple queries", icon: Sparkles },
    { id: "parent", label: "Parent Council", description: "Full debate with multiple rounds", icon: Layers },
    { id: "sentinel", label: "Sentinel Council", description: "Security-focused review", icon: Shield },
];

const MOCK_COUNCIL_RESPONSE = {
    models: [
        { name: "gpt-4o", provider: "OpenAI", confidence: 0.92, cost: 0.018, response: "The proposed architecture follows a clean separation of concerns. The FastAPI backend handles orchestration while Supabase manages persistence. **Recommendation**: Add connection pooling for the database layer to handle concurrent requests efficiently.\n\n```python\nfrom sqlalchemy.pool import QueuePool\nengine = create_engine(url, poolclass=QueuePool, pool_size=5)\n```" },
        { name: "claude-sonnet", provider: "Anthropic", confidence: 0.88, cost: 0.015, response: "I agree with the general architecture but want to highlight a concern: the current design couples the council engine directly to the API layer. Consider introducing a message queue (Redis Streams) between them for better resilience and async processing." },
        { name: "gemini-flash", provider: "Google", confidence: 0.85, cost: 0.001, response: "Architecture looks solid. The cascade pattern for model routing is cost-effective. One suggestion: implement circuit breakers for external API calls to prevent cascade failures when a provider is down." },
    ],
    consensus: 87,
    dissent: ["Consider message queue coupling concern raised by Claude"],
    totalCost: 0.034,
    councilType: "parent",
};

function ConsensusGauge({ score }: { score: number }) {
    const getColor = (s: number) => {
        if (s >= 80) return "text-emerald-400";
        if (s >= 50) return "text-yellow-400";
        return "text-red-400";
    };

    return (
        <div className="flex items-center gap-2">
            <div className="relative w-10 h-10">
                <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                    <circle cx="18" cy="18" r="15" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="3" />
                    <circle
                        cx="18" cy="18" r="15" fill="none"
                        stroke="currentColor"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeDasharray={`${(score / 100) * 94.2} 94.2`}
                        className={`${getColor(score)} transition-all duration-1000`}
                    />
                </svg>
                <span className={`absolute inset-0 flex items-center justify-center text-[10px] font-bold ${getColor(score)}`}>
                    {score}
                </span>
            </div>
            <div>
                <p className="text-xs text-slate-400">Consensus</p>
            </div>
        </div>
    );
}

export default function CouncilPage() {
    const [messages, setMessages] = useState<Message[]>([
        {
            id: "1",
            role: "assistant",
            content: "Aegion Council online. Submit a query for multi-model deliberation.",
            timestamp: new Date(),
        },
    ]);
    const [input, setInput] = useState("");
    const [selectedCouncil, setSelectedCouncil] = useState("parent");
    const [isStreaming, setIsStreaming] = useState(false);
    const [copiedId, setCopiedId] = useState<string | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const [showModels, setShowModels] = useState<string | null>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const copyText = (text: string, id: string) => {
        navigator.clipboard.writeText(text);
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 2000);
    };

    const sendMessage = async () => {
        if (!input.trim() || isStreaming) return;

        const userMsg: Message = {
            id: Date.now().toString(),
            role: "user",
            content: input,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setIsStreaming(true);

        // Simulate streaming delay
        setTimeout(() => {
            const aiMsg: Message = {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: `Based on multi-model council deliberation (${selectedCouncil} council), here is the synthesized response:\n\nThe proposed approach is architecturally sound. The council reached **${MOCK_COUNCIL_RESPONSE.consensus}% consensus** across ${MOCK_COUNCIL_RESPONSE.models.length} models.\n\n**Key Points:**\n1. Clean separation of concerns is maintained\n2. Connection pooling recommended for database layer\n3. Consider message queue for async resilience\n4. Circuit breakers needed for external API calls\n\n**Dissenting View:** ${MOCK_COUNCIL_RESPONSE.dissent[0]}`,
                timestamp: new Date(),
                metadata: MOCK_COUNCIL_RESPONSE,
            };
            setMessages((prev) => [...prev, aiMsg]);
            setIsStreaming(false);
        }, 2000);
    };

    return (
        <div className="h-[calc(100vh)] flex flex-col animate-fade-in">
            {/* Header */}
            <div className="p-4 lg:px-8 border-b border-white/5 flex items-center justify-between shrink-0">
                <div>
                    <h1 className="text-lg font-bold text-white">Council Console</h1>
                    <p className="text-xs text-slate-500">Multi-model AI deliberation</p>
                </div>
                <div className="flex items-center gap-2">
                    {councilTypes.map((ct) => {
                        const Icon = ct.icon;
                        return (
                            <button
                                key={ct.id}
                                onClick={() => setSelectedCouncil(ct.id)}
                                title={ct.description}
                                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                                    selectedCouncil === ct.id
                                        ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                                        : "text-slate-500 hover:text-slate-300 hover:bg-white/5 border border-transparent"
                                }`}
                            >
                                <Icon size={14} />
                                {ct.label}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 lg:px-8 space-y-4">
                {messages.map((msg) => (
                    <div
                        key={msg.id}
                        className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
                    >
                        <div
                            className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                                msg.role === "user" ? "bg-white/10" : "bg-blue-600/20"
                            }`}
                        >
                            {msg.role === "user" ? (
                                <User size={14} />
                            ) : (
                                <Cpu size={14} className="text-blue-400" />
                            )}
                        </div>

                        <div className={`max-w-[75%] space-y-2 ${msg.role === "user" ? "items-end" : ""}`}>
                            <div
                                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                                    msg.role === "user"
                                        ? "bg-white/10 text-white rounded-tr-sm"
                                        : "bg-blue-600/5 text-slate-200 border border-blue-500/10 rounded-tl-sm"
                                }`}
                            >
                                {msg.content}
                            </div>

                            {/* Metadata bar */}
                            {msg.metadata && (
                                <div className="flex items-center gap-3 px-1">
                                    <ConsensusGauge score={msg.metadata.consensus || 0} />

                                    <Badge variant="info" size="sm">
                                        ${msg.metadata.totalCost?.toFixed(4)}
                                    </Badge>

                                    <button
                                        onClick={() =>
                                            setShowModels(showModels === msg.id ? null : msg.id)
                                        }
                                        className="text-[11px] text-slate-500 hover:text-blue-400 transition-colors"
                                    >
                                        {showModels === msg.id ? "Hide" : "Show"} model responses
                                    </button>

                                    <button
                                        onClick={() => copyText(msg.content, msg.id)}
                                        className="text-slate-600 hover:text-white transition-colors ml-auto"
                                    >
                                        {copiedId === msg.id ? (
                                            <Check size={14} className="text-emerald-400" />
                                        ) : (
                                            <Copy size={14} />
                                        )}
                                    </button>
                                </div>
                            )}

                            {/* Individual model responses */}
                            {showModels === msg.id && msg.metadata?.models && (
                                <div className="grid gap-2 animate-slide-down">
                                    {msg.metadata.models.map((m, i) => (
                                        <div
                                            key={i}
                                            className="bg-white/[0.02] border border-white/5 rounded-xl p-4"
                                        >
                                            <div className="flex items-center justify-between mb-2">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs font-medium text-white">
                                                        {m.name}
                                                    </span>
                                                    <Badge variant="neutral" size="sm">
                                                        {m.provider}
                                                    </Badge>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Badge
                                                        variant={m.confidence >= 0.9 ? "success" : m.confidence >= 0.7 ? "warning" : "danger"}
                                                        size="sm"
                                                    >
                                                        {(m.confidence * 100).toFixed(0)}%
                                                    </Badge>
                                                    <span className="text-[10px] text-slate-500">
                                                        ${m.cost.toFixed(4)}
                                                    </span>
                                                </div>
                                            </div>
                                            <p className="text-xs text-slate-400 leading-relaxed whitespace-pre-wrap">
                                                {m.response}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                ))}

                {isStreaming && (
                    <div className="flex gap-3">
                        <div className="w-8 h-8 rounded-full bg-blue-600/20 flex items-center justify-center shrink-0">
                            <Cpu size={14} className="text-blue-400 animate-pulse" />
                        </div>
                        <div className="bg-blue-600/5 border border-blue-500/10 rounded-2xl rounded-tl-sm px-4 py-3">
                            <div className="flex gap-1.5">
                                <div className="w-2 h-2 rounded-full bg-blue-400/60 animate-bounce" style={{ animationDelay: "0ms" }} />
                                <div className="w-2 h-2 rounded-full bg-blue-400/60 animate-bounce" style={{ animationDelay: "150ms" }} />
                                <div className="w-2 h-2 rounded-full bg-blue-400/60 animate-bounce" style={{ animationDelay: "300ms" }} />
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 lg:px-8 border-t border-white/5 bg-black/40 shrink-0">
                <div className="relative max-w-4xl">
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                sendMessage();
                            }
                        }}
                        placeholder="Submit a query for council deliberation..."
                        rows={1}
                        className="glass-input w-full pl-4 pr-14 py-3.5 text-sm resize-none"
                    />
                    <button
                        onClick={sendMessage}
                        disabled={isStreaming || !input.trim()}
                        className="absolute right-2 bottom-2 p-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                        <Send size={14} />
                    </button>
                </div>
            </div>
        </div>
    );
}
