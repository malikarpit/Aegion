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
        <div className="min-h-screen flex items-center justify-center bg-black relative overflow-hidden">
            {/* Background */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-[-20%] right-[-10%] w-[50%] h-[50%] bg-purple-900/15 rounded-full blur-[150px] animate-pulse" />
                <div className="absolute bottom-[-20%] left-[-10%] w-[40%] h-[40%] bg-blue-900/15 rounded-full blur-[150px] animate-pulse" />
            </div>

            <div className="relative z-10 w-full max-w-md px-6">
                <div className="glass-card-static p-8 shadow-2xl animate-slide-up">
                    {/* Header */}
                    <div className="text-center mb-8">
                        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-500 to-blue-600 mb-4 shadow-lg shadow-purple-500/20">
                            <ShieldCheck className="w-7 h-7 text-white" />
                        </div>
                        <h1 className="text-2xl font-bold text-white">
                            Create Account
                        </h1>
                        <p className="text-slate-500 text-sm mt-2">
                            Join the Aegion Control Plane
                        </p>
                    </div>

                    {/* Error */}
                    {displayError && (
                        <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 mb-6 animate-slide-down">
                            <AlertCircle size={16} className="text-red-400 shrink-0" />
                            <p className="text-sm text-red-400">{displayError}</p>
                        </div>
                    )}

                    <form onSubmit={handleSignup} className="space-y-4">
                        <div>
                            <label className="text-xs text-slate-400 mb-1.5 block">
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
                            <label className="text-xs text-slate-400 mb-1.5 block">
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
                            <label className="text-xs text-slate-400 mb-1.5 block">
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
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors"
                                >
                                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                                </button>
                            </div>
                        </div>

                        <div>
                            <label className="text-xs text-slate-400 mb-1.5 block">
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
                            className="w-full py-3 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-medium transition-all duration-200 active:scale-[0.98] disabled:opacity-50 mt-2"
                        >
                            {submitting ? "Creating account..." : "Create Account"}
                        </button>

                        <div className="text-center text-xs text-slate-500 mt-4">
                            Already have an account?{" "}
                            <Link
                                href="/login"
                                className="text-blue-400 hover:text-blue-300 transition-colors"
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
