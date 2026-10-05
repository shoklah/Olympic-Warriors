// @vitest-environment node
import { describe, expect, it, vi } from 'vitest';
import { PUT, DELETE } from './draft/+server.js';
import { POST } from './apply/+server.js';

vi.mock('$lib/server/urls', () => ({ api: (p) => `http://api${p}` }));

const call = (handler, over = {}) =>
	handler({
		params: { year: '2029' },
		cookies: { get: () => 'tok' },
		request: new Request('http://site/x', { method: 'PUT', body: JSON.stringify({ document: { a: 1 }, based_on: null }), headers: { 'content-type': 'application/json' } }),
		fetch: vi.fn(async () => new Response(JSON.stringify({ updated_at: 'v1' }), { status: 200, headers: { 'content-type': 'application/json' } })),
		...over
	});

describe('builder endpoints', () => {
	it('forward the draft with the token and pass status and body through', async () => {
		const fetch = vi.fn(async () => new Response(JSON.stringify({ error: 'stale_draft', draft: null }), { status: 409, headers: { 'content-type': 'application/json' } }));

		const response = await call(PUT, { fetch });

		expect(fetch.mock.calls[0][0]).toBe('http://api/builder/2029/draft/');
		expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'PUT' });
		expect(fetch.mock.calls[0][1].headers.authorization).toBe('Token tok');
		expect(response.status).toBe(409);
		expect(await response.json()).toEqual({ error: 'stale_draft', draft: null });
	});

	it('refuse without a token', async () => {
		expect((await call(PUT, { cookies: { get: () => undefined } })).status).toBe(401);
		expect((await call(POST, { cookies: { get: () => undefined } })).status).toBe(401);
	});

	it('delete and apply go to their API routes, apply with its body', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 204 }));

		await call(DELETE, { fetch });
		await call(POST, { fetch });

		expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ document: { a: 1 }, based_on: null });
		expect(fetch.mock.calls.map((c) => [c[0], c[1].method])).toEqual([
			['http://api/builder/2029/draft/', 'DELETE'],
			['http://api/builder/2029/apply/', 'POST']
		]);
	});

	it('refuse a year that is not four digits', async () => {
		expect((await call(PUT, { params: { year: 'abc' } })).status).toBe(404);
	});
});
