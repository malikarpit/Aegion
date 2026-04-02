"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import {
    LayoutDashboard,
    Network,
    MessageSquare,
    Clock,
    FileCheck,
    Settings,
    DollarSign,
    Brain,
    Puzzle,
    FileText,
    ShieldAlert,
    LogOut,
    User,
    ChevronDown,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useState } from "react";

interface NavItem {
    href: string;
    label: string;
    icon: React.ElementType;
    badge?: number;
}

interface NavSection {
    title: string;
    items: NavItem[];
}

const sections: NavSection[] = [
    {
        title: "Core",
        items: [
            { href: "/", label: "Dashboard", icon: LayoutDashboard },
            { href: "/dashboard/timeline", label: "Timeline", icon: Clock },
            { href: "/dashboard/council", label: "Council", icon: MessageSquare },
            { href: "/dashboard/proposals", label: "Proposals", icon: FileCheck },
        ],
    },
    {
        title: "Analytics",
        items: [
            { href: "/dashboard/knowledge", label: "Knowledge Graph", icon: Network },
            { href: "/dashboard/cost", label: "Cost", icon: DollarSign },
            { href: "/dashboard/adrs", label: "ADRs", icon: FileText },
        ],
    },
    {
        title: "System",
        items: [
            { href: "/dashboard/memory", label: "Memory", icon: Brain },
            { href: "/dashboard/skills", label: "Skills", icon: Puzzle },
            { href: "/admin", label: "Admin", icon: ShieldAlert },
            { href: "/dashboard/settings", label: "Settings", icon: Settings },
        ],
    },
];

function NavSection({
    section,
    pathname,
    defaultOpen = true,
}: {
    section: NavSection;
    pathname: string;
    defaultOpen?: boolean;
}) {
    const [open, setOpen] = useState(defaultOpen);
    const hasActive = section.items.some((item) => pathname === item.href);

    return (
        <div className="mb-2">
            <button
                onClick={() => setOpen(!open)}
                className="flex items-center justify-between w-full px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600 hover:text-slate-400 transition-colors"
            >
                {section.title}
                <ChevronDown
                    size={12}
                    className={`transition-transform duration-200 ${open ? "" : "-rotate-90"}`}
                />
            </button>

            {open && (
                <div className="space-y-0.5">
                    {section.items.map((item) => {
                        const isActive = pathname === item.href;
                        const Icon = item.icon;

                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={`
                                    flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-200 group mx-1
                                    ${
                                        isActive
                                            ? "bg-blue-500/10 text-blue-400 border border-blue-500/20 shadow-[0_0_15px_-3px_rgba(59,130,246,0.2)]"
                                            : "text-slate-400 hover:bg-white/5 hover:text-white border border-transparent"
                                    }
                                `}
                            >
                                <Icon
                                    size={16}
                                    className={
                                        isActive
                                            ? "text-blue-400"
                                            : "text-slate-500 group-hover:text-white"
                                    }
                                />
                                <span className="font-medium text-sm">{item.label}</span>

                                {item.badge !== undefined && item.badge > 0 && (
                                    <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-400 font-medium">
                                        {item.badge}
                                    </span>
                                )}

                                {isActive && (
                                    <div className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.8)]" />
                                )}
                            </Link>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

export function Sidebar() {
    const pathname = usePathname();
    const { user, signOut } = useAuth();

    return (
        <aside className="w-64 h-screen flex flex-col border-r border-white/10 bg-black/50 backdrop-blur-xl fixed left-0 top-0 z-50">
            {/* Logo */}
            <div className="p-6 border-b border-white/10">
                <h1 className="text-xl font-bold gradient-text">Aegion</h1>
                <p className="text-xs text-slate-500 mt-1">Control Plane</p>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-3 overflow-y-auto">
                {sections.map((section) => (
                    <NavSection
                        key={section.title}
                        section={section}
                        pathname={pathname}
                    />
                ))}
            </nav>

            {/* User Footer */}
            <div className="p-4 border-t border-white/10">
                <div className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/5 mb-2">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 to-purple-500 flex items-center justify-center text-xs font-bold text-white uppercase">
                        {user?.email?.[0] || <User size={14} />}
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white truncate">
                            {user?.displayName || "User"}
                        </p>
                        <p className="text-xs text-slate-500 truncate">{user?.email}</p>
                    </div>
                </div>

                <button
                    onClick={signOut}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 text-xs font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-lg transition-colors"
                >
                    <LogOut size={14} />
                    Sign Out
                </button>
            </div>
        </aside>
    );
}
