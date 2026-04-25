"use client";

import { useState, useEffect, useRef } from "react";
import { Send, Key, Cpu, User } from "lucide-react";
import { ProjectGraph } from "@/components/graph/ProjectGraph";
import api from "@/lib/api";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
}

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([
        { id: "1", role: "assistant", content: "Aegion Systems Online. How can I assist with your project architecture today?", timestamp: new Date() }
    ]);
    const [input, setInput] = useState("");
    const [customKey, setCustomKey] = useState("");
    const [showKeyInput, setShowKeyInput] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const savedKey = localStorage.getItem("aegion_custom_key");
        if (savedKey) setCustomKey(savedKey);
    }, []);

    const saveKey = (key: string) => {
        setCustomKey(key);
        if (key) {
            localStorage.setItem("aegion_custom_key", key);
        } else {
            localStorage.removeItem("aegion_custom_key");
        }
    };

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(scrollToBottom, [messages]);

    const sendMessage = async () => {
        if (!input.trim()) return;

        const userMsg: Message = { id: Date.now().toString(), role: "user", content: input, timestamp: new Date() };
        setMessages(prev => [...prev, userMsg]);
        setInput("");

        try {
            setTimeout(() => {
                const aiMsg: Message = {
                    id: (Date.now() + 1).toString(),
                    role: "assistant",
                    content: `Processing with ${customKey ? "Custom API Model" : "Default Aegion Model"}...\n\nI've analyzed your request against the current Project Graph.`,
                    timestamp: new Date()
                };
                setMessages(prev => [...prev, aiMsg]);
            }, 1000);

            // Use api.post("/chat", ...) in real implementation
        } catch (err) {
            console.error("Failed to send message", err);
        }
    };

    return (
        <div className="h-full flex overflow-hidden">
            {/* Left: Chat Interface */}
            <div
                className="w-1/2 flex flex-col"
                style={{ borderRight: "1px solid var(--border-default)", background: "hsla(248, 8%, 5%, 0.5)", backdropFilter: "blur(12px)" }}
            >
                {/* Chat Header */}
                <div
                    className="p-4 flex items-center justify-between"
                    style={{ borderBottom: "1px solid var(--border-default)" }}
                >
                    <div className="flex items-center gap-2">
                        <Cpu style={{ color: "var(--accent-reason)" }} />
                        <span className="font-semibold" style={{ color: "var(--text-primary)" }}>Aegion Core</span>
                    </div>
                    <button
                        onClick={() => setShowKeyInput(!showKeyInput)}
                        className="p-2 rounded-lg transition-colors"
                        style={{
                            color: customKey ? "var(--accent-trust)" : "var(--text-muted)",
                            background: customKey ? "hsla(150, 90%, 55%, 0.08)" : "transparent",
                        }}
                        title="Configure Custom API Key"
                    >
                        <Key size={18} />
                    </button>
                </div>

                {/* Custom Key Input */}
                {showKeyInput && (
                    <div
                        className="p-4 animate-slide-down"
                        style={{ background: "hsla(260, 20%, 80%, 0.03)", borderBottom: "1px solid var(--border-default)" }}
                    >
                        <label className="text-xs mb-1 block" style={{ color: "var(--text-muted)" }}>Custom LLM API Key (Client-Side Override)</label>
                        <input
                            type="password"
                            value={customKey}
                            onChange={(e) => saveKey(e.target.value)}
                            placeholder="sk-..."
                            className="glass-input w-full px-3 py-2 text-sm"
                        />
                        <p className="text-[10px] mt-1" style={{ color: "var(--text-ghost)" }}>Key is stored locally in your browser and injected into headers.</p>
                    </div>
                )}

                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 smooth-scroll">
                    {messages.map(msg => (
                        <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                            <div
                                className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                                style={{
                                    background: msg.role === 'user' ? "hsla(260, 20%, 80%, 0.08)" : "hsla(260, 100%, 70%, 0.12)",
                                }}
                            >
                                {msg.role === 'user'
                                    ? <User size={14} style={{ color: "var(--text-secondary)" }} />
                                    : <Cpu size={14} style={{ color: "var(--accent-reason)" }} />
                                }
                            </div>
                            <div
                                className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${msg.role === 'user' ? 'rounded-tr-sm' : 'rounded-tl-sm'}`}
                                style={{
                                    background: msg.role === 'user'
                                        ? "hsla(260, 20%, 80%, 0.08)"
                                        : "hsla(260, 100%, 70%, 0.06)",
                                    color: msg.role === 'user' ? "var(--text-primary)" : "var(--text-secondary)",
                                    border: msg.role === 'assistant' ? "1px solid hsla(260, 100%, 70%, 0.12)" : "none",
                                }}
                            >
                                {msg.content}
                            </div>
                        </div>
                    ))}
                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="p-4" style={{ borderTop: "1px solid var(--border-default)", background: "hsla(248, 8%, 4%, 0.6)" }}>
                    <div className="relative">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                            placeholder="Type a message to the Council..."
                            className="glass-input w-full pl-4 pr-12 py-3 text-sm"
                        />
                        <button
                            onClick={sendMessage}
                            className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg transition-colors"
                            style={{
                                background: "var(--gradient-primary)",
                                color: "white",
                            }}
                        >
                            <Send size={14} />
                        </button>
                    </div>
                </div>
            </div>

            {/* Right: Context/Graph */}
            <div className="w-1/2 flex flex-col" style={{ background: "hsla(248, 8%, 4%, 0.6)" }}>
                <div
                    className="p-3 text-xs font-medium uppercase tracking-wider"
                    style={{
                        borderBottom: "1px solid var(--border-default)",
                        background: "hsla(248, 8%, 4%, 0.4)",
                        color: "var(--text-muted)",
                        fontFamily: "var(--font-mono)",
                    }}
                >
                    Live Context Visualization
                </div>
                <div className="flex-1 min-h-0 p-4">
                    <ProjectGraph />
                </div>
            </div>
        </div>
    );
}
