/* eslint-disable @typescript-eslint/no-var-requires */
/**
 * End-to-End Extension Test — Phase 56
 *
 * Tests the full extension lifecycle:
 * 1. Extension activates
 * 2. Commands are registered
 * 3. New Phase 52-55 components are available
 */

import * as assert from 'assert';
import * as vscode from 'vscode';

suite('Extension E2E Tests', () => {

    test('extension should be present', () => {
        assert.ok(vscode.extensions.getExtension('aegion.aegion-vscode'));
    });

    test('extension should activate', async () => {
        const ext = vscode.extensions.getExtension('aegion.aegion-vscode');
        if (ext) {
            await ext.activate();
            assert.strictEqual(ext.isActive, true);
        }
    });

    test('core commands should be registered', async () => {
        const allCommands = await vscode.commands.getCommands(true);

        const requiredCommands = [
            'aegion.startSession',
            'aegion.closeSession',
            'aegion.invokeCouncil',
            'aegion.createProposal',
            'aegion.approveProposal',
            'aegion.setRole',
            'aegion.openDashboard',
            'aegion.openGovernanceCenter',
            'aegion.openTimeline',
        ];

        for (const cmd of requiredCommands) {
            assert.ok(
                allCommands.includes(cmd),
                `Command ${cmd} should be registered`,
            );
        }
    });

    test('Phase 52 auth commands should be registered', async () => {
        const allCommands = await vscode.commands.getCommands(true);

        // These should be registered by the extension
        const authCommands = [
            'aegion.setAuthToken',  // Legacy auth (always present)
        ];

        for (const cmd of authCommands) {
            assert.ok(
                allCommands.includes(cmd),
                `Auth command ${cmd} should be registered`,
            );
        }
    });

    test('Phase 54 ghost text command should be registered', async () => {
        const allCommands = await vscode.commands.getCommands(true);
        assert.ok(
            allCommands.includes('aegion.ghostText.accepted'),
            'Ghost text acceptance tracking command should be registered',
        );
    });

    test('panel commands should be registered', async () => {
        const allCommands = await vscode.commands.getCommands(true);

        const panelCommands = [
            'aegion.openDashboard',
            'aegion.openGovernanceCenter',
            'aegion.openTimeline',
            'aegion.openTaskInbox',
            'aegion.openCheckpoints',
            'aegion.openMemoryRules',
            'aegion.openSkillCatalog',
            'aegion.openCollaboration',
            'aegion.openWarRoom',
            'aegion.openAuditLog',
            'aegion.openAdminDashboard',
        ];

        for (const cmd of panelCommands) {
            assert.ok(
                allCommands.includes(cmd),
                `Panel command ${cmd} should be registered`,
            );
        }
    });

    test('new imports should not throw', () => {
        // Verify all new Phase 52-55 modules can be required
        assert.doesNotThrow(() => require('../../auth/FirebaseAuthProvider'));
        assert.doesNotThrow(() => require('../../views/SessionTreeProvider'));
        assert.doesNotThrow(() => require('../../views/TimelineTreeProvider'));
        assert.doesNotThrow(() => require('../../views/ProposalTreeProvider'));
        assert.doesNotThrow(() => require('../../views/RiskTreeProvider'));
        assert.doesNotThrow(() => require('../../views/CostTreeProvider'));
        assert.doesNotThrow(() => require('../../views/CouncilPanel'));
    });
});
