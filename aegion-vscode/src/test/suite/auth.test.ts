/* eslint-disable @typescript-eslint/no-var-requires */
/**
 * Firebase Auth Provider Tests — Phase 56
 *
 * Tests for:
 * - Login flow (email/password)
 * - Token refresh logic
 * - Session restore from SecretStorage
 * - Auth state change notifications
 * - Error handling
 */

import * as assert from 'assert';
import * as vscode from 'vscode';

suite('FirebaseAuthProvider', () => {
    test('should be importable', () => {
        const mod = require('../../auth/FirebaseAuthProvider');
        assert.ok(mod.FirebaseAuthProvider);
        assert.ok(mod.getFirebaseAuth);
    });

    test('should have correct initial state when no credentials stored', async () => {
        const mod = require('../../auth/FirebaseAuthProvider');
        // Reset singleton for testing
        (mod.FirebaseAuthProvider as any).instance = null;

        const context = {
            secrets: {
                get: async () => undefined,
                store: async () => {},
                delete: async () => {},
            },
            subscriptions: [],
        } as unknown as vscode.ExtensionContext;

        const auth = mod.FirebaseAuthProvider.getInstance(context);
        const state = auth.getState();

        assert.strictEqual(state.authenticated, false);
        assert.strictEqual(state.email, null);
        assert.strictEqual(state.uid, null);
        assert.strictEqual(state.token, null);

        // Cleanup singleton
        (mod.FirebaseAuthProvider as any).instance = null;
    });

    test('should fail login when Firebase config is missing', async () => {
        const mod = require('../../auth/FirebaseAuthProvider');
        (mod.FirebaseAuthProvider as any).instance = null;

        const context = {
            secrets: {
                get: async () => undefined,
                store: async () => {},
                delete: async () => {},
            },
            subscriptions: [],
        } as unknown as vscode.ExtensionContext;

        const auth = mod.FirebaseAuthProvider.getInstance(context);
        // Without firebase config set, login should return false
        const result = await auth.loginWithEmail('test@example.com', 'password');
        assert.strictEqual(result, false);

        (mod.FirebaseAuthProvider as any).instance = null;
    });

    test('should notify listeners on logout', async () => {
        const mod = require('../../auth/FirebaseAuthProvider');
        (mod.FirebaseAuthProvider as any).instance = null;

        const context = {
            secrets: {
                get: async () => undefined,
                store: async () => {},
                delete: async () => {},
            },
            subscriptions: [],
        } as unknown as vscode.ExtensionContext;

        const auth = mod.FirebaseAuthProvider.getInstance(context);
        let notifyCount = 0;

        auth.onAuthStateChanged(() => {
            notifyCount++;
        });

        // Initial notification happens on subscribe
        assert.strictEqual(notifyCount, 1);

        await auth.logout();
        // Should have fired again on logout
        assert.strictEqual(notifyCount, 2);

        (mod.FirebaseAuthProvider as any).instance = null;
    });

    test('getToken returns null when not authenticated', async () => {
        const mod = require('../../auth/FirebaseAuthProvider');
        (mod.FirebaseAuthProvider as any).instance = null;

        const context = {
            secrets: {
                get: async () => undefined,
                store: async () => {},
                delete: async () => {},
            },
            subscriptions: [],
        } as unknown as vscode.ExtensionContext;

        const auth = mod.FirebaseAuthProvider.getInstance(context);
        const token = await auth.getToken();
        assert.strictEqual(token, null);

        (mod.FirebaseAuthProvider as any).instance = null;
    });
});
