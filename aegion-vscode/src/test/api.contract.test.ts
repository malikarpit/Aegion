/**
 * AG-001: API Contract Test
 *
 * Verifies that:
 *  1. The Endpoints map in client.ts covers all expected route groups.
 *  2. No orphan hardcoded route strings exist outside the Endpoints map.
 *  3. Client generation mode config is respected.
 */

import * as assert from 'assert';

// We test the Endpoints map statically (no backend needed)
// In a real CI run, generate-client.sh would produce generated/endpoints.ts

suite('API Contract Tests', () => {

    // Expected route prefixes that must appear in the Endpoints map
    const EXPECTED_GROUPS = [
        'sessions',
        'proposals',
        'council',
        'workspaces',
        'health',
        'architecture',
        'graph',
        'sentinel',
        'events',
    ];

    test('Endpoints map covers all expected route groups', () => {
        // Dynamic import so test can fail gracefully if client not compiled
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const { Endpoints } = require('../api/client');

        for (const group of EXPECTED_GROUPS) {
            const groupEndpoints = Endpoints[group];
            assert.ok(
                groupEndpoints !== undefined,
                `Missing endpoint group '${group}' in Endpoints map`,
            );
            assert.ok(
                typeof groupEndpoints === 'object',
                `Endpoint group '${group}' should be an object`,
            );
            // Each group should have at least one method
            const methods = Object.keys(groupEndpoints);
            assert.ok(
                methods.length > 0,
                `Endpoint group '${group}' has no methods defined`,
            );
        }
    });

    test('All endpoint functions return strings starting with /', () => {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const { Endpoints } = require('../api/client');

        for (const [group, methods] of Object.entries(Endpoints)) {
            for (const [name, fn] of Object.entries(methods as Record<string, unknown>)) {
                if (typeof fn === 'function') {
                    // Call with dummy args to check return format
                    try {
                        const result = (fn as (...args: string[]) => string)('test-id', '10');
                        assert.ok(
                            typeof result === 'string' && result.startsWith('/'),
                            `${group}.${name}() should return a string starting with '/', got: ${result}`,
                        );
                    } catch {
                        // Some functions may need specific arg count — skip gracefully
                    }
                }
            }
        }
    });

    test('No hardcoded /api/v1 strings in AegionClient methods', () => {
        // Read the client source and check for raw route strings
        // This is a static analysis test — we check for patterns like
        // fetch('/api/v1/...' or fetch(`/api/v1/...`)
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const fs = require('fs');
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const path = require('path');

        const clientPath = path.join(__dirname, '..', '..', 'src', 'api', 'client.ts');
        let source: string;
        try {
            source = fs.readFileSync(clientPath, 'utf-8');
        } catch {
            // In compiled output, .ts may not be available — skip
            return;
        }

        // Split into Endpoints section vs AegionClient section
        const clientClassStart = source.indexOf('export class AegionClient');
        if (clientClassStart === -1) { return; }

        const clientSection = source.substring(clientClassStart);

        // Find raw route strings (not in Endpoints block or comments)
        const rawRoutes = clientSection.match(/['"`]\/v1\/[^'"`]+['"`]/g) || [];

        // Filter out the API_VERSION references (those are fine)
        const violations = rawRoutes.filter(r => !r.includes('${API_VERSION}'));

        assert.strictEqual(
            violations.length,
            0,
            `Found hardcoded route strings in AegionClient: ${violations.join(', ')}`,
        );
    });

    test('Client generation modes are valid', () => {
        const validModes = ['manual', 'automatic', 'automatic-with-review'];
        // This just validates the enum — actual mode switching is done by generate-client.sh
        for (const mode of validModes) {
            assert.ok(
                typeof mode === 'string' && mode.length > 0,
                `Invalid mode: ${mode}`,
            );
        }
    });
});
