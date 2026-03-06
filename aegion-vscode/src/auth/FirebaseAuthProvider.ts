/**
 * Aegion Firebase Auth Provider — Phase 52
 *
 * Manages Firebase Authentication for the VS Code extension.
 * - Email/password sign-in
 * - Google OAuth via browser
 * - Auto-refresh tokens (Firebase tokens expire after 1 hour)
 * - SecretStorage for secure token persistence
 * - Auth state change events for status bar + API client
 *
 * Firebase config is read from VS Code user settings (not hardcoded).
 */

import * as vscode from 'vscode';
import { Logger } from '../services/Logger';

export interface AuthState {
    authenticated: boolean;
    email: string | null;
    uid: string | null;
    displayName: string | null;
    token: string | null;
    expiresAt: number;
}

export type AuthStateListener = (state: AuthState) => void;

export class FirebaseAuthProvider {
    private static instance: FirebaseAuthProvider | null = null;
    private currentState: AuthState;
    private listeners: AuthStateListener[] = [];
    private refreshTimer: NodeJS.Timeout | null = null;
    private context: vscode.ExtensionContext;

    private constructor(context: vscode.ExtensionContext) {
        this.context = context;
        this.currentState = {
            authenticated: false,
            email: null,
            uid: null,
            displayName: null,
            token: null,
            expiresAt: 0,
        };
    }

    static getInstance(context?: vscode.ExtensionContext): FirebaseAuthProvider {
        if (!FirebaseAuthProvider.instance) {
            if (!context) {
                throw new Error('FirebaseAuthProvider must be initialized with context first');
            }
            FirebaseAuthProvider.instance = new FirebaseAuthProvider(context);
        }
        return FirebaseAuthProvider.instance;
    }

    /**
     * Get Firebase config from VS Code user settings.
     */
    private getFirebaseConfig(): Record<string, string> | null {
        const config = vscode.workspace.getConfiguration('aegion');
        const apiKey = config.get<string>('firebase.apiKey');
        const authDomain = config.get<string>('firebase.authDomain');
        const projectId = config.get<string>('firebase.projectId');

        if (!apiKey || !authDomain || !projectId) {
            return null;
        }

        return {
            apiKey,
            authDomain,
            projectId,
            storageBucket: config.get<string>('firebase.storageBucket') || '',
            messagingSenderId: config.get<string>('firebase.messagingSenderId') || '',
            appId: config.get<string>('firebase.appId') || '',
        };
    }

