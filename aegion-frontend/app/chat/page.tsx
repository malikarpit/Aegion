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
        // Load existing custom key
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
            // Mock streaming response for MVP
            // In real impl, would use fetch + ReadableStream
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
            <div className="w-1/2 flex flex-col border-r border-white/10 bg-black/20 backdrop-blur-md">
                {/* Chat Header */}
                <div className="p-4 border-b border-white/10 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Cpu className="text-blue-400" />
                        <span className="font-semibold text-white">Aegion Core</span>
                    </div>
                    <button
                        onClick={() => setShowKeyInput(!showKeyInput)}
                        className={`p-2 rounded-lg transition-colors ${customKey ? "text-green-400 bg-green-500/10" : "text-slate-400 hover:text-white hover:bg-white/5"}`}
                        title="Configure Custom API Key"
                    >
                        <Key size={18} />
                    </button>
                </div>

                {/* Custom Key Input */}
                {showKeyInput && (
                    <div className="p-4 bg-white/5 border-b border-white/10 animate-in slide-in-from-top-2">
                        <label className="text-xs text-slate-400 mb-1 block">Custom LLM API Key (Client-Side Override)</label>
                        <input
                            type="password"
                            value={customKey}
                            onChange={(e) => saveKey(e.target.value)}
                            placeholder="sk-..."
                            className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                        />
                        <p className="text-[10px] text-slate-500 mt-1">Key is stored locally in your browser and injected into headers.</p>
                    </div>
                )}

                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
                    {messages.map(msg => (
                        <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-white/10' : 'bg-blue-600/20'}`}>
                                {msg.role === 'user' ? <User size={14} /> : <Cpu size={14} className="text-blue-400" />}
                            </div>
                            <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${msg.role === 'user'
                                    ? 'bg-white/10 text-white rounded-tr-sm'
                                    : 'bg-blue-600/10 text-slate-200 border border-blue-500/20 rounded-tl-sm'
                                }`}>
                                {msg.content}
                            </div>
                        </div>
                    ))}
                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="p-4 border-t border-white/10 bg-black/40">
                    <div className="relative">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                            placeholder="Type a message to the Council..."
                            className="w-full bg-white/5 border border-white/10 rounded-xl pl-4 pr-12 py-3 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-colors placeholder:text-slate-600"
                        />
                        <button
                            onClick={sendMessage}
                            className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors"
                        >
                            <Send size={14} />
                        </button>
                    </div>
                </div>
            </div>

            {/* Right: Context/Graph */}
            <div className="w-1/2 flex flex-col bg-black/40">
                <div className="p-3 border-b border-white/10 bg-black/20 text-xs font-medium text-slate-400 uppercase tracking-wider">
                    Live Context Visualization
                </div>
                <div className="flex-1 min-h-0 p-4">
                    <ProjectGraph />
                </div>
            </div>
        </div>
    );
}
