/* eslint-disable @typescript-eslint/no-var-requires */
/**
 * Tree View Provider Tests — Phase 56
 *
 * Tests for all 5 Phase 53 TreeView providers:
 * - SessionTreeProvider
 * - TimelineTreeProvider
 * - ProposalTreeProvider
 * - RiskTreeProvider
 * - CostTreeProvider
 */

import * as assert from 'assert';

suite('TreeView Providers', () => {

    // ──────────────────────────────────────────────
    // Session Tree
    // ──────────────────────────────────────────────
    suite('SessionTreeProvider', () => {
        test('should be importable', () => {
            const mod = require('../../views/SessionTreeProvider');
            assert.ok(mod.SessionTreeProvider);
            assert.ok(mod.registerSessionTree);
        });

        test('should show empty state with no sessions', async () => {
            const mod = require('../../views/SessionTreeProvider');
            const mockContext = {
                subscriptions: [],
            };
            const provider = new mod.SessionTreeProvider(mockContext);
            const children = await provider.getChildren();
            assert.ok(Array.isArray(children));
            provider.dispose();
        });
    });

    // ──────────────────────────────────────────────
    // Timeline Tree
    // ──────────────────────────────────────────────
    suite('TimelineTreeProvider', () => {
        test('should be importable', () => {
            const mod = require('../../views/TimelineTreeProvider');
            assert.ok(mod.TimelineTreeProvider);
            assert.ok(mod.registerTimelineTree);
        });

        test('should show empty state without workspace', async () => {
            const mod = require('../../views/TimelineTreeProvider');
            const mockContext = {
                subscriptions: [],
            };
            const provider = new mod.TimelineTreeProvider(mockContext);
            const children = await provider.getChildren();
            assert.ok(children.length === 1);
            assert.ok(children[0].label.includes('No workspace'));
            provider.dispose();
        });
    });

    // ──────────────────────────────────────────────
    // Proposal Tree
    // ──────────────────────────────────────────────
    suite('ProposalTreeProvider', () => {
        test('should be importable', () => {
            const mod = require('../../views/ProposalTreeProvider');
            assert.ok(mod.ProposalTreeProvider);
            assert.ok(mod.registerProposalTree);
        });

        test('should show empty state without workspace', async () => {
            const mod = require('../../views/ProposalTreeProvider');
            const mockContext = {
                subscriptions: [],
            };
            const provider = new mod.ProposalTreeProvider(mockContext);
            const children = await provider.getChildren();
            assert.ok(children.length === 1);
            assert.ok(children[0].label.includes('No workspace'));
            provider.dispose();
        });

        test('should render proposal tree items with correct icons', () => {
            const mod = require('../../views/ProposalTreeProvider');
            const mockContext = { subscriptions: [] };
            const provider = new mod.ProposalTreeProvider(mockContext);

            const item = provider.getTreeItem({
                type: 'proposal',
                label: 'Test Proposal',
                status: 'pending',
                tier: 'T2',
            });

            assert.ok(item);
            assert.ok(item.description?.includes('T2'));
            provider.dispose();
        });
    });

    // ──────────────────────────────────────────────
    // Risk Tree
    // ──────────────────────────────────────────────
    suite('RiskTreeProvider', () => {
        test('should be importable', () => {
            const mod = require('../../views/RiskTreeProvider');
            assert.ok(mod.RiskTreeProvider);
            assert.ok(mod.registerRiskTree);
        });

        test('should show empty state without workspace', async () => {
            const mod = require('../../views/RiskTreeProvider');
            const mockContext = { subscriptions: [] };
            const provider = new mod.RiskTreeProvider(mockContext);
            const children = await provider.getChildren();
            assert.ok(children[0].label.includes('No workspace'));
            provider.dispose();
        });
    });

    // ──────────────────────────────────────────────
    // Cost Tree
    // ──────────────────────────────────────────────
    suite('CostTreeProvider', () => {
        test('should be importable', () => {
            const mod = require('../../views/CostTreeProvider');
            assert.ok(mod.CostTreeProvider);
            assert.ok(mod.registerCostTree);
        });

        test('should show empty state without workspace', async () => {
            const mod = require('../../views/CostTreeProvider');
            const mockContext = { subscriptions: [] };
            const provider = new mod.CostTreeProvider(mockContext);
            const children = await provider.getChildren();
            assert.ok(children[0].label.includes('No workspace'));
            provider.dispose();
        });
    });
});
