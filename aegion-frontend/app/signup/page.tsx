"use client";

import { useAuth } from "@/lib/auth";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ShieldCheck, Eye, EyeOff, AlertCircle } from "lucide-react";

export default function SignupPage() {
    const { user, signUpWithEmail, loading, error } = useAuth();
    const router = useRouter();
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [localError, setLocalError] = useState<string | null>(null);

    useEffect(() => {
        if (user && !loading) router.push("/");
    }, [user, loading, router]);

    const handleSignup = async (e: React.FormEvent) => {
        e.preventDefault();
        setLocalError(null);

        if (password !== confirmPassword) {
            setLocalError("Passwords do not match");
            return;
        }
        if (password.length < 6) {
            setLocalError("Password must be at least 6 characters");
            return;
        }

        setSubmitting(true);
        await signUpWithEmail(email, password, name);
        setSubmitting(false);
    };

    if (loading) return null;

    const displayError = localError || error;

    return (
        <div className="min-h-screen flex items-center justify-center relative overflow-hidden" style={{ background: "var(--surface-0)" }}>
            {/* Background */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div
                    className="absolute top-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full blur-[150px] animate-pulse"
                    style={{ background: "hsla(280, 85%, 40%, 0.12)" }}
                />
                <div
                    className="absolute bottom-[-20%] left-[-10%] w-[40%] h-[40%] rounded-full blur-[150px] animate-pulse"
                    style={{ background: "hsla(260, 100%, 40%, 0.10)" }}
                />
            </div>

            <div className="relative z-10 w-full max-w-md px-6">
                <div className="glass-l2 p-8 shadow-2xl animate-slide-up" style={{ borderRadius: "var(--radius-xl)" }}>
                    {/* Header */}
                    <div className="text-center mb-8">
                        <div
                            className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-4"
                            style={{
                                background: "var(--gradient-primary)",
                                boxShadow: "0 8px 24px hsla(260, 100%, 50%, 0.2)",
                            }}
                        >
                            <ShieldCheck className="w-7 h-7" style={{ color: "white" }} />
                        </div>
                        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
                            Create Account
                        </h1>
                        <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>
                            Join the Aegion Control Plane
                        </p>
                    </div>

                    {/* Error */}
                    {displayError && (
                        <div
                            className="flex items-center gap-2 px-4 py-3 rounded-xl mb-6 animate-slide-down"
                            style={{
                                background: "hsla(350, 90%, 62%, 0.08)",
                                border: "1px solid hsla(350, 90%, 62%, 0.20)",
                            }}
                        >
                            <AlertCircle size={16} className="shrink-0" style={{ color: "var(--accent-risk)" }} />
                            <p className="text-sm" style={{ color: "var(--accent-risk)" }}>{displayError}</p>
                        </div>
                    )}

                    <form onSubmit={handleSignup} className="space-y-4">
                        <div>
                            <label className="text-xs mb-1.5 block" style={{ color: "var(--text-muted)" }}>
                                Display Name
                            </label>
                            <input
                                type="text"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="Your Name"
                                required
                                className="glass-input w-full px-4 py-3 text-sm"
                            />
                        </div>

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
                                    placeholder="Minimum 6 characters"
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

                        <div>
                            <label className="text-xs mb-1.5 block" style={{ color: "var(--text-muted)" }}>
                                Confirm Password
                            </label>
                            <input
                                type="password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                placeholder="••••••••"
                                required
                                className="glass-input w-full px-4 py-3 text-sm"
                            />
                        </div>

                        <button
                            type="submit"
                            disabled={submitting}
                            className="w-full py-3 rounded-xl font-medium transition-all duration-200 active:scale-[0.98] disabled:opacity-50 mt-2"
                            style={{
                                background: "var(--gradient-primary)",
                                color: "white",
                                boxShadow: "0 4px 20px hsla(260, 100%, 50%, 0.2)",
                            }}
                        >
                            {submitting ? "Creating account..." : "Create Account"}
                        </button>

                        <div className="text-center text-xs mt-4" style={{ color: "var(--text-muted)" }}>
                            Already have an account?{" "}
                            <Link
                                href="/login"
                                className="transition-colors"
                                style={{ color: "var(--accent-reason)" }}
                            >
                                Sign in
                            </Link>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
