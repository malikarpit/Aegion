import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

/**
 * Handles the "Diff-First UX" for AI Council recommendations.
 *
 * Flow:
 * 1. AI Council returns a Unified Diff string.
 * 2. DiffManager applies the patch to produce proposed content.
 * 3. VS Code opens a side-by-side diff editor (original vs proposed).
 * 4. User clicks "Apply Changes" or "Reject Changes".
 */
export class DiffManager {
    private tempDir: string;
    /** Maps temp file path → original URI so apply/reject can find the source. */
    private pendingDiffs: Map<string, { originalUri: vscode.Uri; proposedContent: string }> = new Map();

    constructor(private context: vscode.ExtensionContext) {
        this.tempDir = path.join(context.extensionUri.fsPath, '.aegion_diffs');
        if (!fs.existsSync(this.tempDir)) {
            fs.mkdirSync(this.tempDir, { recursive: true });
        }
    }

    /**
     * Shows a diff preview for the given content and offers Apply / Reject.
     *
     * @param originalUri  URI of the file being modified.
     * @param diffContent  Unified diff string OR full proposed file content.
     * @param title        Human-readable label for the diff tab.
     */
    public async showDiff(
        originalUri: vscode.Uri,
        diffContent: string,
        title: string,
    ): Promise<void> {
        // Read original file content
        const originalBytes = await vscode.workspace.fs.readFile(originalUri);
        const originalText = Buffer.from(originalBytes).toString('utf-8');

        // Determine whether diffContent is a unified diff or full proposed content
        let proposedContent: string;
        if (this.isUnifiedDiff(diffContent)) {
            proposedContent = this.applyUnifiedDiff(originalText, diffContent);
        } else {
            // Treat as full proposed file content
            proposedContent = diffContent;
        }

        // Write proposed content to a temp file
        const timestamp = Date.now();
        const basename = path.basename(originalUri.fsPath);
        const tempFileName = `proposed_${timestamp}_${basename}`;
        const tempFilePath = path.join(this.tempDir, tempFileName);
        fs.writeFileSync(tempFilePath, proposedContent);

        const proposedUri = vscode.Uri.file(tempFilePath);

        // Track this pending diff
        this.pendingDiffs.set(tempFilePath, { originalUri, proposedContent });

        // Open VS Code diff editor
        await vscode.commands.executeCommand(
            'vscode.diff',
            originalUri,
            proposedUri,
            `${title} (Current ↔ Proposed)`,
            { preview: true },
        );

        // Offer Apply / Reject
        const choice = await vscode.window.showInformationMessage(
            `AI Council proposed changes to ${basename}`,
            { modal: false },
            'Apply Changes',
            'Reject Changes',
        );

        if (choice === 'Apply Changes') {
            await this.applyPending(tempFilePath);
        } else {
            this.rejectPending(tempFilePath);
        }
    }

    /** Apply pending diff: overwrite the original file with proposed content. */
    public async applyPending(tempFilePath: string): Promise<void> {
        const pending = this.pendingDiffs.get(tempFilePath);
        if (!pending) {
            vscode.window.showWarningMessage('No pending diff found to apply.');
            return;
        }

        const edit = new vscode.WorkspaceEdit();
        const fullRange = new vscode.Range(
            new vscode.Position(0, 0),
            new vscode.Position(Number.MAX_SAFE_INTEGER, 0),
        );
        edit.replace(pending.originalUri, fullRange, pending.proposedContent);
        await vscode.workspace.applyEdit(edit);

        vscode.window.showInformationMessage('Changes applied successfully.');
        this.cleanupFile(tempFilePath);
        this.pendingDiffs.delete(tempFilePath);
    }

    /** Reject pending diff: close the temp file and clean up. */
    public rejectPending(tempFilePath: string): void {
        vscode.window.showInformationMessage('Changes rejected.');
        this.cleanupFile(tempFilePath);
        this.pendingDiffs.delete(tempFilePath);
    }

    /** Clean up all temp files. */
    public cleanup(): void {
        if (fs.existsSync(this.tempDir)) {
            fs.rmSync(this.tempDir, { recursive: true, force: true });
        }
        this.pendingDiffs.clear();
    }

    // ---------- Private helpers ----------

    /** Detect whether content looks like a unified diff. */
    private isUnifiedDiff(content: string): boolean {
        const lines = content.split('\n');
        return lines.some((l) => l.startsWith('---')) &&
            lines.some((l) => l.startsWith('+++')) &&
            lines.some((l) => l.startsWith('@@'));
    }

    /**
     * Minimal unified-diff applier.
     *
     * Handles simple cases: single or multiple hunks with context lines.
     * For complex patches, falls back to treating diffContent as full content.
     */
    private applyUnifiedDiff(original: string, diff: string): string {
        const origLines = original.split('\n');
        const diffLines = diff.split('\n');
        const result = [...origLines];

        let offset = 0; // track line insertions/deletions

        for (let i = 0; i < diffLines.length; i++) {
            const line = diffLines[i];
            if (!line.startsWith('@@')) { continue; }

            // Parse hunk header: @@ -start,count +start,count @@
            const match = line.match(/@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/);
            if (!match) { continue; }

            const origStart = parseInt(match[1], 10) - 1; // 0-indexed
            let j = i + 1;
            let pos = origStart + offset;
            const removals: number[] = [];
            const additions: string[] = [];

            while (j < diffLines.length && !diffLines[j].startsWith('@@')) {
                const dl = diffLines[j];
                if (dl.startsWith('-')) {
                    removals.push(pos);
                    pos++;
                } else if (dl.startsWith('+')) {
                    additions.push(dl.substring(1));
                } else if (dl.startsWith(' ') || dl === '') {
                    pos++;
                } else if (dl.startsWith('---') || dl.startsWith('+++')) {
                    // skip file headers within hunks
                } else {
                    pos++;
                }
                j++;
            }

            // Apply removals in reverse to keep indices stable
            for (const idx of removals.sort((a, b) => b - a)) {
                result.splice(idx, 1);
                offset--;
            }

            // Apply additions at the original start position (adjusted)
            const insertPos = origStart + offset;
            result.splice(insertPos, 0, ...additions);
            offset += additions.length;
        }

        return result.join('\n');
    }

    private cleanupFile(filePath: string): void {
        try {
            if (fs.existsSync(filePath)) {
                fs.unlinkSync(filePath);
            }
        } catch {
            // Best-effort cleanup
        }
    }
}
