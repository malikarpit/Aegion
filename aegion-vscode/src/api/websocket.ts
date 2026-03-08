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
    private socket: WebSocket | null = null;
    private isConnected: boolean = false;
    private reconnectAttempts: number = 0;
    private maxReconnectAttempts: number = 10;
    private baseReconnectDelay: number = 1000;
    private lastSequenceId: number | null = null;
    private messageBuffer: WebSocketMessage[] = [];
    private explicitClose: boolean = false;

    constructor(url: string, token: string) {
        super();
        this.url = url;
        this.token = token;
    }

    public connect() {
        if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
            return;
        }

        this.explicitClose = false;
        let finalUrl = `${this.url}?token=${this.token}`;
        if (this.lastSequenceId !== null) {
            finalUrl += `&last_event_id=${this.lastSequenceId}`;
        }

        try {
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
