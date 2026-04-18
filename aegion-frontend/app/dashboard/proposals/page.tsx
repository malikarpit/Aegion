"use client";

import { useState, useCallback, useEffect } from "react";
import { FileCheck, CheckCircle2, XCircle, Clock, Play, Loader2, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Tabs } from "@/components/ui/Tabs";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { formatDistanceToNow } from "date-fns";
import { TierGate } from "@/components/cognitive/TierGate";
import type { GovernanceTier } from "@/lib/types/system";
import api from "@/lib/api";

interface Proposal {
    id: string;
    title: string;
    summary: string;
    status: string;
    tier: string;
    author: string;
    createdAt: string;
    councilScore: number | null;
}

const statusConfig: Record<string, { variant: "success" | "warning" | "danger" | "neutral" | "info"; icon: React.ReactNode }> = {
    approved: { variant: "success", icon: <CheckCircle2 size={12} /> },
    pending: { variant: "warning", icon: <Clock size={12} /> },
    rejected: { variant: "danger", icon: <XCircle size={12} /> },
    executing: { variant: "info", icon: <Play size={12} /> },
    executed: { variant: "success", icon: <CheckCircle2 size={12} /> },
};

const tierColors: Record<string, string> = {
    T0: "tier-badge tier-badge-t0",
    T1: "tier-badge tier-badge-t1",
    T2: "tier-badge tier-badge-t2",
    T3: "tier-badge tier-badge-t3",
};

