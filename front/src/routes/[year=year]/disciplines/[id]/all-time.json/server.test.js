import { describe, expect, it, vi } from 'vitest';
import { GET } from './+server.js';
import { allTime } from '$lib/fixtures/players.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('discipline all-time endpoint', () => {
	it("serves the API's table for the discipline", async () => {
		const fetch = vi.fn(async () => json(200, allTime));

		const response = await GET({ fetch, params: { year: '2026', id: '10' } });

		expect(fetch.mock.calls[0][0]).toBe('http://api/discipline/10/all-time/');
		expect(await response.json()).toEqual(allTime);
	});

	it('answers 404 to anything but a canonical id without calling the API', async () => {
		const fetch = vi.fn();

		for (const id of ['abc', '../admin', '12a', '', '010', '0', '123456789012']) {
			await expect(GET({ fetch, params: { year: '2026', id } })).rejects.toMatchObject({ status: 404 });
		}
		expect(fetch).not.toHaveBeenCalled();
	});

	it("passes the API's errors through", async () => {
		const fetch = vi.fn(async () => json(404, { error: 'Discipline not found' }));

		await expect(GET({ fetch, params: { year: '2026', id: '999' } })).rejects.toMatchObject({ status: 404 });
	});
});
