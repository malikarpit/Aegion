"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useSystemContext } from "@/lib/context/SystemContext";
import type { WSChannel, WSMessage, WSPriority, SystemState, SystemEvent } from "@/lib/types/system";

/* ══════════════════════════════════════════════════════════════
   SYNC CONTEXT — WebSocket with Priority Channels
   
   Manages persistent connection to backend.
   Priority routing:
     critical → immediate dispatch
     high     → 100ms batch
     low      → 500ms batch
   
   Reconnect: exponential backoff (1s→2s→4s→8s→16s max)
   Heartbeat: 30s ping/pong
   ══════════════════════════════════════════════════════════════ */

type MessageHandler = (msg: WSMessage) => void;

interface SyncContextValue {
  status: "connecting" | "connected" | "disconnected";
  send: (channel: WSChannel, data: unknown) => void;
  subscribe: (channel: WSChannel, handler: MessageHandler) => () => void;
  lastError: string | null;
}

const SyncContext = createContext<SyncContextValue | null>(null);

// ── Priority batching queues ──
interface BatchQueue {
  messages: WSMessage[];
  timer: NodeJS.Timeout | null;
  delay: number;
}

export function SyncProvider({ children }: { children: ReactNode }) {
  const { dispatch } = useSystemContext();
  const [status, setStatus] = useState<SyncContextValue["status"]>("disconnected");
  const [lastError, setLastError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const handlersRef = useRef<Map<WSChannel, Set<MessageHandler>>>(new Map());
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatRef = useRef<NodeJS.Timeout | null>(null);
  const batchQueuesRef = useRef<Record<WSPriority, BatchQueue>>({
    critical: { messages: [], timer: null, delay: 0 },
    high: { messages: [], timer: null, delay: 100 },
    low: { messages: [], timer: null, delay: 500 },
  });

  // ── Process batched messages ──
  const processBatch = useCallback(
    (priority: WSPriority) => {
      const queue = batchQueuesRef.current[priority];
      const messages = queue.messages.splice(0);
      for (const msg of messages) {
        const handlers = handlersRef.current.get(msg.channel);
        if (handlers) {
          for (const handler of handlers) {
            try {
              handler(msg);
            } catch (e) {
              console.error(`[SyncContext] Handler error on ${msg.channel}:`, e);
            }
          }
        }
      }
    },
    []
  );

  // ── Route incoming message by priority ──
  const routeMessage = useCallback(
    (msg: WSMessage) => {
      const priority = msg.priority ?? "low";
      const queue = batchQueuesRef.current[priority];

      if (priority === "critical") {
        // Immediate dispatch
        queue.messages.push(msg);
        processBatch("critical");
      } else {
        queue.messages.push(msg);
        if (!queue.timer) {
          queue.timer = setTimeout(() => {
            processBatch(priority);
            queue.timer = null;
          }, queue.delay);
        }
      }
    },
    [processBatch]
  );

  // ── Map system channels to SystemContext actions ──
  const handleSystemMessage = useCallback(
    (msg: WSMessage) => {
      switch (msg.channel) {
        case "sentinel:risk":
          dispatch({ type: "RISK", payload: msg.data as Record<string, unknown> });
          break;
        case "sentinel:alerts":
          dispatch({
            type: "ALERT",
            payload: msg.data as { count: number; topAlert: string | null },
          });
          break;
        case "governance:freeze":
          dispatch({
            type: "FREEZE",
            payload: msg.data as { frozen: boolean; reason?: string },
          });
          break;
        case "governance:proposal":
          dispatch({
            type: "GOVERNANCE",
            payload: msg.data as Record<string, unknown>,
          });
          break;
        case "session:lifecycle":
          dispatch({ type: "SESSION", payload: msg.data as SystemState["session"] });
          break;
        case "ai:reasoning":
          dispatch({ type: "THINKING", payload: { context: (msg.data as { context?: string })?.context } });
          break;
        case "ai:response":
          dispatch({ type: "THINKING_DONE", payload: {} });
          break;
        case "system:initiative":
          dispatch({ type: "SYSTEM_EVENT", payload: msg.data as SystemEvent });
          break;
        case "system:heartbeat":
          // Just update lastSync
          break;
      }
    },
    [dispatch]
  );

  // ── Connect ──
  const connect = useCallback(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const wsUrl = apiUrl.replace(/^http/, "ws") + "/ws/sync";

    try {
      setStatus("connecting");
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("connected");
        setLastError(null);
        reconnectAttemptRef.current = 0;
        dispatch({ type: "BACKEND_STATUS", payload: { status: "connected" } });

        // Start heartbeat
        heartbeatRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ channel: "system:heartbeat", data: {} }));
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          handleSystemMessage(msg);
          routeMessage(msg);
        } catch (e) {
          console.error("[SyncContext] Parse error:", e);
        }
      };

      ws.onclose = () => {
        setStatus("disconnected");
        dispatch({ type: "BACKEND_STATUS", payload: { status: "degraded" } });
        clearInterval(heartbeatRef.current!);
        scheduleReconnect();
      };

      ws.onerror = (e) => {
        setLastError("WebSocket connection error");
        console.error("[SyncContext] WebSocket error:", e);
      };
    } catch (e) {
      setStatus("disconnected");
      setLastError(String(e));
      dispatch({ type: "BACKEND_STATUS", payload: { status: "disconnected" } });
      scheduleReconnect();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch, handleSystemMessage, routeMessage]);

  // ── Reconnect with exponential backoff ──
  const scheduleReconnect = useCallback(() => {
    const attempt = reconnectAttemptRef.current;
    const delay = Math.min(1000 * Math.pow(2, attempt), 16000);
    reconnectAttemptRef.current = attempt + 1;

    reconnectTimerRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [connect]);

  // ── Send ──
  const send = useCallback((channel: WSChannel, data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ channel, data, timestamp: Date.now() })
      );
    }
  }, []);

  // ── Subscribe ──
  const subscribe = useCallback(
    (channel: WSChannel, handler: MessageHandler) => {
      if (!handlersRef.current.has(channel)) {
        handlersRef.current.set(channel, new Set());
      }
      handlersRef.current.get(channel)!.add(handler);
      return () => {
        handlersRef.current.get(channel)?.delete(handler);
      };
    },
    []
  );

  // ── Lifecycle ──
  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      clearInterval(heartbeatRef.current!);
      clearTimeout(reconnectTimerRef.current!);
      // Clear batch timers
      for (const q of Object.values(batchQueuesRef.current)) {
        if (q.timer) clearTimeout(q.timer);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <SyncContext.Provider value={{ status, send, subscribe, lastError }}>
      {children}
    </SyncContext.Provider>
  );
}

export function useSync(): SyncContextValue {
  const ctx = useContext(SyncContext);
  if (!ctx) {
    throw new Error("useSync must be used within SyncProvider");
  }
  return ctx;
}

export function useChannel(channel: WSChannel, handler: MessageHandler) {
  const { subscribe } = useSync();
  useEffect(() => {
    return subscribe(channel, handler);
  }, [channel, handler, subscribe]);
}