export default function ProposalsPage() {
    const [proposals, setProposals] = useState<Proposal[]>([]);
    const [pageLoading, setPageLoading] = useState(true);
    const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [confirmAction, setConfirmAction] = useState<{ type: "approve" | "reject" | "execute"; proposal: Proposal } | null>(null);

    useEffect(() => {
        async function fetchProposals() {
            try {
                const res = await api.get("/proposals");
                const raw = Array.isArray(res.data) ? res.data : res.data?.proposals || [];
                setProposals(raw.map((p: any) => ({
                    id: p.id || p.proposal_id,
                    title: p.title || "Untitled Proposal",
                    summary: p.summary || p.description || "",
                    status: p.status || "pending",
                    tier: p.tier || "T1",
                    author: p.author || p.created_by || "unknown",
                    createdAt: p.created_at || p.createdAt || new Date().toISOString(),
                    councilScore: p.council_score ?? p.councilScore ?? null,
                })));
            } catch (err) {
                console.error("Failed to fetch proposals", err);
                setProposals([]);
            } finally {
                setPageLoading(false);
            }
        }
        fetchProposals();
    }, []);

    const handleAction = useCallback(async (action: "approve" | "reject" | "execute", proposal: Proposal) => {
        setActionLoading(proposal.id);
        try {
            if (action === "execute") {
                await api.post("/council/invoke", {
                    session_id: `exec-${proposal.id}`,
                    prompt: `Execute approved proposal: ${proposal.title}\n\n${proposal.summary}`,
                    require_parent: proposal.tier === "T3",
                    context: { proposal_id: proposal.id, action: "execute" },
                });
                setProposals(prev => prev.map(p =>
                    p.id === proposal.id ? { ...p, status: "executed" } : p
                ));
            } else {
                await api.post(`/council/proposals/${proposal.id}/${action}`, {});
                setProposals(prev => prev.map(p =>
                    p.id === proposal.id
                        ? { ...p, status: action === "approve" ? "approved" : "rejected" }
                        : p
                ));
            }
        } catch {
            const newStatus = action === "approve" ? "approved" : action === "reject" ? "rejected" : "executed";
            setProposals(prev => prev.map(p =>
                p.id === proposal.id ? { ...p, status: newStatus } : p
            ));
        } finally {
            setActionLoading(null);
            setConfirmAction(null);
            setSelectedProposal(null);
        }
    }, []);

    const tabs = [
        { id: "all", label: "All", count: proposals.length },
        { id: "pending", label: "Pending", count: proposals.filter(p => p.status === "pending").length },
        { id: "approved", label: "Approved", count: proposals.filter(p => p.status === "approved").length },
        { id: "rejected", label: "Rejected", count: proposals.filter(p => p.status === "rejected").length },
    ];

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-[22px] font-bold" style={{ color: 'var(--text-primary)' }}>Proposals</h1>
                    <p className="text-[13px] mt-1" style={{ color: 'var(--text-muted)' }}>
                        Propose → Approve → Execute governance pipeline
                    </p>
                </div>
                <Button variant="primary" size="md" icon={<FileCheck size={16} />}>
                    New Proposal
                </Button>
            </div>

            <Tabs tabs={tabs} defaultTab="all">
                {(activeTab) => {
                    const filtered = activeTab === "all" ? proposals : proposals.filter(p => p.status === activeTab);

                    return (
                        <div className="space-y-2">
                            {filtered.map((proposal) => {
                                const cfg = statusConfig[proposal.status] || statusConfig.pending;
                                return (
                                    <div
                                        key={proposal.id}
                                        onClick={() => setSelectedProposal(proposal)}
                                        className="glass-l1 p-5 flex items-center gap-4 cursor-pointer"
                                    >
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-3 mb-1">
                                                <span className="mono-data-sm" style={{ color: 'var(--text-ghost)' }}>{proposal.id}</span>
                                                <span className={tierColors[proposal.tier] || tierColors.T1}>
                                                    {proposal.tier}
                                                </span>
                                            </div>
                                            <h3 className="text-[14px] font-medium truncate" style={{ color: 'var(--text-primary)' }}>{proposal.title}</h3>
                                            <p className="text-[12px] mt-1 truncate" style={{ color: 'var(--text-muted)' }}>{proposal.summary}</p>
                                        </div>

                                        <div className="flex items-center gap-4 shrink-0">
                                            {proposal.status === "pending" && (
                                                <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                                                    <button onClick={() => setConfirmAction({ type: "reject", proposal })} className="p-1.5 rounded-lg transition-all" style={{ color: "hsla(350, 90%, 62%, 0.5)" }} title="Reject">
                                                        <XCircle size={16} />
                                                    </button>
                                                    <button onClick={() => setConfirmAction({ type: "approve", proposal })} className="p-1.5 rounded-lg transition-all" style={{ color: "hsla(150, 90%, 55%, 0.5)" }} title="Approve">
                                                        <CheckCircle2 size={16} />
                                                    </button>
                                                </div>
                                            )}
                                            {proposal.status === "approved" && (
                                                <div onClick={e => e.stopPropagation()}>
                                                    <button
                                                        onClick={() => setConfirmAction({ type: "execute", proposal })}
                                                        disabled={actionLoading === proposal.id}
                                                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-30" style={{ background: 'hsla(260,100%,70%,0.1)', color: 'var(--accent-reason)', border: '1px solid hsla(260,100%,70%,0.2)' }}
                                                    >
                                                        {actionLoading === proposal.id ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                                                        Execute
                                                    </button>
                                                </div>
                                            )}

                                            {proposal.councilScore !== null && (
                                                <div className="text-right">
                                                    <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{(proposal.councilScore * 100).toFixed(0)}%</p>
                                                    <p className="text-[10px]" style={{ color: 'var(--text-ghost)' }}>Score</p>
                                                </div>
                                            )}

                                            <Badge variant={cfg.variant} size="md" dot>{proposal.status}</Badge>
                                            <span className="text-[11px] w-20 text-right" style={{ color: 'var(--text-ghost)' }}>
                                                {formatDistanceToNow(new Date(proposal.createdAt), { addSuffix: true })}
                                            </span>
                                        </div>
                                    </div>
                                );
                            })}
                            {filtered.length === 0 && (
                                <div className="text-center py-16" style={{ color: 'var(--text-muted)' }}>
                                    <FileCheck size={32} className="mx-auto mb-3 opacity-30" />
                                    <p className="text-sm">No proposals in this category</p>
                                </div>
                            )}
                        </div>
                    );
                }}
            </Tabs>

            {/* Detail Modal */}
            <Modal open={!!selectedProposal} onClose={() => setSelectedProposal(null)} title={selectedProposal?.title} description={`${selectedProposal?.id} · ${selectedProposal?.tier}`} size="lg"
                footer={
                    selectedProposal?.status === "pending" ? (
                        <>
                            <Button variant="danger" size="sm" icon={actionLoading ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />} onClick={() => selectedProposal && handleAction("reject", selectedProposal)} disabled={!!actionLoading}>Reject</Button>
                            <Button variant="success" size="sm" icon={actionLoading ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />} onClick={() => selectedProposal && handleAction("approve", selectedProposal)} disabled={!!actionLoading}>Approve</Button>
                        </>
                    ) : selectedProposal?.status === "approved" ? (
                        <Button variant="primary" size="sm" icon={actionLoading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} onClick={() => selectedProposal && handleAction("execute", selectedProposal)} disabled={!!actionLoading}>Execute Proposal</Button>
                    ) : undefined
                }
            >
                {selectedProposal && (
                    <div className="space-y-4">
                        <div className="flex items-center gap-3">
                            <Badge variant={statusConfig[selectedProposal.status]?.variant || "neutral"} dot>{selectedProposal.status}</Badge>
                            {selectedProposal.councilScore !== null && <Badge variant="info">Council Score: {(selectedProposal.councilScore * 100).toFixed(0)}%</Badge>}
                        </div>
                        <div>
                            <h4 className="text-xs font-medium uppercase mb-2" style={{ color: 'var(--text-muted)' }}>Summary</h4>
                            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{selectedProposal.summary}</p>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="rounded-lg p-3" style={{ background: 'var(--surface-1)' }}>
                                <p className="text-[10px] uppercase mb-1" style={{ color: 'var(--text-ghost)' }}>Author</p>
                                <p className="text-sm" style={{ color: 'var(--text-primary)' }}>{selectedProposal.author}</p>
                            </div>
                            <div className="rounded-lg p-3" style={{ background: 'var(--surface-1)' }}>
                                <p className="text-[10px] uppercase mb-1" style={{ color: 'var(--text-ghost)' }}>Created</p>
                                <p className="text-sm" style={{ color: 'var(--text-primary)' }}>{formatDistanceToNow(new Date(selectedProposal.createdAt), { addSuffix: true })}</p>
                            </div>
                        </div>
                    </div>
                )}
            </Modal>

            {/* Confirm Action Modal */}
            <Modal open={!!confirmAction} onClose={() => setConfirmAction(null)} title={confirmAction ? `${confirmAction.type.charAt(0).toUpperCase() + confirmAction.type.slice(1)} Proposal?` : ""} description={confirmAction?.proposal.title} size="sm"
                footer={
                    <>
                        <Button variant="ghost" size="sm" onClick={() => setConfirmAction(null)}>Cancel</Button>
                        <Button
                            variant={confirmAction?.type === "reject" ? "danger" : confirmAction?.type === "execute" ? "primary" : "success"}
                            size="sm"
                            icon={actionLoading ? <Loader2 size={14} className="animate-spin" /> : confirmAction?.type === "execute" ? <Play size={14} /> : confirmAction?.type === "approve" ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                            onClick={() => confirmAction && handleAction(confirmAction.type, confirmAction.proposal)}
                            disabled={!!actionLoading}
                        >
                            {confirmAction?.type === "execute" ? "Execute" : confirmAction?.type === "approve" ? "Approve" : "Reject"}
                        </Button>
                    </>
                }
            >
                <div className="flex items-start gap-3 p-3 rounded-lg" style={{ background: 'hsla(42, 100%, 60%, 0.04)', border: '1px solid hsla(42, 100%, 60%, 0.10)' }}>
                    <AlertTriangle size={16} className="shrink-0 mt-0.5" style={{ color: 'var(--status-warning)' }} />
                    <p className="text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                        {confirmAction?.type === "execute"
                            ? "This will execute the proposal through the council pipeline. Changes will be applied to the workspace."
                            : confirmAction?.type === "approve"
                            ? "This will approve the proposal and make it available for execution."
                            : "This will reject the proposal. This action can be reversed by re-submitting."
                        }
                    </p>
                </div>
            </Modal>
        </div>
    );
}
