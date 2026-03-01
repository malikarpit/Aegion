// Aegion VS Code Extension - Configuration

export interface AegionConfig {
    backendUrl: string;
    sessionTimeoutMinutes: number;
    debugMode: boolean;
}

export function getConfig(): AegionConfig {
    // Phase 0: Hardcoded defaults
    // Phase 1: Read from VS Code settings
    return {
        backendUrl: process.env.AEGION_BACKEND_URL || 'http://localhost:8000',
        sessionTimeoutMinutes: 120,
        debugMode: process.env.NODE_ENV === 'development',
    };
}

/**
 * Derive the active workspace ID from the VS Code workspace folder.
 * Falls back to 'default-workspace' if no folder is open.
 */
export function getActiveWorkspaceId(): string {
    try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const vscode = require('vscode');
        const folders = vscode.workspace.workspaceFolders;
        if (folders && folders.length > 0) {
            return folders[0].name;
        }
    } catch {
        // Running outside VS Code context (tests, etc.)
    }
    return 'default-workspace';
}
