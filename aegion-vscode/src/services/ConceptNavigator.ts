
import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

export class ConceptNavigator implements vscode.DefinitionProvider, vscode.TextDocumentContentProvider {
    static scheme = 'aegion-concept';

    // DefinitionProvider
    async provideDefinition(
        document: vscode.TextDocument,
        position: vscode.Position,
        _token: vscode.CancellationToken,
    ): Promise<vscode.Definition | undefined> {
        const wordRange = document.getWordRangeAtPosition(position);
        if (!wordRange) {return undefined;}

        const word = document.getText(wordRange);
        if (word.length < 3) {return undefined;} // Ignore short words

        try {
            const api = getApiClient();
            // Use memory query to find relevant concepts/decisions matching the term
            const results = await api.queryMemory(word);

            // Filter for high confidence or exact matches in key/tags
            // Filter for high confidence or exact matches in content or metadata
            const relevant = results.results.find(r =>
                r.id.toLowerCase().includes(word.toLowerCase()) ||
                r.content.toLowerCase().includes(word.toLowerCase()) ||
                (r.metadata?.tags && Array.isArray(r.metadata.tags) && (r.metadata.tags as string[]).some(t => t.toLowerCase() === word.toLowerCase())),
            );

            if (relevant) {
                const uri = vscode.Uri.parse(`${ConceptNavigator.scheme}:${relevant.id}`);
                return new vscode.Location(uri, new vscode.Position(0, 0));
            }
        } catch (e) {
            console.error('Concept lookup failed:', e);
        }
        return undefined;
    }

    // TextDocumentContentProvider
    async provideTextDocumentContent(uri: vscode.Uri): Promise<string> {
        const memoryId = uri.path;
        try {
            const api = getApiClient();
            const memory = await api.getMemory(memoryId);
            return JSON.stringify(memory, null, 2);
        } catch (e) {
            return `Error loading concept: ${e}`;
        }
    }
}

export function registerConceptNavigation(context: vscode.ExtensionContext) {
    const provider = new ConceptNavigator();

    // Register Definition Provider
    const selector: vscode.DocumentSelector = [
        { scheme: 'file', language: 'typescript' },
        { scheme: 'file', language: 'python' },
        { scheme: 'file', language: 'javascript' },
        { scheme: 'file', language: 'json' },
    ];
    context.subscriptions.push(
        vscode.languages.registerDefinitionProvider(selector, provider),
    );

    // Register Virtual Document Provider
    context.subscriptions.push(
        vscode.workspace.registerTextDocumentContentProvider(ConceptNavigator.scheme, provider),
    );

    // Command to manually look up
    context.subscriptions.push(
        vscode.commands.registerCommand('aegion.lookupConcept', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {return;}

            const position = editor.selection.active;
            const defs = await provider.provideDefinition(editor.document, position, new vscode.CancellationTokenSource().token);

            if (defs) {
                const loc = Array.isArray(defs) ? defs[0] : defs;
                if (loc instanceof vscode.Location) {
                    const doc = await vscode.workspace.openTextDocument(loc.uri);
                    await vscode.window.showTextDocument(doc, { preview: true, viewColumn: vscode.ViewColumn.Beside });
                }
            } else {
                vscode.window.showInformationMessage('No concept found for current word.');
            }
        }),
    );
}
