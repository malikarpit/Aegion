/**
 * Aegion Context Engine — Type Definitions
 *
 * Shared types for the workspace context system.
 * These types define the structured snapshot of the developer's
 * working environment that flows into sessions, council calls,
 * and ghost text completions.
 */

/** Metadata about a single open file. */
export interface FileContext {
    /** Absolute filesystem path. */
    path: string;
    /** VS Code language identifier (e.g. 'typescript', 'python'). */
    language: string;
    /** Total line count. */
    line_count: number;
    /** True if the file has unsaved modifications. */
    is_dirty: boolean;
}

/** A recent edit event captured by the engine. */
export interface EditEvent {
    /** Path of the edited file. */
    file_path: string;
    /** ISO timestamp of the edit. */
    timestamp: string;
    /** Number of lines affected by the edit. */
    lines_changed: number;
}

/** Git state of the current workspace. */
export interface GitContext {
    /** Current branch name, or 'unknown' if unavailable. */
    branch: string;
    /** True if there are uncommitted changes. */
    has_uncommitted: boolean;
    /** Root of the git repository, or null if not a repo. */
    repo_root: string | null;
}

/** Snapshot of the active Aegion session. */
export interface SessionSnapshot {
    session_id: string | null;
    status: string;
    decision_count: number;
    evidence_count: number;
    exploration_stage: string;
}

/**
 * Complete workspace context snapshot.
 *
 * This is the primary output of the ContextEngine — a frozen-in-time
 * representation of everything relevant about the developer's environment.
 */
export interface WorkspaceContext {
    /** Absolute path to the workspace root folder. */
    workspace_root: string;
    /** The currently focused file, or null if none. */
    active_file: FileContext | null;
    /** All files currently open in editors. */
    open_files: FileContext[];
    /** Recent edits (last N, configurable). */
    recent_edits: EditEvent[];
    /** Git state. */
    git: GitContext;
    /** Session state snapshot. */
    session: SessionSnapshot;
    /** SHA-256 hash of the context for deduplication / drift detection. */
    context_hash: string;
    /** ISO timestamp when this snapshot was taken. */
    timestamp: string;
}
