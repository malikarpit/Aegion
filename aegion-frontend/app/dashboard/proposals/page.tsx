"use client";

import { useState } from "react";
import { FileCheck, CheckCircle2, XCircle, Clock, Eye } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Tabs } from "@/components/ui/Tabs";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { MOCK_PROPOSALS } from "@/lib/mock-data";
import { formatDistanceToNow } from "date-fns";

const statusConfig: Record<string, { variant: "success" | "warning" | "danger" | "neutral"; icon: React.ReactNode }> = {
    approved: { variant: "success", icon: <CheckCircle2 size={12} /> },
    pending: { variant: "warning", icon: <Clock size={12} /> },
    rejected: { variant: "danger", icon: <XCircle size={12} /> },
};

const tierColors: Record<string, string> = {
    T1: "text-slate-400 bg-slate-500/10 border-slate-500/20",
    T2: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    T3: "text-purple-400 bg-purple-500/10 border-purple-500/20",
};

export default function ProposalsPage() {
    const [selectedProposal, setSelectedProposal] = useState<typeof MOCK_PROPOSALS[0] | null>(null);

    const tabs = [
        { id: "all", label: "All", count: MOCK_PROPOSALS.length },
        { id: "pending", label: "Pending", count: MOCK_PROPOSALS.filter((p) => p.status === "pending").length },
        { id: "approved", label: "Approved", count: MOCK_PROPOSALS.filter((p) => p.status === "approved").length },
        { id: "rejected", label: "Rejected", count: MOCK_PROPOSALS.filter((p) => p.status === "rejected").length },
    ];

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Proposals</h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Governance proposals and decision history
                    </p>
                </div>
                <Button variant="primary" size="md" icon={<FileCheck size={16} />}>
                    New Proposal
                </Button>
            </div>

            <Tabs tabs={tabs} defaultTab="all">
                {(activeTab) => {
                    const filtered =
                        activeTab === "all"
                            ? MOCK_PROPOSALS
                            : MOCK_PROPOSALS.filter((p) => p.status === activeTab);

                    return (
                        <div className="space-y-2">
                            {filtered.map((proposal) => {
                                const cfg = statusConfig[proposal.status] || statusConfig.pending;

                                return (
                                    <div
                                        key={proposal.id}
                                        onClick={() => setSelectedProposal(proposal)}
                                        className="glass-card p-5 flex items-center gap-4 cursor-pointer"
                                    >
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-3 mb-1">
                                                <span className="text-xs font-mono text-slate-500">
                                                    {proposal.id}
                                                </span>
                                                <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${tierColors[proposal.tier]}`}>
                                                    {proposal.tier}
                                                </span>
                                            </div>
                                            <h3 className="text-sm font-medium text-white truncate">
                                                {proposal.title}
                                            </h3>
                                            <p className="text-xs text-slate-500 mt-1 truncate">
                                                {proposal.summary}
                                            </p>
                                        </div>

                                        <div className="flex items-center gap-4 shrink-0">
                                            {proposal.councilScore !== null && (
                                                <div className="text-right">
                                                    <p className="text-sm font-bold text-white">
                                                        {(proposal.councilScore * 100).toFixed(0)}%
                                                    </p>
                                                    <p className="text-[10px] text-slate-500">Score</p>
                                                </div>
                                            )}

                                            <Badge variant={cfg.variant} size="md" dot>
                                                {proposal.status}
                                            </Badge>

                                            <span className="text-[11px] text-slate-600 w-20 text-right">
                                                {formatDistanceToNow(new Date(proposal.createdAt), { addSuffix: true })}
                                            </span>
                                        </div>
                                    </div>
                                );
                            })}

                            {filtered.length === 0 && (
                                <div className="text-center py-16 text-slate-500">
                                    <FileCheck size={32} className="mx-auto mb-3 opacity-30" />
                                    <p className="text-sm">No proposals in this category</p>
                                </div>
                            )}
                        </div>
                    );
                }}
            </Tabs>

            {/* Proposal Detail Modal */}
            <Modal
                open={!!selectedProposal}
                onClose={() => setSelectedProposal(null)}
                title={selectedProposal?.title}
                description={`${selectedProposal?.id} · ${selectedProposal?.tier}`}
                size="lg"
                footer={
                    selectedProposal?.status === "pending" ? (
                        <>
                            <Button variant="danger" size="sm" icon={<XCircle size={14} />}>
                                Reject
                            </Button>
                            <Button variant="success" size="sm" icon={<CheckCircle2 size={14} />}>
                                Approve
                            </Button>
                        </>
                    ) : undefined
                }
            >
                {selectedProposal && (
                    <div className="space-y-4">
                        <div className="flex items-center gap-3">
                            <Badge variant={statusConfig[selectedProposal.status]?.variant || "neutral"} dot>
                                {selectedProposal.status}
                            </Badge>
                            {selectedProposal.councilScore !== null && (
                                <Badge variant="info">
                                    Council Score: {(selectedProposal.councilScore * 100).toFixed(0)}%
                                </Badge>
                            )}
                        </div>

                        <div>
                            <h4 className="text-xs font-medium text-slate-500 uppercase mb-2">Summary</h4>
                            <p className="text-sm text-slate-300 leading-relaxed">
                                {selectedProposal.summary}
                            </p>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-white/[0.02] rounded-lg p-3">
                                <p className="text-[10px] text-slate-500 uppercase mb-1">Author</p>
                                <p className="text-sm text-white">{selectedProposal.author}</p>
                            </div>
                            <div className="bg-white/[0.02] rounded-lg p-3">
                                <p className="text-[10px] text-slate-500 uppercase mb-1">Created</p>
                                <p className="text-sm text-white">
                                    {formatDistanceToNow(new Date(selectedProposal.createdAt), { addSuffix: true })}
                                </p>
                            </div>
                        </div>
                    </div>
                )}
            </Modal>
        </div>
    );
}
