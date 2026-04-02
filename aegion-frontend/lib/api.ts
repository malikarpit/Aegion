import axios from "axios";
import { auth } from "./firebase";

// Determine API base URL (assuming proxy or direct)
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        "Content-Type": "application/json",
    },
});

// Request interceptor to add Auth Token and Custom Key
api.interceptors.request.use(async (config) => {
    // 1. Firebase Auth Token
    const user = auth.currentUser;
    if (user) {
        const token = await user.getIdToken();
        config.headers.Authorization = `Bearer ${token}`;
    }

    // 2. Custom API Key (Client-Side Override)
    // This key is stored in localStorage by the user in the Settings page.
    // It is NEVER stored in our backend database.
    const customKey = localStorage.getItem("aegion_custom_key");
    if (customKey) {
        config.headers["X-Aegion-Custom-Key"] = customKey;
    }

    return config;
}, (error) => {
    return Promise.reject(error);
});

// Response interceptor for global error handling
api.interceptors.response.use((response) => {
    return response;
}, async (error) => {
    if (error.response && error.response.status === 401) {
        // Token is expired, revoked, or invalid.
        // Force sign-out so the user is immediately returned to the login page.
        // This handles both Firebase-expired tokens and backend-revoked tokens.
        console.warn("401 Unauthorized — token revoked or expired. Signing out.");
        try {
            await auth.signOut();
        } catch {
            // Even if Firebase sign-out fails, redirect to login
        }
        if (typeof window !== "undefined") {
            window.location.href = "/login";
        }
    }
    return Promise.reject(error);
});

export default api;
