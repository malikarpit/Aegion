import WebSocket from 'ws';
import { EventEmitter } from 'events';
import { Logger } from '../services/Logger';

export interface WebSocketMessage {
    type: string;
    sequence_id?: number;
    timestamp?: string;
    [key: string]: unknown;
}

export class AegionSocket extends EventEmitter {
    private url: string;
    private token: string;
    private apiBaseUrl: string;
    private socket: WebSocket | null = null;
    private isConnected: boolean = false;
    private reconnectAttempts: number = 0;
    private maxReconnectAttempts: number = 10;
    private baseReconnectDelay: number = 1000;
    private lastSequenceId: number | null = null;
    private messageBuffer: WebSocketMessage[] = [];
    private explicitClose: boolean = false;

    constructor(url: string, token: string, apiBaseUrl?: string) {
        super();
        this.url = url;
        this.token = token;
        // Derive HTTP base URL from WebSocket URL for ticket exchange
        this.apiBaseUrl = apiBaseUrl || url.replace(/^ws/, 'http').replace(/\/ws\/.*$/, '');
    }

    /**
     * Obtain a short-lived, one-time-use WebSocket ticket via HTTP.
     * The ticket expires after 30 seconds or first use, whichever comes first.
     * This prevents token exposure in server logs, browser history, and Referer headers.
     */
    private async obtainTicket(): Promise<string> {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/v1/auth/ws-ticket`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json',
                },
            });
            if (!response.ok) {
                throw new Error(`Ticket exchange failed: ${response.status} ${response.statusText}`);
            }
            const data = await response.json() as { ticket: string };
            return data.ticket;
        } catch (error) {
            Logger.error('[AegionSocket] Ticket exchange failed, falling back to header auth:', error);
            throw error;
        }
    }

    public async connect() {
        if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
            return;
        }

        this.explicitClose = false;

        try {
            // Phase 89: Use ticket-exchange pattern — token never appears in URL
            const ticket = await this.obtainTicket();
            let finalUrl = `${this.url}?ticket=${ticket}`;
            if (this.lastSequenceId !== null) {
                finalUrl += `&last_event_id=${this.lastSequenceId}`;
            }

            Logger.info(`[AegionSocket] Connecting to ${this.url} (Last-Event-ID: ${this.lastSequenceId})`);
            const socket = new WebSocket(finalUrl);
            this.socket = socket;

            socket.onopen = () => {
                Logger.info('[AegionSocket] Connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.emit('open');
                this._flushBuffer();
            };

            socket.onmessage = (event: WebSocket.MessageEvent) => {
                try {
                    const data = JSON.parse(event.data.toString()) as WebSocketMessage;

                    // Update sequence ID if present
                    if (data.sequence_id !== undefined) {
                        if (this.lastSequenceId !== null && data.sequence_id > this.lastSequenceId + 1) {
                            Logger.warn(`[AegionSocket] Gap detected! Last: ${this.lastSequenceId}, Received: ${data.sequence_id}`);
                            // We could trigger a full sync here if gap is too large
                        }
                        this.lastSequenceId = data.sequence_id;
                    }

                    this.emit('message', data);
                } catch (e) {
                    Logger.error('[AegionSocket] Failed to parse message:', e);
                }
            };

            socket.onclose = (event: WebSocket.CloseEvent) => {
                Logger.info(`[AegionSocket] Disconnected (Code: ${event.code})`);
                this.isConnected = false;
                this.socket = null;
                this.emit('close', event.code, event.reason);

                if (!this.explicitClose) {
                    this._scheduleReconnect();
                }
            };

            socket.onerror = (error: WebSocket.ErrorEvent) => {
                Logger.error('[AegionSocket] Error:', error);
                this.emit('error', error);
            };

        } catch (e) {
            Logger.error('[AegionSocket] Connection failed:', e);
            if (!this.explicitClose) {
                this._scheduleReconnect();
            }
        }
    }

    public send(message: WebSocketMessage) {
        if (this.isConnected && this.socket?.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(message));
        } else {
            Logger.info(`[AegionSocket] Buffering message (Type: ${message.type})`);
            this.messageBuffer.push(message);
        }
    }

    public close() {
        this.explicitClose = true;
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.isConnected = false;
    }

    private _scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            Logger.error('[AegionSocket] Max reconnect attempts reached');
            this.emit('max_reconnects');
            return;
        }

        const delay = this.baseReconnectDelay * Math.pow(1.5, this.reconnectAttempts);
        this.reconnectAttempts++;

        Logger.info(`[AegionSocket] Reconnecting in ${delay}ms (Attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(), delay);
    }

    private _flushBuffer() {
        if (this.messageBuffer.length > 0) {
            Logger.info(`[AegionSocket] Flushing ${this.messageBuffer.length} buffered messages`);
            while (this.messageBuffer.length > 0) {
                const msg = this.messageBuffer.shift();
                if (msg) { this.send(msg); }
            }
        }
    }
}
