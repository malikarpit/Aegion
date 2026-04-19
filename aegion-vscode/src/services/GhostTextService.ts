/**
 * Ghost Text Service — Phase 54 Enhanced + Production Hardening
 *
 * Enhancements:
 * 1. Multi-line completions: 40 prefix + 20 suffix lines
 * 2. FIM (Fill-in-Middle) support for models that support it
 * 3. Language-aware prompting: Different system prompts per language
 * 4. Confidence display in status bar with color-coded indicators
 * 5. Accept/Reject telemetry tracking with metrics
 * 6. Smart debounce with cancellation tokens
 * 7. Sensitive file detection (blocks .env, secrets)
 * 8. Ghost text diagnostics integration (risk/governance warnings)
 * 9. Multi-line vs single-line mode detection
 * 10. Session-aware cost tracking display
 */

import * as vscode from 'vscode';
import { Logger } from './Logger';
import { getApiClient } from '../api/client';
import { SessionManager } from '../session/manager';

// Language-specific system prompts for higher quality completions
const LANGUAGE_PROMPTS: Record<string, string> = {
    python: 'You are a Python expert. Follow PEP 8, use type hints, prefer pathlib over os.path.',
    typescript: 'You are a TypeScript expert. Use strict types, avoid any, prefer interfaces over types.',
    javascript: 'You are a JavaScript expert. Use modern ES2022+, prefer const, avoid var.',
    rust: 'You are a Rust expert. Follow ownership conventions, prefer Result over panic.',
    go: 'You are a Go expert. Follow standard Go conventions, handle all errors.',
    java: 'You are a Java expert. Follow SOLID principles, use proper design patterns.',
    csharp: 'You are a C# expert. Follow .NET conventions, use async/await properly.',
    cpp: 'You are a C++ expert. Follow modern C++20 conventions, use RAII patterns.',
    default: 'You are a code completion AI. Generate clean, idiomatic code.',
};

// FIM-capable model identifiers
const FIM_MODELS = new Set([
    'codestral', 'deepseek-coder', 'codegemma', 'starcoder2',
    'codellama', 'qwen2.5-coder',
]);

// File patterns that should NEVER receive ghost text (sensitive data)
const SENSITIVE_PATTERNS = [
    /\.env($|\.)/i,
    /secret/i,
    /credential/i,
    /password/i,
    /(private[_-])?key/i,
    /\.pem$/i,
    /token/i,
];

// Governance diagnostics collection
const diagnosticCollection = vscode.languages.createDiagnosticCollection('aegion-ghost');

export class GhostTextService implements vscode.InlineCompletionItemProvider {
    private debounceTimer: NodeJS.Timeout | null = null;
    private activeRequestId: string | null = null;
    private readonly DEBOUNCE_MS: number;
    private readonly PREFIX_LINES = 40;
    private readonly SUFFIX_LINES = 20;
    private statusBarItem: vscode.StatusBarItem;
    private costStatusBar: vscode.StatusBarItem;

    // Telemetry counters
    private acceptCount = 0;
    private rejectCount = 0;
    private totalCostUsd = 0;
    private sessionCompletions = 0;

    constructor(private sessionManager: SessionManager) {
        // Read debounce from settings
        const config = vscode.workspace.getConfiguration('aegion');
        this.DEBOUNCE_MS = config.get<number>('ghostText.debounceMs') || 600;

        // Completion confidence status bar
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            90,
        );
        this.statusBarItem.name = 'Aegion Ghost Text';
        this.statusBarItem.command = 'aegion.ghostText.showStats';

