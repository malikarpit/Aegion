"use client";

import { useAuth } from "@/lib/auth";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ShieldCheck, Mail, Eye, EyeOff, AlertCircle } from "lucide-react";

export default function LoginPage() {
    const { user, signInWithGoogle, signInWithEmail, loading, error } = useAuth();
    const router = useRouter();
    const [mode, setMode] = useState<"select" | "email">("select");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    useEffect(() => {
        if (user && !loading) {
            router.push("/");
        }
    }, [user, loading, router]);

    const handleEmailLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);
        await signInWithEmail(email, password);
        setSubmitting(false);
    };

    if (loading) return null;

    return (
        <div className="min-h-screen flex items-center justify-center relative overflow-hidden" style={{ background: "var(--surface-0)" }}>
            {/* Background Ambience */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-[-20%] left-[-15%] w-[50%] h-[50%] rounded-full blur-[150px] animate-pulse" style={{ background: "hsla(260, 100%, 40%, 0.10)" }} />
                <div className="absolute bottom-[-20%] right-[-15%] w-[50%] h-[50%] rounded-full blur-[150px] animate-pulse" style={{ background: "hsla(280, 85%, 40%, 0.10)" }} />
                <div className="absolute top-[40%] left-[50%] w-[30%] h-[30%] rounded-full blur-[120px]" style={{ background: "hsla(165, 85%, 40%, 0.06)" }} />
            </div>

            <div className="relative z-10 w-full max-w-md px-6">
                <div className="glass-l2 p-8 shadow-2xl animate-slide-up" style={{ borderRadius: "var(--radius-xl)" }}>
                    {/* Header */}
                    <div className="text-center mb-8">
                        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-4" style={{ background: "var(--gradient-primary)", boxShadow: "0 8px 24px hsla(260, 100%, 50%, 0.2)" }}>
                            <ShieldCheck className="w-7 h-7" style={{ color: "white" }} />
                        </div>
                        <h1 className="text-3xl font-bold tracking-tight gradient-text">
                            Aegion
                        </h1>
                        <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>
                            AI Governance Control Plane
                        </p>
                    </div>

                    {/* Error */}
                    {error && (
                        <div className="flex items-center gap-2 px-4 py-3 rounded-xl mb-6 animate-slide-down" style={{ background: "hsla(350, 90%, 62%, 0.08)", border: "1px solid hsla(350, 90%, 62%, 0.20)" }}>
                            <AlertCircle size={16} className="shrink-0" style={{ color: "var(--accent-risk)" }} />
                            <p className="text-sm" style={{ color: "var(--status-error)" }}>{error}</p>
                        </div>
                    )}

                    {mode === "select" ? (
                        <div className="space-y-3">
                            {/* Google */}
                            <button
                                onClick={signInWithGoogle}
                                className="w-full group relative flex items-center justify-center gap-3 px-6 py-3.5 rounded-xl transition-all duration-300 active:scale-[0.98]"
                                style={{ background: "hsla(260, 20%, 80%, 0.05)", border: "1px solid var(--border-subtle)" }}
                            >
                                <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
                                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                                </svg>
                                <span className="font-medium" style={{ color: "var(--text-primary)" }}>
                                    Continue with Google
                                </span>
                            </button>

                            {/* Divider */}
                            <div className="flex items-center gap-4 py-2">
                                <div className="flex-1 h-px" style={{ background: "var(--border-default)" }} />
                                <span className="text-xs" style={{ color: "var(--text-ghost)" }}>or</span>
                                <div className="flex-1 h-px" style={{ background: "var(--border-default)" }} />
                            </div>

                            {/* Email */}
                            <button
                                onClick={() => setMode("email")}
                                className="w-full group flex items-center justify-center gap-3 px-6 py-3.5 rounded-xl transition-all duration-300 active:scale-[0.98]"
                                style={{ background: "hsla(260, 20%, 80%, 0.05)", border: "1px solid var(--border-subtle)" }}
                            >
                                <Mail size={18} style={{ color: "var(--text-muted)" }} />
                                <span className="font-medium" style={{ color: "var(--text-primary)" }}>
                                    Sign in with Email
                                </span>
                            </button>
                        </div>
                    ) : (
                        <form onSubmit={handleEmailLogin} className="space-y-4">
                            <div>
                                <label className="text-xs mb-1.5 block" style={{ color: "var(--text-muted)" }}>
                                    Email
                                </label>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="you@example.com"
                                    required
                                    className="glass-input w-full px-4 py-3 text-sm"
                                />
                            </div>
                            <div>
                                <label className="text-xs mb-1.5 block" style={{ color: "var(--text-muted)" }}>
                                    Password
                                </label>
                                <div className="relative">
                                    <input
                                        type={showPassword ? "text" : "password"}
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        placeholder="••••••••"
                                        required
                                        className="glass-input w-full px-4 py-3 pr-12 text-sm"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors"
                                        style={{ color: "var(--text-muted)" }}
                                    >
                                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>
                                </div>
                            </div>

                            <button
                                type="submit"
                                disabled={submitting}
                                className="w-full py-3 rounded-xl font-medium transition-all duration-200 active:scale-[0.98] disabled:opacity-50"
                                style={{ background: "var(--gradient-primary)", color: "white", boxShadow: "0 4px 20px hsla(260, 100%, 50%, 0.2)" }}
                            >
                                {submitting ? "Signing in..." : "Sign In"}
                            </button>

                            <div className="flex items-center justify-between text-xs">
                                <button
                                    type="button"
                                    onClick={() => setMode("select")}
                                    className="transition-colors"
                                    style={{ color: "var(--text-muted)" }}
                                >
                                    ← Back
                                </button>
                                <Link
                                    href="/signup"
                                    className="transition-colors"
                                    style={{ color: "var(--accent-reason)" }}
                                >
                                    Create account →
                                </Link>
                            </div>
                        </form>
                    )}

                    {/* Footer */}
                    <div className="mt-8 pt-6 text-center" style={{ borderTop: "1px solid var(--border-subtle)" }}>
                        <p className="text-[10px] tracking-wider uppercase" style={{ color: "var(--text-ghost)", fontFamily: "var(--font-mono)" }}>
                            System Access: Restricted
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
