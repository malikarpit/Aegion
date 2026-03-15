// Aegion Cursor Tracker
// Shows collaborator cursor positions in real-time

import * as vscode from 'vscode';

interface CursorPosition {
    userId: string;
    displayName: string;
    file: string;
    line: number;
    column: number;
    color: string;
}

export class CursorTracker {
    private decorationType: vscode.TextEditorDecorationType;
    private cursors: Map<string, CursorPosition> = new Map();
    private updateInterval: ReturnType<typeof setInterval> | null = null;

    // Predefined colors for collaborators
    private readonly colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4',
        '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F',
    ];
    private colorIndex = 0;

    constructor() {
        this.decorationType = vscode.window.createTextEditorDecorationType({
            borderWidth: '2px',
            borderStyle: 'solid',
            after: {
                margin: '0 0 0 10px',
            },
        });

        // Start update loop
        this.startUpdating();
    }

    private startUpdating() {
        this.updateInterval = setInterval(() => {
            this.renderCursors();
        }, 100);
    }

    public updateCursor(userId: string, displayName: string, file: string, line: number, column: number): void {
        let cursor = this.cursors.get(userId);

        if (!cursor) {
            cursor = {
                userId,
                displayName,
                file,
                line,
                column,
                color: this.colors[this.colorIndex++ % this.colors.length],
            };
        } else {
            cursor.file = file;
            cursor.line = line;
            cursor.column = column;
        }

        this.cursors.set(userId, cursor);
    }

    public removeCursor(userId: string): void {
        this.cursors.delete(userId);
        this.renderCursors();
    }

    private renderCursors(): void {
        const activeEditor = vscode.window.activeTextEditor;
        if (!activeEditor) {return;}

        const currentFile = activeEditor.document.uri.fsPath;

        // Filter to cursors in current file
        const visibleCursors = Array.from(this.cursors.values())
            .filter(c => c.file === currentFile);

        // Create decorations
        const decorations: vscode.DecorationOptions[] = visibleCursors.map(cursor => {
            const position = new vscode.Position(cursor.line, cursor.column);
            const range = new vscode.Range(position, position);

            return {
                range,
                hoverMessage: cursor.displayName,
                renderOptions: {
                    after: {
                        contentText: ` ${cursor.displayName}`,
                        color: cursor.color,
                        fontStyle: 'italic',
                        fontSize: '10px',
                    },
                    border: `2px solid ${cursor.color}`,
                },
            };
        });

        activeEditor.setDecorations(this.decorationType, decorations);
    }

    public getCursors(): CursorPosition[] {
        return Array.from(this.cursors.values());
    }

    public dispose(): void {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        this.decorationType.dispose();
    }
}

export function createCursorTracker(): CursorTracker {
    return new CursorTracker();
}
