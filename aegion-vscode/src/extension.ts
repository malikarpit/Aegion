/**
 * Aegion VS Code Extension - Entry Point
 *
 * Initial version with core commands.
 */

import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
    console.log('Aegion extension activated');

    // Core commands
    context.subscriptions.push(
        vscode.commands.registerCommand('aegion.startSession', () => {
            vscode.window.showInformationMessage('Starting Aegion session...');
        }),
        vscode.commands.registerCommand('aegion.closeSession', () => {
            vscode.window.showInformationMessage('Session closed.');
        }),
        vscode.commands.registerCommand('aegion.invokeCouncil', () => {
            vscode.window.showInformationMessage('Invoking AI Council...');
        }),
        vscode.commands.registerCommand('aegion.createProposal', () => {
            vscode.window.showInformationMessage('Creating proposal...');
        }),
        vscode.commands.registerCommand('aegion.openDashboard', () => {
            vscode.window.showInformationMessage('Opening dashboard...');
        })
    );
}

export function deactivate() {}
