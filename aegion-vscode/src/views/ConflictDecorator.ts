
import * as vscode from 'vscode';
import { CollaborationService } from '../services/CollaborationService';
import { Conflict } from '../api/types';

export class ConflictDecorator {
    private decorationType: vscode.TextEditorDecorationType;
    private conflicts: Map<string, Conflict[]> = new Map();
    private disposables: vscode.Disposable[] = [];

    constructor(private collaborationService: CollaborationService) {
        this.decorationType = vscode.window.createTextEditorDecorationType({
            backgroundColor: 'rgba(255, 0, 0, 0.1)',
            border: '1px solid rgba(255, 0, 0, 0.5)',
            overviewRulerColor: 'red',
            overviewRulerLane: vscode.OverviewRulerLane.Right,
            after: {
                contentText: ' ⚠️ Governance Violation',
                color: 'red',
                margin: '0 0 0 10px',
            },
        });

        // Listen for conflicts
        this.disposables.push(
            this.collaborationService.onConflictDetected((conflict) => {
                this.addConflict(conflict);
            }),
        );

        // Listen for editor changes
        this.disposables.push(
            vscode.window.onDidChangeActiveTextEditor((editor) => {
                if (editor) {
                    this.updateDecorations(editor);
                }
            }),
        );
    }

    private addConflict(conflict: Conflict) {
        if (!conflict.file_path) { return; }

        // Normalize path (simple check for now)
        const _uri = vscode.Uri.file(conflict.file_path); // Backend sends relative or absolute? Assuming workspace relative for now needs careful handling
        // For simplicity, let's assume backend sends relative path and we match loosely or user ensures workspace root matches

        const existing = this.conflicts.get(conflict.file_path) || [];
        existing.push(conflict);
        this.conflicts.set(conflict.file_path, existing);

        // If current editor matches, update
        const editor = vscode.window.activeTextEditor;
        if (editor && editor.document.uri.fsPath.endsWith(conflict.file_path)) {
            this.updateDecorations(editor);
        }
    }

    private updateDecorations(editor: vscode.TextEditor) {
        // Find conflicts for this file
        // Naive path matching
        const relativePath = vscode.workspace.asRelativePath(editor.document.uri);
        const fileConflicts = this.conflicts.get(relativePath) || [];

        const decorations: vscode.DecorationOptions[] = [];
        for (const conflict of fileConflicts) {
            const line = conflict.line_number ? conflict.line_number - 1 : 0; // 0-indexed
            const range = new vscode.Range(line, 0, line, 100); // 100 chars fallback

            const decoration: vscode.DecorationOptions = {
                range,
                hoverMessage: `**Governance Conflict**: ${conflict.message} (${conflict.severity})`,
            };
            decorations.push(decoration);
        }

        editor.setDecorations(this.decorationType, decorations);
    }

    public dispose() {
        this.decorationType.dispose();
        this.disposables.forEach(d => d.dispose());
    }
}
