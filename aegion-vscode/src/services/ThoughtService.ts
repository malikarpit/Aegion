
import * as vscode from 'vscode';
import { AegionClient } from '../api/client';
import {
    ThoughtCommit,
    CreateThoughtRequest,
} from '../api/types';

export class ThoughtService {
    private static instance: ThoughtService;
    private client: AegionClient;
    private _currentDraft: ThoughtCommit | undefined;

    // Event emitter for UI updates
    private _onDidChangeDraft = new vscode.EventEmitter<ThoughtCommit | undefined>();
    public readonly onDidChangeDraft = this._onDidChangeDraft.event;

    private constructor(client: AegionClient) {
        this.client = client;
    }

    public static getInstance(client: AegionClient): ThoughtService {
        if (!ThoughtService.instance) {
            ThoughtService.instance = new ThoughtService(client);
        }
        return ThoughtService.instance;
    }

    public get currentDraft(): ThoughtCommit | undefined {
        return this._currentDraft;
    }

    /**
     * Start a new thought draft.
     */
    public async startDraft(title: string, rationale: string, sessionId: string, workspaceId: string): Promise<ThoughtCommit> {
        const req: CreateThoughtRequest = {
            workspace_id: workspaceId,
            session_id: sessionId,
            title,
            rationale,
        };

        try {
            const thought = await this.client.thoughts.create(req);
            this._currentDraft = thought;
            this._onDidChangeDraft.fire(this._currentDraft);
            return thought;
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to create thought: ${error}`);
            throw error;
        }
    }

    /**
     * Update the current draft locally (and optionally sync to backend)
     * For now we just update backend immediately for simplicity,
     * but we could debounce this.
     */
    public async updateDraft(updates: { title?: string, rationale?: string, alternatives?: string[] }): Promise<ThoughtCommit> {
        if (!this._currentDraft) {
            throw new Error('No active draft to update');
        }

        try {
            const updated = await this.client.thoughts.update(this._currentDraft.thought_id, {
                title: updates.title,
                rationale: updates.rationale,
                alternatives: updates.alternatives,
            });
            this._currentDraft = updated;
            this._onDidChangeDraft.fire(this._currentDraft);
            return updated;
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to update thought: ${error}`);
            throw error;
        }
    }

    /**
     * Seal the current draft.
     */
    public async sealDraft(): Promise<ThoughtCommit> {
        if (!this._currentDraft) {
            throw new Error('No active draft to seal');
        }

        try {
            const sealed = await this.client.thoughts.seal(this._currentDraft.thought_id);
            this._currentDraft = sealed;
            this._onDidChangeDraft.fire(this._currentDraft);
            vscode.window.showInformationMessage(`Thought sealed: ${sealed.thought_id}`);
            return sealed;
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to seal thought: ${error}`);
            throw error;
        }
    }

    /**
     * Link the current (sealed) thought to a commit.
     */
    public async linkToCommit(commitSha: string, repoPath?: string): Promise<void> {
        if (!this._currentDraft) {
            throw new Error('No active thought to link');
        }

        // Ensure it's sealed (policy) -> backend enforces most logic, but good to check state
        if (this._currentDraft.state !== 'sealed') {
            const selection = await vscode.window.showWarningMessage(
                'Thought is not sealed yet. Seal it now?',
                'Seal & Link', 'Cancel',
            );
            if (selection === 'Seal & Link') {
                await this.sealDraft();
            } else {
                return;
            }
        }

        try {
            await this.client.thoughts.linkCommit(this._currentDraft.thought_id, {
                commit_sha: commitSha,
                repo_path: repoPath,
            });
            vscode.window.showInformationMessage(`Linked thought ${this._currentDraft.thought_id} to commit ${commitSha.substring(0, 7)}`);

            // Clear draft after successful link? Or keep it for reference?
            // Usually we clear it to start a new one for the next task.
            this._currentDraft = undefined;
            this._onDidChangeDraft.fire(undefined);

        } catch (error) {
            vscode.window.showErrorMessage(`Failed to link commit: ${error}`);
            throw error;
        }
    }

    public clearDraft(): void {
        this._currentDraft = undefined;
        this._onDidChangeDraft.fire(undefined);
    }

    /**
     * Generate a markdown report of thoughts for a list of commits.
     */
    public async generateReport(commitShas: string[]): Promise<string> {
        let report = `# Thought Report\n\nGenerated at ${new Date().toISOString()}\n\n`;
        let foundCount = 0;

        for (const sha of commitShas) {
            try {
                const thought = await this.client.thoughts.getByCommit(sha);
                if (thought) {
                    foundCount++;
                    report += `## ${thought.title} (${sha.substring(0, 7)})\n`;
                    report += `**Rationale:** ${thought.rationale}\n\n`;
                    if (thought.alternatives && thought.alternatives.length > 0) {
                        report += `**Alternatives:**\n${thought.alternatives.map(a => `- ${a}`).join('\n')}\n`;
                    }
                    report += '\n---\n\n';
                }
            } catch (error) {
                // Ignore missing thoughts or errors
                // console.log(`No thought for ${sha}`);
            }
        }

        if (foundCount === 0) {
            report += 'No thoughts found for the provided commits.';
        } else {
            report += `\n*Found ${foundCount} thoughts linking to ${commitShas.length} commits.*`;
        }

        return report;
    }
}
