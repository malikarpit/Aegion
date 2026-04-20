"use client";

import React, {
  createContext,
  useContext,
  useReducer,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import type {
  SystemState,
  SystemAction,
  CognitiveMode,
  SystemEvent,
  DegradationStage,
} from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   SYSTEM CONTEXT — Persistent state across all navigation.
   Single source of truth. Reads from WebSocket or REST fallback.
   ══════════════════════════════════════════════════════════════ */

// ── Initial State ──
const initialState: SystemState = {
  session: null,
  activeDecision: null,
  risk: {
    score: 0,
    level: "low",
    trend: "stable",
    trendDelta: 0,
    activeAlerts: 0,
    topAlert: null,
  },
  governance: {
    frozen: false,
    pendingApprovals: 0,
    pendingByTier: { T1: 0, T2: 0, T3: 0 },
    activePipelines: 0,
  },
  system: {
    thinking: false,
    backendStatus: "connected",
    degradationStage: "healthy",
    lastSync: Date.now(),
    uptime: 0,
    activeAgents: [],
  },
  temporal: {
    totalDecisions: 0,
    oldestDecisionAge: 0,
    recentDecisionRate: 0,
    lastSystemEvent: null,
  },
  systemEvents: [],
  activeInterruption: null,
  focusMode: false,
};

// ── Degradation stage calculator ──
function computeDegradationStage(disconnectedSince?: number): DegradationStage {
  if (!disconnectedSince) return "healthy";
  const elapsed = Date.now() - disconnectedSince;
  if (elapsed > 15 * 60 * 1000) return "critical";  // >15 min
  if (elapsed > 5 * 60 * 1000) return "extended";    // >5 min
  return "degraded";                                    // 0-5 min
}

// ── Reducer ──
function systemReducer(state: SystemState, action: SystemAction): SystemState {
  switch (action.type) {
    case "SESSION":
      return { ...state, session: action.payload };

    case "GOVERNANCE":
      return {
        ...state,
        governance: { ...state.governance, ...action.payload },
      };

    case "FREEZE":
      return {
        ...state,
        governance: {
          ...state.governance,
          frozen: action.payload.frozen,
          freezeReason: action.payload.reason,
        },
      };

    case "RISK":
      return {
        ...state,
        risk: { ...state.risk, ...action.payload },
      };

    case "ALERT":
      return {
        ...state,
        risk: {
          ...state.risk,
          activeAlerts: action.payload.count,
          topAlert: action.payload.topAlert,
        },
      };

    case "THINKING":
      return {
        ...state,
        system: {
          ...state.system,
          thinking: true,
          thinkingContext: action.payload.context,
        },
      };

    case "THINKING_DONE":
      return {
        ...state,
        system: {
          ...state.system,
          thinking: false,
          thinkingContext: undefined,
        },
      };

    case "SYSTEM_EVENT": {
      const event = action.payload;
      const newEvents = [event, ...state.systemEvents].slice(0, 50); // cap at 50
      // Critical events become active interruption
      const activeInterruption =
        event.priority === "critical" ? event : state.activeInterruption;
      return {
        ...state,
        systemEvents: newEvents,
        activeInterruption,
        temporal: {
          ...state.temporal,
          lastSystemEvent: {
            type: event.type,
            timestamp: event.timestamp,
            description: event.description,
          },
        },
      };
    }

    case "ACKNOWLEDGE_EVENT":
      return {
        ...state,
        systemEvents: state.systemEvents.map((e) =>
          e.id === action.payload.eventId ? { ...e, acknowledged: true } : e
        ),
        activeInterruption:
          state.activeInterruption?.id === action.payload.eventId
            ? null
            : state.activeInterruption,
      };

    case "DISMISS_INTERRUPTION":
      return { ...state, activeInterruption: null };

    case "SET_MODE":
      return state.session
        ? {
            ...state,
            session: { ...state.session, mode: action.payload },
          }
        : state;

    case "TOGGLE_FOCUS":
      return { ...state, focusMode: !state.focusMode };

    case "TICK_DURATION":
      return state.session?.status === "active"
        ? {
            ...state,
            session: {
              ...state.session,
              duration: state.session.duration + 1,
            },
          }
        : state;

    case "BACKEND_STATUS": {
      const bs = action.payload.status;
      const degradedSince =
        bs !== "connected"
          ? state.system.degradedSince ?? Date.now()
          : undefined;
      return {
        ...state,
        system: {
          ...state.system,
          backendStatus: bs,
          degradedSince,
          degradationStage: computeDegradationStage(degradedSince),
          lastSync: bs === "connected" ? Date.now() : state.system.lastSync,
        },
      };
    }

    case "ACTIVE_DECISION":
      return { ...state, activeDecision: action.payload };

    case "FULL_SYNC":
      return { ...state, ...action.payload };

    default:
      return state;
  }
}

// ── Context ──
interface SystemContextValue {
  state: SystemState;
  dispatch: React.Dispatch<SystemAction>;
  setMode: (mode: CognitiveMode) => void;
  toggleFocus: () => void;
  acknowledgeEvent: (eventId: string) => void;
  dismissInterruption: () => void;
}

const SystemContext = createContext<SystemContextValue | null>(null);

// ── Provider ──
export function SystemContextProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(systemReducer, initialState);

  // Session duration ticker
  useEffect(() => {
    if (state.session?.status !== "active") return;
    const timer = setInterval(() => {
      dispatch({ type: "TICK_DURATION", payload: {} });
    }, 1000);
    return () => clearInterval(timer);
  }, [state.session?.status]);

  // Degradation stage updater (check every 30s)
  useEffect(() => {
    if (state.system.backendStatus === "connected") return;
    const interval = setInterval(() => {
      const stage = computeDegradationStage(state.system.degradedSince);
      if (stage !== state.system.degradationStage) {
        dispatch({
          type: "FULL_SYNC",
          payload: { system: { ...state.system, degradationStage: stage } },
        });
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [state.system.backendStatus, state.system.degradedSince, state.system.degradationStage, state.system]);

  // Convenience dispatchers
  const setMode = useCallback(
    (mode: CognitiveMode) => dispatch({ type: "SET_MODE", payload: mode }),
    []
  );
  const toggleFocus = useCallback(
    () => dispatch({ type: "TOGGLE_FOCUS", payload: {} }),
    []
  );
  const acknowledgeEvent = useCallback(
    (eventId: string) =>
      dispatch({ type: "ACKNOWLEDGE_EVENT", payload: { eventId } }),
    []
  );
  const dismissInterruption = useCallback(
    () => dispatch({ type: "DISMISS_INTERRUPTION", payload: {} }),
    []
  );

  return (
    <SystemContext.Provider
      value={{
        state,
        dispatch,
        setMode,
        toggleFocus,
        acknowledgeEvent,
        dismissInterruption,
      }}
    >
      {children}
    </SystemContext.Provider>
  );
}

// ── Hook ──
export function useSystemContext(): SystemContextValue {
  const ctx = useContext(SystemContext);
  if (!ctx) {
    throw new Error("useSystemContext must be used within SystemContextProvider");
  }
  return ctx;
}

// ── Derived selectors ──
export function useSession() {
  const { state } = useSystemContext();
  return state.session;
}

export function useRisk() {
  const { state } = useSystemContext();
  return state.risk;
}

export function useGovernance() {
  const { state } = useSystemContext();
  return state.governance;
}

export function useSystemStatus() {
  const { state } = useSystemContext();
  return state.system;
}

export function useSystemEvents() {
  const { state } = useSystemContext();
  return state.systemEvents;
}

export function useActiveInterruption() {
  const { state, dismissInterruption, acknowledgeEvent } = useSystemContext();
  return {
    event: state.activeInterruption,
    dismiss: dismissInterruption,
    acknowledge: state.activeInterruption
      ? () => acknowledgeEvent(state.activeInterruption!.id)
      : undefined,
  };
}

export function useCognitiveMode(): [CognitiveMode, (m: CognitiveMode) => void] {
  const { state, setMode } = useSystemContext();
  return [state.session?.mode ?? "explore", setMode];
}

export function useFocusMode(): [boolean, () => void] {
  const { state, toggleFocus } = useSystemContext();
  return [state.focusMode, toggleFocus];
}

export function useIsDegraded() {
  const { state } = useSystemContext();
  return state.system.backendStatus !== "connected";
}
