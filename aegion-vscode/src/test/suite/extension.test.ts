/* eslint-disable @typescript-eslint/no-var-requires */
import * as assert from 'assert';

// You can import and use all API from the 'vscode' module
// as well as import your extension to test it
import * as vscode from 'vscode';
// import * as myExtension from '../../extension';

suite('Extension Test Suite', () => {
    vscode.window.showInformationMessage('Start all tests.');

    test('Sample test', () => {
        assert.strictEqual(-1, [1, 2, 3].indexOf(5));
        assert.strictEqual(-1, [1, 2, 3].indexOf(0));
    });

    test('Extension should accept activation', () => {
        // Just verify vscode module is present and we can mock basic interactions
        assert.ok(vscode.extensions);
    });

    test('Views should be importable', async () => {
        // Dynamic import to verify modules load without error
        const dashboard = await import('../../views/Dashboard.js');
        const collaboration = await import('../../views/collaboration.js');
        const chronos = await import('../../views/ChronosExplorer.js');
        const warroom = await import('../../views/WarRoomPanel.js');

        assert.ok(dashboard.DashboardPanel, 'DashboardPanel should be exported');
        assert.ok(collaboration.CollaborationPanel, 'CollaborationPanel should be exported');
        assert.ok(chronos.ChronosExplorerProvider, 'ChronosExplorerProvider should be exported');
        assert.ok(warroom.WarRoomPanel, 'WarRoomPanel should be exported');
    });
});
