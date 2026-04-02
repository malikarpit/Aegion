"use client";

import { useState } from "react";
import { FileText, Plus, Search } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { MOCK_ADRS } from "@/lib/mock-data";
import { formatDistanceToNow } from "date-fns";

const statusVariants: Record<string, "success" | "warning" | "danger" | "neutral" | "purple"> = {
    accepted: "success",
    proposed: "warning",
    superseded: "neutral",
    deprecated: "danger",
};

export default function ADRsPage() {
    const [search, setSearch] = useState("");
    const [selectedADR, setSelectedADR] = useState<typeof MOCK_ADRS[0] | null>(null);
    const [showCreate, setShowCreate] = useState(false);

    const filtered = MOCK_ADRS.filter(
        (a) =>
            a.title.toLowerCase().includes(search.toLowerCase()) ||
            a.id.toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Architecture Decision Records</h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Track architectural decisions and their lifecycle
                    </p>
                </div>
                <Button variant="primary" size="md" icon={<Plus size={16} />} onClick={() => setShowCreate(true)}>
                    New ADR
                </Button>
            </div>

            {/* Search */}
            <div className="relative max-w-md">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search ADRs..."
                    className="glass-input w-full pl-10 pr-4 py-2.5 text-sm"
                />
            </div>

            {/* ADR List */}
            <div className="space-y-2">
                {filtered.map((adr) => (
                    <div
                        key={adr.id}
                        onClick={() => setSelectedADR(adr)}
                        className="glass-card p-5 cursor-pointer"
                    >
                        <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-3 mb-1.5">
                                    <span className="text-xs font-mono text-slate-500">{adr.id}</span>
                                    <Badge variant={statusVariants[adr.status] || "neutral"} size="sm" dot>
                                        {adr.status}
                                    </Badge>
                                </div>
                                <h3 className="text-sm font-medium text-white">{adr.title}</h3>
                                <p className="text-xs text-slate-500 mt-1.5 line-clamp-2">
                                    {adr.summary}
                                </p>
                            </div>
                            <div className="text-right shrink-0">
                                <p className="text-[11px] text-slate-600">
                                    {formatDistanceToNow(new Date(adr.createdAt), { addSuffix: true })}
                                </p>
                                <p className="text-[10px] text-slate-600 mt-0.5">by {adr.author}</p>
                            </div>
                        </div>
                    </div>
                ))}

                {filtered.length === 0 && (
                    <div className="text-center py-16 text-slate-500">
                        <FileText size={32} className="mx-auto mb-3 opacity-30" />
                        <p className="text-sm">No ADRs match your search</p>
                    </div>
                )}
            </div>

            {/* ADR Detail Modal */}
            <Modal
                open={!!selectedADR}
                onClose={() => setSelectedADR(null)}
                title={selectedADR?.title}
                description={selectedADR?.id}
                size="lg"
            >
                {selectedADR && (
                    <div className="space-y-4">
                        <div className="flex items-center gap-3">
                            <Badge variant={statusVariants[selectedADR.status] || "neutral"} dot>
                                {selectedADR.status}
                            </Badge>
                            <span className="text-xs text-slate-500">
                                Created by {selectedADR.author} · {formatDistanceToNow(new Date(selectedADR.createdAt), { addSuffix: true })}
                            </span>
                        </div>

                        <div>
                            <h4 className="text-xs font-medium text-slate-500 uppercase mb-2">Context & Decision</h4>
                            <p className="text-sm text-slate-300 leading-relaxed">{selectedADR.summary}</p>
                        </div>

                        <div className="bg-white/[0.02] border border-white/5 rounded-lg p-4">
                            <h4 className="text-xs font-medium text-slate-500 uppercase mb-2">Consequences</h4>
                            <ul className="text-sm text-slate-400 space-y-1 list-disc list-inside">
                                <li>Reduces external service dependencies</li>
                                <li>Requires team to learn new patterns</li>
                                <li>Improves system reliability and latency</li>
                            </ul>
                        </div>
                    </div>
                )}
            </Modal>

            {/* Create ADR Modal */}
            <Modal
                open={showCreate}
                onClose={() => setShowCreate(false)}
                title="Create New ADR"
                description="Document an architectural decision"
                size="lg"
                footer={
                    <>
                        <Button variant="secondary" onClick={() => setShowCreate(false)}>Cancel</Button>
                        <Button variant="primary" onClick={() => setShowCreate(false)}>Create ADR</Button>
                    </>
                }
            >
                <div className="space-y-4">
                    <div>
                        <label className="text-xs text-slate-400 mb-1.5 block">Title</label>
                        <input type="text" placeholder="ADR title..." className="glass-input w-full px-4 py-2.5 text-sm" />
                    </div>
                    <div>
                        <label className="text-xs text-slate-400 mb-1.5 block">Context</label>
                        <textarea rows={3} placeholder="Why is this decision needed?" className="glass-input w-full px-4 py-2.5 text-sm resize-none" />
                    </div>
                    <div>
                        <label className="text-xs text-slate-400 mb-1.5 block">Decision</label>
                        <textarea rows={4} placeholder="What is the decision and rationale?" className="glass-input w-full px-4 py-2.5 text-sm resize-none" />
                    </div>
                    <div>
                        <label className="text-xs text-slate-400 mb-1.5 block">Status</label>
                        <select className="glass-input w-full px-4 py-2.5 text-sm">
                            <option value="proposed" className="bg-[#111118]">Proposed</option>
                            <option value="accepted" className="bg-[#111118]">Accepted</option>
                        </select>
                    </div>
                </div>
            </Modal>
        </div>
    );
}
