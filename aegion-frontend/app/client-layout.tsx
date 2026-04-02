"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { ToastProvider } from "@/components/ui/Toast";

export function ClientLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const isLoginPage = pathname === "/login" || pathname === "/signup";

    return (
        <ToastProvider>
            <div className="flex h-screen overflow-hidden">
                {!isLoginPage && <Sidebar />}
                <main
                    className={`flex-1 overflow-auto relative ${!isLoginPage ? "pl-64" : ""}`}
                >
                    {children}
                </main>
            </div>
        </ToastProvider>
    );
}
