"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import {
    User,
    onAuthStateChanged,
    signInWithPopup,
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    sendPasswordResetEmail,
    updateProfile,
    GoogleAuthProvider,
    signOut as firebaseSignOut,
} from "firebase/auth";
import { auth } from "./firebase";
import { useRouter } from "next/navigation";

interface AuthContextType {
    user: User | null;
    loading: boolean;
    signInWithGoogle: () => Promise<void>;
    signInWithEmail: (email: string, password: string) => Promise<void>;
    signUpWithEmail: (email: string, password: string, displayName: string) => Promise<void>;
    resetPassword: (email: string) => Promise<void>;
    signOut: () => Promise<void>;
    getToken: () => Promise<string | null>;
    error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const router = useRouter();

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
            setUser(currentUser);
            setLoading(false);
        });
        return () => unsubscribe();
    }, []);

    const clearError = () => setError(null);

    const signInWithGoogle = async () => {
        clearError();
        const provider = new GoogleAuthProvider();
        try {
            await signInWithPopup(auth, provider);
            router.push("/");
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Failed to sign in";
            setError(message);
        }
    };

    const signInWithEmail = async (email: string, password: string) => {
        clearError();
        try {
            await signInWithEmailAndPassword(auth, email, password);
            router.push("/");
        } catch (err: unknown) {
            const code = (err as { code?: string })?.code;
            switch (code) {
                case "auth/invalid-credential":
                    setError("Invalid email or password");
                    break;
                case "auth/user-not-found":
                    setError("No account found with this email");
                    break;
                case "auth/too-many-requests":
                    setError("Too many attempts. Please try again later");
                    break;
                default:
                    setError("Failed to sign in. Please try again");
            }
        }
    };

    const signUpWithEmail = async (
        email: string,
        password: string,
        displayName: string
    ) => {
        clearError();
        try {
            const result = await createUserWithEmailAndPassword(auth, email, password);
            await updateProfile(result.user, { displayName });
            router.push("/");
        } catch (err: unknown) {
            const code = (err as { code?: string })?.code;
            switch (code) {
                case "auth/email-already-in-use":
                    setError("An account with this email already exists");
                    break;
                case "auth/weak-password":
                    setError("Password should be at least 6 characters");
                    break;
                default:
                    setError("Failed to create account. Please try again");
            }
        }
    };

    const resetPassword = async (email: string) => {
        clearError();
        try {
            await sendPasswordResetEmail(auth, email);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Failed to send reset email";
            setError(message);
        }
    };

    const signOut = async () => {
        try {
            await firebaseSignOut(auth);
            router.push("/login");
        } catch (err) {
            console.error("Error signing out", err);
        }
    };

    const getToken = async () => {
        if (!user) return null;
        return await user.getIdToken();
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                loading,
                signInWithGoogle,
                signInWithEmail,
                signUpWithEmail,
                resetPassword,
                signOut,
                getToken,
                error,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
};
