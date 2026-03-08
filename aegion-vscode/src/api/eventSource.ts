/**
 * Aegion EventSource Client.
 *
 * SSE client for real-time workspace events.
 * Uses eventsource-polyfill for Node.js environments (VS Code extension host).
 *
 * Doctrine: "State flows from source of truth."
 */



// Use polyfill for Node.js environment (VS Code extension host)
// This provides EventSource with proper header support
import { Logger } from '../services/Logger';

let EventSourcePolyfill: typeof EventSource;
try {
    // Dynamic import for environments where native EventSource isn't available
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    EventSourcePolyfill = require('eventsource-polyfill').EventSource;
} catch {
    // Fallback to native if available (browser context)
    EventSourcePolyfill = globalThis.EventSource;
}

export interface WorkspaceEvent {
    type: string;
    event_id: string;
    payload: Record<string, unknown>;
    timestamp: string;
}

export type EventHandler = (event: WorkspaceEvent) => void;

export type SSEMode = 'polyfill' | 'fetch';

export class EventSourceClient {
    private eventSource: EventSource | null = null;
    private handlers: Map<string, EventHandler[]> = new Map();
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 1000;
    private workspaceId: string | null = null;
    private connected = false;
    private authToken: string | null = null;
    private sseMode: SSEMode;

    constructor(private baseUrl: string, mode: SSEMode = 'fetch') {
        this.sseMode = mode;
    }

    /**
     * Connect to workspace event stream.
     * Uses polyfill mode for native SSE with headers, or fetch fallback.
     */
    async connect(workspaceId: string, authToken: string): Promise<void> {
        this.workspaceId = workspaceId;
        this.authToken = authToken;

        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const { Endpoints } = require('./client');
        const url = `${this.baseUrl}${Endpoints.events.subscribe(workspaceId)}`;

        try {
            if (this.sseMode === 'polyfill' && EventSourcePolyfill) {
                // Use EventSource polyfill with header support
                this.eventSource = new EventSourcePolyfill(url, {
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                    },
                } as EventSourceInit);

                this.eventSource.onmessage = (event: MessageEvent) => {
                    try {
                        const data = JSON.parse(event.data) as WorkspaceEvent;
                        this.dispatchEvent(data);
                    } catch (e) {
                        Logger.error('Failed to parse SSE message:', e);
                    }
                };

                this.eventSource.onerror = () => {
                    Logger.error('EventSource connection error');
                    this.handleReconnect();
                };

                this.connected = true;
                this.reconnectAttempts = 0;
            } else {
                // Fallback: Use fetch with streaming
                const response = await fetch(url, {
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                        'Accept': 'text/event-stream',
                    },
                });

                if (!response.ok) {
                    throw new Error(`Failed to connect: ${response.status}`);
                }

                if (!response.body) {
                    throw new Error('No response body');
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                this.connected = true;
                this.reconnectAttempts = 0;

                // Process stream
                this.processStream(reader, decoder);
            }
        } catch (error) {
            Logger.error('EventSource connection failed:', error);
            this.handleReconnect();
        }
    }

    private async processStream(
        reader: ReadableStreamDefaultReader<Uint8Array>,
        decoder: { decode(input?: Uint8Array, options?: { stream?: boolean }): string },
    ): Promise<void> {
        let buffer = '';

        while (this.connected) {
            try {
                const { done, value } = await reader.read();

                if (done) {
                    Logger.info('Stream closed');
                    this.handleReconnect();
                    break;
                }

                buffer += decoder.decode(value, { stream: true });

                // Process complete messages
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || ''; // Keep incomplete message

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        try {
                            const event = JSON.parse(data) as WorkspaceEvent;
                            this.dispatchEvent(event);
                        } catch (e) {
                            Logger.error('Failed to parse event:', e);
                        }
                    }
                }
            } catch (error) {
                Logger.error('Stream read error:', error);
                this.handleReconnect();
                break;
            }
        }
    }

    private dispatchEvent(event: WorkspaceEvent): void {
        // Dispatch to type-specific handlers
        const typeHandlers = this.handlers.get(event.type) || [];
        for (const handler of typeHandlers) {
            try {
                handler(event);
            } catch (e) {
                Logger.error(`Handler error for ${event.type}:`, e);
            }
        }

        // Dispatch to wildcard handlers
        const wildcardHandlers = this.handlers.get('*') || [];
        for (const handler of wildcardHandlers) {
            try {
                handler(event);
            } catch (e) {
                Logger.error('Wildcard handler error:', e);
            }
        }
    }

    private handleReconnect(): void {
        if (!this.connected || !this.workspaceId) {
            return;
        }

        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            Logger.error('Max reconnect attempts reached');
            this.connected = false;
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        Logger.info(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => {
            if (this.workspaceId) {
                // Note: Would need to pass token again
                Logger.info('Reconnect logic would trigger here');
            }
        }, delay);
    }

    /**
     * Register handler for specific event type.
     */
    on(eventType: string, handler: EventHandler): void {
        const handlers = this.handlers.get(eventType);
        if (handlers) {
            handlers.push(handler);
        } else {
            this.handlers.set(eventType, [handler]);
        }
    }

    /**
     * Register handler for all events.
     */
    onAny(handler: EventHandler): void {
        this.on('*', handler);
    }

    // Convenience methods for common event types
    onProposalCreated(handler: EventHandler): void {
        this.on('proposal.created', handler);
    }

    onProposalReviewSubmitted(handler: EventHandler): void {
        this.on('proposal.review_submitted', handler);
    }

    onProposalApproved(handler: EventHandler): void {
        this.on('proposal.approved', handler);
    }

    onMemberJoined(handler: EventHandler): void {
        this.on('member.joined', handler);
    }

    onMemberLeft(handler: EventHandler): void {
        this.on('member.left', handler);
    }

    onDecisionCreated(handler: EventHandler): void {
        this.on('decision.created', handler);
    }

    /**
     * Disconnect from event stream.
     */
    disconnect(): void {
        this.connected = false;
        this.workspaceId = null;
        this.handlers.clear();
    }

    /**
     * Check if connected.
     */
    isConnected(): boolean {
        return this.connected;
    }
}
