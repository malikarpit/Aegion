/**
 * Aegion Context Engine — Barrel Export
 */

export { ContextEngine, getContextEngine, registerContextEngine } from './ContextEngine';
export type {
    WorkspaceContext,
    FileContext,
    EditEvent,
    GitContext,
    SessionSnapshot,
} from './types';
