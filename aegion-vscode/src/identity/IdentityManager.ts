// Aegion Identity Manager
// Manages user roles and permissions within governance

import * as vscode from 'vscode';

export type AegionRole = 'developer' | 'architect' | 'admin';

interface RoleConfig {
    name: string;
    icon: string;
    description: string;
    permissions: string[];
}

const ROLE_CONFIGS: Record<AegionRole, RoleConfig> = {
    developer: {
        name: 'Developer',
        icon: '👨‍💻',
        description: 'Can create proposals, submit evidence, but needs review for T2+ decisions',
        permissions: [
            'session.start',
            'session.close',
            'proposal.create',
            'evidence.submit',
            'council.invoke',
        ],
    },
    architect: {
        name: 'Architect',
        icon: '🏛️',
        description: 'Can approve T2 decisions, supersede decisions, and review proposals',
        permissions: [
            'session.start',
            'session.close',
            'proposal.create',
            'proposal.approve',
            'proposal.reject',
            'decision.supersede',
            'evidence.submit',
            'evidence.classify',
            'council.invoke',
            'adr.generate',
        ],
    },
    admin: {
        name: 'Admin',
        icon: '🔐',
        description: 'Full permissions including freeze mode and system configuration',
        permissions: [
            '*', // All permissions
        ],
    },
};

export class IdentityManager {
    private static instance: IdentityManager;
    private statusBarItem: vscode.StatusBarItem;
    private currentRole: AegionRole = 'developer';
    private context: vscode.ExtensionContext;

    private constructor(context: vscode.ExtensionContext) {
        this.context = context;

        // Create status bar item
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Left,
            100,
        );
        this.statusBarItem.command = 'aegion.setRole';
        this.statusBarItem.tooltip = 'Click to change Aegion role';

        // Restore saved role
        const savedRole = context.workspaceState.get<AegionRole>('aegion.role');
        if (savedRole && ROLE_CONFIGS[savedRole]) {
            this.currentRole = savedRole;
        }

        this.updateStatusBar();
        this.statusBarItem.show();
    }

    public static getInstance(context?: vscode.ExtensionContext): IdentityManager {
        if (!IdentityManager.instance) {
            if (!context) {
                throw new Error('IdentityManager must be initialized with context first');
            }
            IdentityManager.instance = new IdentityManager(context);
        }
        return IdentityManager.instance;
    }

    public getRole(): AegionRole {
        return this.currentRole;
    }

    public getRoleConfig(): RoleConfig {
        return ROLE_CONFIGS[this.currentRole];
    }

    public async setRole(role: AegionRole): Promise<void> {
        this.currentRole = role;
        await this.context.workspaceState.update('aegion.role', role);
        this.updateStatusBar();

        vscode.window.showInformationMessage(
            `Aegion role set to ${ROLE_CONFIGS[role].icon} ${ROLE_CONFIGS[role].name}`,
        );
    }

    public async promptRoleSelection(): Promise<AegionRole | undefined> {
        const items = Object.entries(ROLE_CONFIGS).map(([key, config]) => ({
            label: `${config.icon} ${config.name}`,
            description: config.description,
            role: key as AegionRole,
        }));

        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: 'Select your governance role',
        });

        if (selected) {
            await this.setRole(selected.role);
            return selected.role;
        }
        return undefined;
    }

    public hasPermission(permission: string): boolean {
        const config = ROLE_CONFIGS[this.currentRole];

        // Admin has all permissions
        if (config.permissions.includes('*')) {
            return true;
        }

        return config.permissions.includes(permission);
    }

    public requirePermission(permission: string): boolean {
        if (!this.hasPermission(permission)) {
            const config = ROLE_CONFIGS[this.currentRole];
            vscode.window.showWarningMessage(
                `⚠️ Permission denied: ${permission} requires higher role (current: ${config.name})`,
            );
            return false;
        }
        return true;
    }

    private updateStatusBar(): void {
        const config = ROLE_CONFIGS[this.currentRole];
        this.statusBarItem.text = `${config.icon} Aegion: ${config.name}`;
    }

    public dispose(): void {
        this.statusBarItem.dispose();
    }
}

export function getIdentityManager(context?: vscode.ExtensionContext): IdentityManager {
    return IdentityManager.getInstance(context);
}