    /**
     * Sign in with email and password.
     */
    async loginWithEmail(email: string, password: string): Promise<boolean> {
        const firebaseConfig = this.getFirebaseConfig();
        if (!firebaseConfig) {
            vscode.window.showErrorMessage(
                'Aegion: Firebase not configured. Go to Settings → Aegion → Firebase to set API Key, Auth Domain, and Project ID.',
            );
            return false;
        }

        try {
            // Use Firebase REST API for sign-in (avoids bundling firebase SDK in extension)
            const response = await fetch(
                `https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${firebaseConfig.apiKey}`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        email,
                        password,
                        returnSecureToken: true,
                    }),
                },
            );

            if (!response.ok) {
                const error = await response.json() as { error?: { message?: string } };
                const message = error?.error?.message || 'Unknown error';
                throw new Error(message);
            }

            const data = await response.json() as Record<string, unknown>;
            await this.handleAuthSuccess(data);
            vscode.window.showInformationMessage(`🟢 Aegion: Signed in as ${email}`);
            return true;
        } catch (error) {
            Logger.error('Firebase login failed', error);
            vscode.window.showErrorMessage(`Aegion login failed: ${error}`);
            return false;
        }
    }

    /**
     * Sign in via Google OAuth (opens browser).
     */
    async loginWithGoogle(): Promise<boolean> {
        const firebaseConfig = this.getFirebaseConfig();
        if (!firebaseConfig) {
            vscode.window.showErrorMessage(
                'Aegion: Firebase not configured. Set firebase settings first.',
            );
            return false;
        }

        try {
            // Open browser for OAuth flow
            const oauthUrl = `https://${firebaseConfig.authDomain}/__/auth/handler?apiKey=${firebaseConfig.apiKey}&authType=signInViaPopup&providerId=google.com`;
            await vscode.env.openExternal(vscode.Uri.parse(oauthUrl));

            // Prompt user to paste the token (VS Code can't intercept OAuth redirects directly)
            const token = await vscode.window.showInputBox({
                prompt: 'Paste the Firebase ID token from the browser after Google sign-in',
                password: true,
                placeHolder: 'Firebase ID token',
            });

            if (!token) {
                return false;
            }

            // Verify and use the token
            await this.handleTokenAuth(token, firebaseConfig.apiKey);
            vscode.window.showInformationMessage('🟢 Aegion: Signed in via Google');
            return true;
        } catch (error) {
            Logger.error('Google OAuth failed', error);
            vscode.window.showErrorMessage(`Google sign-in failed: ${error}`);
            return false;
        }
    }

    /**
     * Get current auth token. Refreshes if near expiry.
     */
    async getToken(): Promise<string | null> {
        if (!this.currentState.authenticated || !this.currentState.token) {
            // Try to restore from SecretStorage
            const stored = await this.restoreSession();
            if (!stored) {
                return null;
            }
        }

        // Check if token is near expiry (5 minutes buffer)
        const now = Date.now();
        if (this.currentState.expiresAt > 0 && now > this.currentState.expiresAt - 5 * 60 * 1000) {
            await this.refreshToken();
        }

        return this.currentState.token;
    }

    /**
     * Log out and clear stored credentials.
     */
    async logout(): Promise<void> {
        this.currentState = {
            authenticated: false,
            email: null,
            uid: null,
            displayName: null,
            token: null,
            expiresAt: 0,
        };

        // Clear stored credentials
        await this.context.secrets.delete('aegion.refreshToken');
        await this.context.secrets.delete('aegion.idToken');

        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }

        this.notifyListeners();
        vscode.window.showInformationMessage('🔴 Aegion: Signed out');
    }

    /**
     * Check if currently authenticated.
     */
    isAuthenticated(): boolean {
        return this.currentState.authenticated;
    }

    /**
     * Get current auth state.
     */
    getState(): AuthState {
        return { ...this.currentState };
    }

    /**
     * Listen for auth state changes.
     */
    onAuthStateChanged(listener: AuthStateListener): vscode.Disposable {
        this.listeners.push(listener);
        // Immediately notify with current state
        listener(this.getState());
        return new vscode.Disposable(() => {
            this.listeners = this.listeners.filter(l => l !== listener);
        });
    }

    /**
     * Try to restore session from SecretStorage on activation.
     */
    async restoreSession(): Promise<boolean> {
        try {
            const refreshToken = await this.context.secrets.get('aegion.refreshToken');
            if (!refreshToken) {
                return false;
            }

            const firebaseConfig = this.getFirebaseConfig();
            if (!firebaseConfig) {
                return false;
            }

            // Exchange refresh token for new ID token
            const response = await fetch(
                `https://securetoken.googleapis.com/v1/token?key=${firebaseConfig.apiKey}`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: `grant_type=refresh_token&refresh_token=${refreshToken}`,
                },
            );

            if (!response.ok) {
                return false;
            }

            const data = await response.json() as Record<string, unknown>;
            this.currentState = {
                authenticated: true,
                email: this.currentState.email,  // Preserve from previous session
                uid: (data.user_id as string) || null,
                displayName: null,
                token: data.id_token as string,
                expiresAt: Date.now() + parseInt((data.expires_in as string) || '3600') * 1000,
            };

            // Store new tokens
            await this.context.secrets.store('aegion.idToken', data.id_token as string);
            if (data.refresh_token) {
                await this.context.secrets.store('aegion.refreshToken', data.refresh_token as string);
            }

            this.startTokenRefresh();
            this.notifyListeners();
            Logger.info('Session restored from SecretStorage');
            return true;
        } catch (error) {
            Logger.error('Session restore failed', error);
            return false;
        }
    }

    // ══════════════════════════════════════════════
    // Internal helpers
    // ══════════════════════════════════════════════

    private async handleAuthSuccess(data: Record<string, unknown>): Promise<void> {
        this.currentState = {
            authenticated: true,
            email: (data.email as string) || null,
            uid: (data.localId as string) || null,
            displayName: (data.displayName as string) || null,
            token: (data.idToken as string) || null,
            expiresAt: Date.now() + parseInt((data.expiresIn as string) || '3600') * 1000,
        };

        // Persist refresh token securely
        if (data.refreshToken) {
            await this.context.secrets.store('aegion.refreshToken', data.refreshToken as string);
        }
        if (data.idToken) {
            await this.context.secrets.store('aegion.idToken', data.idToken as string);
        }

        this.startTokenRefresh();
        this.notifyListeners();
    }

    private async handleTokenAuth(idToken: string, apiKey: string): Promise<void> {
        // Look up user info from the token
        const response = await fetch(
            `https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=${apiKey}`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idToken }),
            },
        );

        const data = await response.json() as Record<string, unknown>;
        const users = (data.users as Array<Record<string, unknown>>) || [];

        const user = users[0] || {};

        this.currentState = {
            authenticated: true,
            email: (user.email as string) || null,
            uid: (user.localId as string) || null,
            displayName: (user.displayName as string) || null,
            token: idToken,
            expiresAt: Date.now() + 3600 * 1000,
        };

        await this.context.secrets.store('aegion.idToken', idToken);
        this.startTokenRefresh();
        this.notifyListeners();
    }

    private async refreshToken(): Promise<void> {
        try {
            const refreshToken = await this.context.secrets.get('aegion.refreshToken');
            if (!refreshToken) {
                return;
            }

            const firebaseConfig = this.getFirebaseConfig();
            if (!firebaseConfig) {
                return;
            }

            const response = await fetch(
                `https://securetoken.googleapis.com/v1/token?key=${firebaseConfig.apiKey}`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: `grant_type=refresh_token&refresh_token=${refreshToken}`,
                },
            );

            if (!response.ok) {
                Logger.error('Token refresh failed');
                return;
            }

            const data = await response.json() as Record<string, unknown>;
            this.currentState.token = data.id_token as string;
            this.currentState.expiresAt = Date.now() + parseInt((data.expires_in as string) || '3600') * 1000;

            await this.context.secrets.store('aegion.idToken', data.id_token as string);
            if (data.refresh_token) {
                await this.context.secrets.store('aegion.refreshToken', data.refresh_token as string);
            }

            Logger.info('Token refreshed successfully');
        } catch (error) {
            Logger.error('Token refresh error', error);
        }
    }

    private startTokenRefresh(): void {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        // Refresh every 50 minutes (tokens expire at 60 min)
        this.refreshTimer = setInterval(() => this.refreshToken(), 50 * 60 * 1000);
    }

    private notifyListeners(): void {
        const state = this.getState();
        for (const listener of this.listeners) {
            try {
                listener(state);
            } catch (error) {
                Logger.error('Auth state listener error', error);
            }
        }
    }

    dispose(): void {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        this.listeners = [];
    }
}

export function getFirebaseAuth(context?: vscode.ExtensionContext): FirebaseAuthProvider {
    return FirebaseAuthProvider.getInstance(context);
}
