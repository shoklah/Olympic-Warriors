import { describe, expect, it, vi } from 'vitest';
import { load } from './+page.server.js';
import { held } from '$lib/fixtures/held.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('disciplines load', () => {
	it('loads every discipline ever held', async () => {
		const fetch = vi.fn(async () => json(200, held));

		const data = await load({ fetch });

		expect(fetch.mock.calls[0][0]).toBe('http://api/disciplines/all-time/');
		expect(data.held).toEqual(held);
	});
});
