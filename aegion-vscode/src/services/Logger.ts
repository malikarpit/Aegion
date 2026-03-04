import * as vscode from 'vscode';

export enum LogLevel {
    DEBUG = 0,
    INFO = 1,
    WARN = 2,
    ERROR = 3
}

export class Logger {
    private static _outputChannel: vscode.OutputChannel;
    private static _logLevel: LogLevel = LogLevel.INFO;

    public static initialize(context: vscode.ExtensionContext, logLevel: LogLevel = LogLevel.INFO): void {
        this._outputChannel = vscode.window.createOutputChannel('Aegion');
        this._logLevel = logLevel;
        context.subscriptions.push(this._outputChannel);
    }

    public static setLogLevel(level: LogLevel): void {
        this._logLevel = level;
    }

    private static _log(level: LogLevel, message: string, ...args: unknown[]): void {
        if (level < this._logLevel) {
            return;
        }

        const date = new Date().toISOString();
        const levelName = LogLevel[level];
        let formattedMessage = `[${date}] [${levelName}] ${message}`;

        if (args.length > 0) {
            formattedMessage += ' ' + args.map(arg => {
                if (arg instanceof Error) {
                    return arg.stack || arg.message;
                }
                if (typeof arg === 'object') {
                    try {
                        return JSON.stringify(arg);
                    } catch (e) {
                        return String(arg);
                    }
                }
                return String(arg);
            }).join(' ');
        }

        if (this._outputChannel) {
            this._outputChannel.appendLine(formattedMessage);
        } else {
            // Fallback if not initialized (e.g. tests)
            // eslint-disable-next-line no-console
            console.log(formattedMessage);
        }
    }

    public static debug(message: string, ...args: unknown[]): void {
        this._log(LogLevel.DEBUG, message, ...args);
    }

    public static info(message: string, ...args: unknown[]): void {
        this._log(LogLevel.INFO, message, ...args);
    }

    public static warn(message: string, ...args: unknown[]): void {
        this._log(LogLevel.WARN, message, ...args);
    }

    public static error(message: string, ...args: unknown[]): void {
        this._log(LogLevel.ERROR, message, ...args);
    }

    public static show(): void {
        this._outputChannel?.show();
    }
}
