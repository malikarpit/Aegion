
import * as vscode from 'vscode';
import { SessionState } from '../session/manager';

export class GovernanceStatusBar {
    private statusBarItem: vscode.StatusBarItem;

    constructor(context: vscode.ExtensionContext) {
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Left,
            100,
        );
        this.statusBarItem.command = 'aegion.showSessionMenu';
        context.subscriptions.push(this.statusBarItem);
        this.update({
            sessionId: null,
            status: 'inactive',
            workspaceId: 'default',
            startedAt: null,
            decisionCount: 0,
            evidenceCount: 0,
            explorationStage: 'exploration',
        }); // Initial state
        this.statusBarItem.show();
    }

    public update(state: SessionState): void {
        if (state.status === 'active') {
            const stageIcon = this.getStageIcon(state.explorationStage);
            // $(shield) Aegion: Active (Green)
            this.statusBarItem.text = `$(shield) Aegion: Active ${stageIcon} [${state.decisionCount}]`;
            this.statusBarItem.tooltip = `Session: ${state.sessionId}\nDecisions: ${state.decisionCount}\nEvidence: ${state.evidenceCount}\nStage: ${state.explorationStage}`;
            this.statusBarItem.backgroundColor = undefined; // Default/Greenish in some themes, or explicit color if needed? Standard is usually fine for active.
            // Requirement said "Active (Green)". In VS Code API, we can't easily force "Green" without ThemeColor 'statusBarItem.warningBackground' (Yellow) or 'statusBarItem.errorBackground' (Red).
            // Normal is "Blue" or "Purple" depending on theme.
            // We'll stick to default for Active (often blue/purple) unless we want to use specific theme colors.
            // Wait, the requirement says "Active (Green)". There is no "successBackground".
            // We can just use default.
        } else if (state.status === 'closing') {
            this.statusBarItem.text = '$(sync~spin) Aegion: Closing...';
            this.statusBarItem.tooltip = 'Session is being distilled';
            this.statusBarItem.backgroundColor = undefined;
        } else {
            // Idle: $(warning) Aegion: Idle (Yellow)
            this.statusBarItem.text = '$(warning) Aegion: Idle';
            this.statusBarItem.tooltip = 'Click to start a session';
            this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        }
    }

    private getStageIcon(stage: string): string {
        switch (stage) {
            case 'exploration': return '🧠';
            case 'proposed': return '🏗️';
            case 'governed': return '🏛️';
            default: return '';
        }
    }

    public dispose(): void {
        this.statusBarItem.dispose();
    }
}
