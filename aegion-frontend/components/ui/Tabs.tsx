"use client";

import { useState, ReactNode } from "react";
import { motion } from "framer-motion";

interface Tab {
  id: string;
  label: string;
  icon?: ReactNode;
  count?: number;
}

interface TabsProps {
  tabs: Tab[];
  defaultTab?: string;
  onChange?: (tabId: string) => void;
  children: (activeTab: string) => ReactNode;
  className?: string;
}

export function Tabs({
  tabs,
  defaultTab,
  onChange,
  children,
  className = "",
}: TabsProps) {
  const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.id || "");

  const handleChange = (id: string) => {
    setActiveTab(id);
    onChange?.(id);
  };

  return (
    <div className={className}>
      {/* Tab Bar */}
      <div
        className="flex items-center gap-1 p-1 rounded-xl mb-6 overflow-x-auto"
        style={{ background: "hsla(260, 20%, 80%, 0.02)", border: "1px solid var(--border-subtle)" }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleChange(tab.id)}
            className={`
              relative flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium
              transition-colors duration-200 whitespace-nowrap
              ${activeTab === tab.id
                  ? ""
                  : ""
              }
            `}
          >
            {activeTab === tab.id && (
              <motion.div
                layoutId="activeTab"
                className="absolute inset-0 rounded-lg"
                style={{ background: "hsla(260, 20%, 80%, 0.06)", border: "1px solid var(--border-default)" }}
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
            <span className="relative flex items-center gap-2" style={{ color: activeTab === tab.id ? "var(--text-primary)" : "var(--text-muted)" }}>
              {tab.icon}
              {tab.label}
              {tab.count !== undefined && (
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                  style={{
                    background: activeTab === tab.id ? "hsla(260, 100%, 70%, 0.12)" : "hsla(260, 20%, 80%, 0.05)",
                    color: activeTab === tab.id ? "var(--accent-reason)" : "var(--text-muted)",
                  }}
                >
                  {tab.count}
                </span>
              )}
            </span>
          </button>
        ))}
      </div>

      {/* Content */}
      <motion.div
        key={activeTab}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.15 }}
      >
        {children(activeTab)}
      </motion.div>
    </div>
  );
}
