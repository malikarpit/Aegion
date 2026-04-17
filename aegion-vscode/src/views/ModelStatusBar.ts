import * as vscode from 'vscode';
import { AegionClient } from '../api/client';
import { SessionManager } from '../session/manager';

/**
 * Phase 86: Model Settings Status Bar Item
 * Shows the current active model optimization preset (e.g., "Aegion: Balanced 🔵")
 */
export class ModelStatusBar {
    private statusBarItem: vscode.StatusBarItem;

    constructor(
        private context: vscode.ExtensionContext,
        private apiClient: AegionClient,
        private sessionManager: SessionManager,
    ) {
        this.statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 99);
        this.statusBarItem.command = 'aegion.modelSettingsView.focus'; // Clicking it opens the settings webview
        this.context.subscriptions.push(this.statusBarItem);

        // Update periodically or on session changes
        this.update();
        setInterval(() => this.update(), 60000); // Check every minute
    }

    public async update() {
        const workspaceId = this.sessionManager.getState().workspaceId;
        if (!workspaceId) {
            this.statusBarItem.hide();
            return;
        }

        try {
            const settings = await this.apiClient.get('/v1/model-settings/');
            const activePreset = settings.active_preset || 'balanced';

            const presetIcons: Record<string, string> = {
                'cost_saver': '🟢 Cost Saver',
                'balanced': '🔵 Balanced',
                'quality_first': '🟡 Quality First',
                'no_limits': '🔴 No Limits',
                'privacy_first': '🟣 Privacy First',
                'custom': '⚙️ Custom',
            };

            const label = presetIcons[activePreset] || activePreset;

            this.statusBarItem.text = `$(hubot) ${label}`;
            this.statusBarItem.tooltip = 'Aegion Model Engine Profile (Click to configure)';
            this.statusBarItem.show();
        } catch (error) {
            // Fails silently if backend isn't reachable
            this.statusBarItem.hide();
        }
    }
}
