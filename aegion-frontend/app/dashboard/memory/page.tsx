"use client";

import { useState } from "react";
import { Brain, Search, Trash2, Tag } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { MOCK_MEMORIES } from "@/lib/mock-data";
import { formatDistanceToNow } from "date-fns";

const typeVariants: Record<string, "info" | "success" | "purple" | "warning"> = {
    preference: "info",
    decision: "success",
    fact: "purple",
};

export default function MemoryPage() {
    const [search, setSearch] = useState("");
    const [memories, setMemories] = useState(MOCK_MEMORIES);

    const filtered = memories.filter(
        (m) =>
            m.concept.toLowerCase().includes(search.toLowerCase()) ||
            m.content.toLowerCase().includes(search.toLowerCase())
    );

    const handleForget = (id: string) => {
        setMemories((prev) => prev.filter((m) => m.id !== id));
    };

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div>
                <h1 className="text-2xl font-bold text-white">Memory</h1>
                <p className="text-sm text-slate-500 mt-1">
                    Stored preferences, decisions, and facts from council interactions
                </p>
            </div>

            {/* Search */}
            <div className="relative max-w-md">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search memories..."
                    className="glass-input w-full pl-10 pr-4 py-2.5 text-sm"
                />
            </div>

            {/* Memory Cards */}
            <div className="space-y-2">
                {filtered.map((mem) => (
                    <div key={mem.id} className="glass-card p-5">
                        <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-2">
                                    <Badge variant={typeVariants[mem.type] || "neutral"} size="sm">
                                        <Tag size={10} className="mr-1" />
                                        {mem.type}
                                    </Badge>
                                    <span className="text-xs text-slate-500">
                                        Confidence: {(mem.confidence * 100).toFixed(0)}%
                                    </span>
                                </div>
                                <h3 className="text-sm font-medium text-white mb-1">{mem.concept}</h3>
                                <p className="text-xs text-slate-400 leading-relaxed">{mem.content}</p>
                                <p className="text-[10px] text-slate-600 mt-2">
                                    Stored {formatDistanceToNow(new Date(mem.createdAt), { addSuffix: true })}
                                </p>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleForget(mem.id)}
                                className="text-slate-600 hover:text-red-400"
                            >
                                <Trash2 size={14} />
                            </Button>
                        </div>
                    </div>
                ))}

                {filtered.length === 0 && (
                    <div className="text-center py-16 text-slate-500">
                        <Brain size={32} className="mx-auto mb-3 opacity-30" />
                        <p className="text-sm">No memories found</p>
                    </div>
                )}
            </div>
        </div>
    );
}
