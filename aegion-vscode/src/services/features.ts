
import * as vscode from 'vscode';
import axios from 'axios';

interface _FeatureFlag {
    name: string;
    enabled: boolean;
    tier: 'stable' | 'beta' | 'experimental' | 'deprecated';
}

export class FeatureFlagService {
    private static instance: FeatureFlagService;
    private flags: Map<string, boolean> = new Map();
    private readonly configKey = 'aegion.features';

    private constructor(private context: vscode.ExtensionContext) {
        this.refresh();
    }

    static getInstance(context: vscode.ExtensionContext): FeatureFlagService {
        if (!FeatureFlagService.instance) {
            FeatureFlagService.instance = new FeatureFlagService(context);
        }
        return FeatureFlagService.instance;
    }

    /**
     * Fetch flags from backend and update VS Code context keys.
     */
    public async refresh() {
        // 1. Load from User Config (overrides)
        const config = vscode.workspace.getConfiguration('aegion');
        const localOverrides = config.get<Record<string, boolean>>('features') || {};

        // 2. Fetch from Backend (if possible)
        let backendFlags: Record<string, boolean> = {};
        try {
            const backendUrl = config.get<string>('backendUrl') || 'http://localhost:8000';
            // Remove trailing slash if present to avoid double slash issues
            const baseUrl = backendUrl.replace(/\/$/, '');
            const response = await axios.get(`${baseUrl}/api/v1/system/features/`);
            if (response.status === 200) {
                backendFlags = response.data as Record<string, boolean>;
            }
        } catch (e) {
            console.warn('Failed to fetch feature flags from backend:', e);
        }

        // 3. Merge Strategies: Config > Backend > Default
        // For now we trust backend as source of truth for availability, but allow local override
        const merged: Record<string, boolean> = { ...backendFlags, ...localOverrides };

        // 4. Set Context Keys
        for (const [key, value] of Object.entries(merged)) {
            await vscode.commands.executeCommand('setContext', `aegion.feature.${key}`, value);
            this.flags.set(key, value);
        }

        // Set a specialized context for "Advanced Mode" if any experimental features are on
        const isAdvanced = Array.from(this.flags.values()).some(v => v === true); // Simplified logic
        await vscode.commands.executeCommand('setContext', 'aegion.mode.advanced', isAdvanced);
    }

    public isEnabled(feature: string): boolean {
        return this.flags.get(feature) ?? false;
    }
}