        // Cost tracking status bar
        this.costStatusBar = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            89,
        );
        this.costStatusBar.name = 'Aegion Completion Cost';
    }

    async provideInlineCompletionItems(
        document: vscode.TextDocument,
        position: vscode.Position,
        context: vscode.InlineCompletionContext,
        token: vscode.CancellationToken,
    ): Promise<vscode.InlineCompletionItem[] | null> {

        // ── 1. Session Check ──
        const state = this.sessionManager.getState();
        if (state.status !== 'active') {
            return null;
        }

        // ── 1b. Sensitive File Block ──
        const fileName = document.uri.fsPath;
        if (this.isSensitiveFile(fileName)) {
            this.showSensitiveWarning(document.uri);
            return null;
        }

        // ── 1c. Ghost Text Enabled Check ──
        const config = vscode.workspace.getConfiguration('aegion');
        if (!config.get<boolean>('ghostText.enabled', true)) {
            return null;
        }

        // ── 2. Smart Debounce with Cancellation ──
        const requestId = `ghost-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
        this.activeRequestId = requestId;

        await new Promise(resolve => {
            if (this.debounceTimer) { clearTimeout(this.debounceTimer); }
            this.debounceTimer = setTimeout(resolve, this.DEBOUNCE_MS);
        });

        // Check if this request was superseded by a newer one
        if (token.isCancellationRequested || this.activeRequestId !== requestId) {
            return null;
        }

        try {
            const api = getApiClient();

            // ── 3. Extract Prefix + Suffix ──
            const prefixStart = Math.max(0, position.line - this.PREFIX_LINES);
            const suffixEnd = Math.min(document.lineCount - 1, position.line + this.SUFFIX_LINES);

            const prefixRange = new vscode.Range(prefixStart, 0, position.line, position.character);
            const suffixRange = new vscode.Range(position.line, position.character, suffixEnd, document.lineAt(suffixEnd).text.length);

            const prefix = document.getText(prefixRange);
            const suffix = document.getText(suffixRange);

            // ── 4. Language-Aware Prompting ──
            const languageId = document.languageId;
            const languagePrompt = LANGUAGE_PROMPTS[languageId] || LANGUAGE_PROMPTS.default;

            // ── 5. Multi-line Detection ──
            const isMultiLine = this.detectMultiLineContext(prefix, languageId);

            // ── 6. FIM Format Detection ──
            const fimEnabled = this.isFimSupported();

            // ── 7. Call Backend ──
            this.statusBarItem.text = '$(loading~spin) Ghost...';
            this.statusBarItem.show();

            const suggestion = await api.completeGhostText({
                file_path: document.uri.fsPath,
                file_content: document.getText(),
                cursor_position: {
                    line: position.line,
                    character: position.character,
                },
                language_id: languageId,
                workspace_id: state.workspaceId || 'default',
                prefix,
                suffix,
                language_prompt: languagePrompt,
                fim_enabled: fimEnabled,
                max_tokens: isMultiLine ? 512 : 128,
                request_id: requestId,
            } as any);

            if (token.isCancellationRequested || this.activeRequestId !== requestId) {
                return null;
            }

            if (!suggestion || !suggestion.text) { return null; }

            // ── 8. Track Cost ──
            this.sessionCompletions++;
            if (suggestion.cost_usd) {
                this.totalCostUsd += suggestion.cost_usd;
                this.updateCostDisplay();
            }

            // ── 9. Confidence Display ──
            this.updateConfidenceDisplay(suggestion.confidence, languageId, suggestion.model);

            // ── 10. Create Completion Item ──
            const item = new vscode.InlineCompletionItem(
                suggestion.text,
                new vscode.Range(position, position),
            );

            // Track acceptance via command
            item.command = {
                command: 'aegion.ghostText.accepted',
                title: 'Ghost Text Accepted',
                arguments: [suggestion.confidence, languageId, suggestion.cost_usd || 0],
            };

            Logger.info(`GhostText: confidence=${suggestion.confidence} lang=${languageId} fim=${fimEnabled} multiLine=${isMultiLine} model=${suggestion.model || 'unknown'}`);
            return [item];

        } catch (error) {
            Logger.error('GhostText failed', error);
            this.statusBarItem.text = '$(error) Ghost';
            setTimeout(() => this.statusBarItem.hide(), 3000);
            return null;
        }
    }

    // ──────────────────────────────────────────────
    // Sensitive file detection
    // ──────────────────────────────────────────────

    private isSensitiveFile(filePath: string): boolean {
        const baseName = filePath.split('/').pop() || filePath.split('\\').pop() || '';
        return SENSITIVE_PATTERNS.some(p => p.test(baseName));
    }

    private showSensitiveWarning(uri: vscode.Uri): void {
        const diag = new vscode.Diagnostic(
            new vscode.Range(0, 0, 0, 1),
            'Aegion Ghost Text is disabled for sensitive files (secrets, .env, credentials)',
            vscode.DiagnosticSeverity.Information,
        );
        diag.source = 'aegion';
        diagnosticCollection.set(uri, [diag]);

        // Clear after 10 seconds
        setTimeout(() => diagnosticCollection.delete(uri), 10000);
    }

    // ──────────────────────────────────────────────
    // Multi-line detection
    // ──────────────────────────────────────────────

    private detectMultiLineContext(prefix: string, language: string): boolean {
        const lines = prefix.trimEnd().split('\n');
        const lastLine = lines[lines.length - 1]?.trimEnd() || '';

        // Python: after colon (def, class, if, for, etc.)
        if (language === 'python' && lastLine.endsWith(':')) { return true; }

        // C-family: after opening brace
        if (['typescript', 'javascript', 'java', 'csharp', 'cpp', 'rust', 'go'].includes(language)) {
            if (lastLine.endsWith('{')) { return true; }
        }

        // After function signature with no body
        if (/^(export\s+)?(async\s+)?function\s+\w+/.test(lastLine) && lastLine.endsWith('{')) {
            return true;
        }

        // Blank line after a definition
        if (lastLine === '' && lines.length >= 2) {
            const prevLine = lines[lines.length - 2]?.trimEnd() || '';
            if (prevLine.endsWith(':') || prevLine.endsWith('{')) { return true; }
        }

        return false;
    }

    // ──────────────────────────────────────────────
    // FIM detection
    // ──────────────────────────────────────────────

    private isFimSupported(): boolean {
        const config = vscode.workspace.getConfiguration('aegion');
        const completionModel = config.get<string>('completionModel') || '';
        return FIM_MODELS.has(completionModel.toLowerCase());
    }

    // ──────────────────────────────────────────────
    // Status bar displays
    // ──────────────────────────────────────────────

    private updateConfidenceDisplay(confidence: number | string, language: string, model?: string): void {
        const confNum = typeof confidence === 'number' ? confidence : parseFloat(confidence) || 0.5;
        const confPercent = Math.round(confNum * 100);

        let icon: string;
        let color: vscode.ThemeColor | undefined;
        if (confPercent >= 80) {
            icon = '$(pass-filled)';
            color = new vscode.ThemeColor('charts.green');
        } else if (confPercent >= 50) {
            icon = '$(info)';
            color = new vscode.ThemeColor('charts.yellow');
        } else {
            icon = '$(warning)';
            color = new vscode.ThemeColor('charts.orange');
        }

        this.statusBarItem.text = `${icon} Ghost: ${confPercent}%`;
        this.statusBarItem.color = color;
        this.statusBarItem.tooltip = [
            'Aegion Ghost Text',
            `Confidence: ${confPercent}%`,
            `Language: ${language}`,
            model ? `Model: ${model}` : '',
            `Accepted: ${this.acceptCount}`,
            `Dismissed: ${this.rejectCount}`,
            `Session completions: ${this.sessionCompletions}`,
            `Session cost: $${this.totalCostUsd.toFixed(4)}`,
        ].filter(Boolean).join('\n');
        this.statusBarItem.backgroundColor = undefined;
        this.statusBarItem.show();

        // Auto-hide after 8 seconds
        setTimeout(() => this.statusBarItem.hide(), 8000);
    }

    private updateCostDisplay(): void {
        this.costStatusBar.text = `$(credit-card) $${this.totalCostUsd.toFixed(3)}`;
        this.costStatusBar.tooltip = `Aegion Ghost Text Cost\nSession: $${this.totalCostUsd.toFixed(4)}\nCompletions: ${this.sessionCompletions}`;
        this.costStatusBar.show();
    }

    // ──────────────────────────────────────────────
    // Telemetry
    // ──────────────────────────────────────────────

    trackAccepted(confidence: number | string, language: string, _costUsd?: number): void {
        this.acceptCount++;
        const acceptRate = this.acceptCount / Math.max(this.acceptCount + this.rejectCount, 1);

        try {
            // eslint-disable-next-line @typescript-eslint/no-var-requires
            const { TelemetryService } = require('./TelemetryService');
            TelemetryService.getInstance().sendEvent('GhostTextAccepted', {
                confidence: String(confidence),
                language,
                totalAccepted: this.acceptCount,
                acceptRate: acceptRate.toFixed(3),
                sessionCost: this.totalCostUsd.toFixed(4),
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

    // ──────────────────────────────────────────────
    // Stats command
    // ──────────────────────────────────────────────

    showStats(): void {
        const total = this.acceptCount + this.rejectCount;
        const rate = total > 0 ? ((this.acceptCount / total) * 100).toFixed(1) : '0.0';

        vscode.window.showInformationMessage(
            'Aegion Ghost Text Stats\n' +
            `  Completions: ${this.sessionCompletions}\n` +
            `  Accepted: ${this.acceptCount} / Rejected: ${this.rejectCount}\n` +
            `  Accept Rate: ${rate}%\n` +
            `  Session Cost: $${this.totalCostUsd.toFixed(4)}`,
        );
    }

    dispose(): void {
        this.statusBarItem.dispose();
        this.costStatusBar.dispose();
        diagnosticCollection.dispose();
    }
}

export function registerGhostText(context: vscode.ExtensionContext, sessionManager: SessionManager) {
    const provider = new GhostTextService(sessionManager);
    const selector: vscode.DocumentSelector = { scheme: 'file', language: '*' };

    context.subscriptions.push(
        vscode.languages.registerInlineCompletionItemProvider(selector, provider),

        // Track acceptance
        vscode.commands.registerCommand('aegion.ghostText.accepted', (confidence: number, language: string, costUsd?: number) => {
            provider.trackAccepted(confidence, language, costUsd);
        }),

        // Show stats command
        vscode.commands.registerCommand('aegion.ghostText.showStats', () => {
            provider.showStats();
        }),

        // Toggle ghost text
        vscode.commands.registerCommand('aegion.ghostText.toggle', () => {
            const config = vscode.workspace.getConfiguration('aegion');
            const current = config.get<boolean>('ghostText.enabled', true);
            config.update('ghostText.enabled', !current, vscode.ConfigurationTarget.Workspace);
            vscode.window.showInformationMessage(`Aegion Ghost Text ${!current ? 'enabled' : 'disabled'}`);
        }),
    );
}
