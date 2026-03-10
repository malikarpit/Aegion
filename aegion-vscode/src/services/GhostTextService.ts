/**
 * Ghost Text Service — Phase 54 Enhanced
 *
 * Enhancements:
 * 1. Multi-line completions: 40 prefix + 20 suffix lines (up from 20)
 * 2. FIM (Fill-in-Middle) support for models that support it
 * 3. Language-aware prompting: Different system prompts per language
 * 4. Confidence display in status bar
 * 5. Accept/Reject telemetry tracking
 */

import * as vscode from 'vscode';
import { Logger } from './Logger';
import { getApiClient } from '../api/client';
import { SessionManager } from '../session/manager';

// Phase 54: Language-specific system prompts
const LANGUAGE_PROMPTS: Record<string, string> = {
    python: 'You are a Python expert. Follow PEP 8, use type hints, prefer pathlib over os.path.',
    typescript: 'You are a TypeScript expert. Use strict types, avoid any, prefer interfaces over types.',
    javascript: 'You are a JavaScript expert. Use modern ES2022+, prefer const, avoid var.',
    rust: 'You are a Rust expert. Follow ownership conventions, prefer Result over panic.',
    go: 'You are a Go expert. Follow standard Go conventions, handle all errors.',
    java: 'You are a Java expert. Follow SOLID principles, use proper design patterns.',
    default: 'You are a code completion AI. Generate clean, idiomatic code.',
};

// Phase 54: FIM-capable model identifiers
const FIM_MODELS = new Set([
    'codestral', 'deepseek-coder', 'codegemma', 'starcoder2',
    'codellama', 'qwen2.5-coder',
]);

export class GhostTextService implements vscode.InlineCompletionItemProvider {
    private debounceTimer: NodeJS.Timeout | null = null;
    private readonly DEBOUNCE_MS = 600;
    private readonly PREFIX_LINES = 40;   // Phase 54: Increased from 20
    private readonly SUFFIX_LINES = 20;   // Phase 54: Added suffix context
    private statusBarItem: vscode.StatusBarItem;
    private acceptCount = 0;
    private rejectCount = 0;

