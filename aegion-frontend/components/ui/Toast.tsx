"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, CheckCircle2, AlertCircle, Info, AlertTriangle } from "lucide-react";

type ToastType = "success" | "error" | "info" | "warning";

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
}

interface ToastContextType {
  toast: (type: ToastType, title: string, description?: string) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
  warning: (title: string, description?: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

const iconMap = {
  success: <CheckCircle2 size={18} style={{ color: "var(--status-success)" }} />,
  error: <AlertCircle size={18} style={{ color: "var(--status-error)" }} />,
  info: <Info size={18} style={{ color: "var(--status-info)" }} />,
  warning: <AlertTriangle size={18} style={{ color: "var(--status-warning)" }} />,
};

const borderColors: Record<string, string> = {
  success: "var(--status-success)",
  error: "var(--status-error)",
  info: "var(--status-info)",
  warning: "var(--status-warning)",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback(
    (type: ToastType, title: string, description?: string) => {
      const id = Math.random().toString(36).slice(2);
      setToasts((prev) => [...prev.slice(-2), { id, type, title, description }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4000);
    },
    []
  );

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const ctx: ToastContextType = {
    toast: addToast,
    success: (t, d) => addToast("success", t, d),
    error: (t, d) => addToast("error", t, d),
    info: (t, d) => addToast("info", t, d),
    warning: (t, d) => addToast("warning", t, d),
  };

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      {/* Toast Container */}
      <div className="fixed bottom-4 right-4 z-[200] flex flex-col gap-2 w-80">
        <AnimatePresence mode="popLayout">
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 80, scale: 0.95 }}
              transition={{ duration: 0.25 }}
              className="rounded-xl p-4 shadow-2xl flex items-start gap-3"
              style={{
                background: "var(--surface-1)",
                border: "1px solid var(--border-default)",
                borderLeft: `3px solid ${borderColors[t.type]}`,
                boxShadow: "0 16px 48px hsla(248, 30%, 4%, 0.4)",
              }}
            >
              <div className="mt-0.5">{iconMap[t.type]}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{t.title}</p>
                {t.description && (
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>{t.description}</p>
                )}
              </div>
              <button
                onClick={() => removeToast(t.id)}
                className="transition-colors"
                style={{ color: "var(--text-muted)" }}
              >
                <X size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
