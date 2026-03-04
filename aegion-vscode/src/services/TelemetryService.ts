import * as vscode from 'vscode';

export class TelemetryService implements vscode.Disposable {
    private outputChannel: vscode.OutputChannel;
    private static instance: TelemetryService;

    private constructor() {
        this.outputChannel = vscode.window.createOutputChannel('Aegion Telemetry');
    }

    public static getInstance(): TelemetryService {
        if (!TelemetryService.instance) {
            TelemetryService.instance = new TelemetryService();
        }
        return TelemetryService.instance;
    }

    /**
     * Log a telemetry event.
     * @param eventName The name of the event (e.g., 'CouncilInvoke', 'VoteCast')
     * @param properties Optional custom properties
     */
    public sendEvent(eventName: string, properties?: Record<string, unknown>): void {
        const timestamp = new Date().toISOString();
        const data = JSON.stringify(properties || {});
        // In a real implementation, this would send data to a backend or analytics service.
        // For now, we log to the Output Channel for observability.
        this.outputChannel.appendLine(`[${timestamp}] [EVENT] ${eventName}: ${data}`);
    }

    /**
     * Log an error event.
     * @param errorName The name of the error context
     * @param error The error object or message
     */
    public sendError(errorName: string, error: unknown): void {
        const timestamp = new Date().toISOString();
        const errorMessage = error instanceof Error ? error.message : String(error);
        this.outputChannel.appendLine(`[${timestamp}] [ERROR] ${errorName}: ${errorMessage}`);
    }

    public dispose() {
        this.outputChannel.dispose();
    }
}
