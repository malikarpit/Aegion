"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import api from "../api";

// ──────────────────────────────────────────────────────────────────────────────
// Generic fetch hook
// ──────────────────────────────────────────────────────────────────────────────

interface UseApiState<T> {
    data: T | null;
    loading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

function useApi<T>(url: string, deps: any[] = []): UseApiState<T> {
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetch = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await api.get(url);
            setData(res.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || "Request failed");
        } finally {
            setLoading(false);
        }
    }, [url]);

    useEffect(() => { fetch(); }, [fetch, ...deps]);

    return { data, loading, error, refetch: fetch };
}

// ──────────────────────────────────────────────────────────────────────────────
// Dashboard / Sessions
// ──────────────────────────────────────────────────────────────────────────────

export function useSessions() {
    const state = useApi<any[]>("/sessions");
    const active = state.data?.filter((s: any) => s.status === "active") || [];
    return { ...state, active, count: state.data?.length || 0 };
}

export function useProposals(status?: string) {
    const params = status ? `?status=${status}` : "";
    return useApi<any[]>(`/proposals${params}`);
}

export function useDecisions() {
    return useApi<any[]>("/decisions");
}

// ──────────────────────────────────────────────────────────────────────────────
// Council
// ──────────────────────────────────────────────────────────────────────────────

export function useCouncil() {
    const [streaming, setStreaming] = useState(false);
    const [messages, setMessages] = useState<any[]>([]);
    const eventSourceRef = useRef<EventSource | null>(null);

    const invoke = useCallback(async (prompt: string, councilType: string = "child") => {
        setStreaming(true);
        try {
            const res = await api.post("/council/invoke", {
                query: prompt,
                council_type: councilType,
            });
            setMessages((prev) => [...prev, res.data]);
            return res.data;
        } catch (err: any) {
            throw err;
        } finally {
            setStreaming(false);
        }
    }, []);

    const close = useCallback(() => {
        eventSourceRef.current?.close();
        setStreaming(false);
    }, []);

    return { invoke, streaming, messages, close };
}

// ──────────────────────────────────────────────────────────────────────────────
// Cost & Budget
// ──────────────────────────────────────────────────────────────────────────────

export function useBudget() {
    return useApi<any>("/model-settings/budget");
}

export function useUsageAnalytics(period: string = "7d", groupBy: string = "day") {
    return useApi<any>(`/model-settings/usage?period=${period}&group_by=${groupBy}`, [period, groupBy]);
}

export function useSetBudget() {
    const [loading, setLoading] = useState(false);

    const setBudget = useCallback(async (monthly: number, daily: number, autoPause: boolean = true) => {
        setLoading(true);
        try {
            const res = await api.put("/model-settings/budget", {
                monthly_limit_usd: monthly,
                daily_limit_usd: daily,
                auto_pause: autoPause,
            });
            return res.data;
        } finally {
            setLoading(false);
        }
    }, []);

    return { setBudget, loading };
}

// ──────────────────────────────────────────────────────────────────────────────
// Model Settings
// ──────────────────────────────────────────────────────────────────────────────

export function useModelSettings() {
    const state = useApi<any>("/model-settings/");

    const updateSetting = useCallback(async (path: string, value: any) => {
        await api.patch("/model-settings/setting", { path, value });
        state.refetch();
    }, [state.refetch]);

    return { ...state, updateSetting };
}

export function usePresets() {
    const state = useApi<any>("/model-settings/presets");

    const applyPreset = useCallback(async (preset: string) => {
        await api.post("/model-settings/preset", { preset });
        state.refetch();
    }, [state.refetch]);

    return { ...state, applyPreset };
}

export function useProviders() {
    const state = useApi<any>("/model-settings/providers");

    const testProvider = useCallback(async (providerId: string) => {
        const res = await api.post(`/model-settings/providers/${providerId}/test`);
        return res.data;
    }, []);

    return { ...state, testProvider };
}

export function useCascade() {
    const state = useApi<any>("/model-settings/cascade");

    const updateCascade = useCallback(async (order: string[], threshold: number) => {
        await api.put("/model-settings/cascade", {
            cascade_order: order,
            confidence_threshold: threshold,
            max_fallback_attempts: 3,
        });
        state.refetch();
    }, [state.refetch]);

    return { ...state, updateCascade };
}

// ──────────────────────────────────────────────────────────────────────────────
// Timeline (Chronos)
// ──────────────────────────────────────────────────────────────────────────────

export function useTimeline(limit: number = 20) {
    return useApi<any[]>(`/chronos/timeline?limit=${limit}`, [limit]);
}

// ──────────────────────────────────────────────────────────────────────────────
// Governance
// ──────────────────────────────────────────────────────────────────────────────

export function useGovernance() {
    const state = useApi<any>("/governance/status");

    const toggleFreeze = useCallback(async (freeze: boolean) => {
        if (freeze) {
            await api.post("/governance/freeze");
        } else {
            await api.post("/governance/unfreeze");
        }
        state.refetch();
    }, [state.refetch]);

    return { ...state, toggleFreeze };
}

// ──────────────────────────────────────────────────────────────────────────────
// Knowledge Graph
// ──────────────────────────────────────────────────────────────────────────────

export function useKnowledgeGraph() {
    return useApi<any>("/knowledge/graph");
}

// ──────────────────────────────────────────────────────────────────────────────
// Memory & Skills
// ──────────────────────────────────────────────────────────────────────────────

export function useMemories() {
    const state = useApi<any[]>("/memory");

    const createMemory = useCallback(async (content: string, type: string = "learned") => {
        await api.post("/memory", { content, type });
        state.refetch();
    }, [state.refetch]);

    const deleteMemory = useCallback(async (id: string) => {
        await api.delete(`/memory/${id}`);
        state.refetch();
    }, [state.refetch]);

    return { ...state, createMemory, deleteMemory };
}

export function useSkills() {
    const state = useApi<any[]>("/skills");

    const installSkill = useCallback(async (skillId: string) => {
        await api.post(`/skills/${skillId}/install`);
        state.refetch();
    }, [state.refetch]);

    return { ...state, installSkill };
}

// ──────────────────────────────────────────────────────────────────────────────
// Risk / Sentinel
// ──────────────────────────────────────────────────────────────────────────────

export function useRiskScore() {
    return useApi<any>("/sentinel/risk-score");
}

// ──────────────────────────────────────────────────────────────────────────────
// Health
// ──────────────────────────────────────────────────────────────────────────────

export function useHealth() {
    return useApi<any>("/health/ready");
}

// ──────────────────────────────────────────────────────────────────────────────
// Workspace
// ──────────────────────────────────────────────────────────────────────────────

export function useWorkspace() {
    const state = useApi<any>("/workspaces/current");

    const updateWorkspace = useCallback(async (updates: any) => {
        await api.put("/workspaces/current", updates);
        state.refetch();
    }, [state.refetch]);

    return { ...state, updateWorkspace };
}