    constructor(private sessionManager: SessionManager) {
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            90,
        );
        this.statusBarItem.name = 'Aegion Ghost Text';
    }

    async provideInlineCompletionItems(
        document: vscode.TextDocument,
        position: vscode.Position,
        context: vscode.InlineCompletionContext,
        token: vscode.CancellationToken,
    ): Promise<vscode.InlineCompletionItem[] | null> {

        // 1. Check Session State
        const state = this.sessionManager.getState();
        if (state.status !== 'active') {
            return null;
        }

        // 2. Debounce
        await new Promise(resolve => {
            if (this.debounceTimer) { clearTimeout(this.debounceTimer); }
            this.debounceTimer = setTimeout(resolve, this.DEBOUNCE_MS);
        });

        if (token.isCancellationRequested) { return null; }

        try {
            const api = getApiClient();

            // Phase 54: Extract prefix and suffix with expanded window
            const prefixStart = Math.max(0, position.line - this.PREFIX_LINES);
            const suffixEnd = Math.min(document.lineCount - 1, position.line + this.SUFFIX_LINES);

            const prefixRange = new vscode.Range(prefixStart, 0, position.line, position.character);
            const suffixRange = new vscode.Range(position.line, position.character, suffixEnd, document.lineAt(suffixEnd).text.length);

            const prefix = document.getText(prefixRange);
            const suffix = document.getText(suffixRange);

            // Phase 54: Language-aware prompting
            const languageId = document.languageId;
            const languagePrompt = LANGUAGE_PROMPTS[languageId] || LANGUAGE_PROMPTS.default;

            // Phase 54: FIM format detection
            const fimEnabled = this.isFimSupported();

            // 3. Call Backend
            const suggestion = await api.completeGhostText({
                file_path: document.uri.fsPath,
                file_content: document.getText(),
                cursor_position: {
                    line: position.line,
                    character: position.character,
                },
                language_id: languageId,
                workspace_id: state.workspaceId || 'default',
                // Phase 54: Enhanced context
                prefix,
                suffix,
                language_prompt: languagePrompt,
                fim_enabled: fimEnabled,
            } as any);

            if (!suggestion || !suggestion.text) { return null; }

            // Phase 54: Confidence display in status bar
            this.updateConfidenceDisplay(suggestion.confidence, languageId);

            // 4. Create Completion Item
            const item = new vscode.InlineCompletionItem(
                suggestion.text,
                new vscode.Range(position, position),
            );

            // Phase 54: Track accept/reject via command
            item.command = {
                command: 'aegion.ghostText.accepted',
                title: 'Ghost Text Accepted',
                arguments: [suggestion.confidence, languageId],
            };

            Logger.info(`GhostText: confidence=${suggestion.confidence} lang=${languageId} fim=${fimEnabled}`);
            return [item];

        } catch (error) {
            Logger.error('GhostText failed', error);
            this.statusBarItem.hide();
            return null;
        }
    }

    // Phase 54: FIM model detection
    private isFimSupported(): boolean {
        const config = vscode.workspace.getConfiguration('aegion');
        const completionModel = config.get<string>('completionModel') || '';
        return FIM_MODELS.has(completionModel.toLowerCase());
    }

    // Phase 54: Status bar confidence
    private updateConfidenceDisplay(confidence: number | string, language: string): void {
        const confNum = typeof confidence === 'number' ? confidence : parseFloat(confidence) || 0.5;
        const confPercent = Math.round(confNum * 100);

        let icon: string;
        if (confPercent >= 80) {
            icon = '$(pass-filled)';
        } else if (confPercent >= 50) {
            icon = '$(info)';
        } else {
            icon = '$(warning)';
        }

        this.statusBarItem.text = `${icon} Ghost: ${confPercent}%`;
        this.statusBarItem.tooltip = `Aegion Ghost Text\nConfidence: ${confPercent}%\nLanguage: ${language}\nAccepted: ${this.acceptCount}\nDismissed: ${this.rejectCount}`;
        this.statusBarItem.show();

        // Auto-hide after 5 seconds
        setTimeout(() => this.statusBarItem.hide(), 5000);
    }

    // Phase 54: Telemetry
    trackAccepted(confidence: number | string, language: string): void {
        this.acceptCount++;
        try {
            // eslint-disable-next-line @typescript-eslint/no-var-requires
            const { TelemetryService } = require('./TelemetryService');
            TelemetryService.getInstance().sendEvent('GhostTextAccepted', {
                confidence: String(confidence),
                language,
                totalAccepted: this.acceptCount,
            });
        } catch {
            // Telemetry is best-effort
        }
    }

    trackRejected(language: string): void {
        this.rejectCount++;
        try {
            // eslint-disable-next-line @typescript-eslint/no-var-requires
            const { TelemetryService } = require('./TelemetryService');
            TelemetryService.getInstance().sendEvent('GhostTextRejected', {
                language,
                totalRejected: this.rejectCount,
            });
        } catch {
            // Telemetry is best-effort
        }
    }

    dispose(): void {
        this.statusBarItem.dispose();
    }
}

export function registerGhostText(context: vscode.ExtensionContext, sessionManager: SessionManager) {
    const provider = new GhostTextService(sessionManager);
    const selector: vscode.DocumentSelector = { scheme: 'file', language: '*' };

    context.subscriptions.push(
        vscode.languages.registerInlineCompletionItemProvider(selector, provider),
        // Phase 54: Track acceptance
        vscode.commands.registerCommand('aegion.ghostText.accepted', (confidence: number, language: string) => {
            provider.trackAccepted(confidence, language);
        }),
    );
}
