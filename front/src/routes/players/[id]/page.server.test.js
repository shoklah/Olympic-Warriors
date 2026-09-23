import { describe, expect, it, vi } from 'vitest';
import { load } from './+page.server.js';
import { profile } from '$lib/fixtures/players.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('player profile load', () => {
	it('loads the profile of a numeric id', async () => {
		const fetch = vi.fn(async () => json(200, profile));

		const data = await load({ fetch, params: { id: '34' } });

		expect(fetch.mock.calls[0][0]).toBe('http://api/profile/34/');
		expect(data.profile).toEqual(profile);
	});

	it('answers 404 to anything but digits without calling the API', async () => {
		const fetch = vi.fn();

		for (const id of ['abc', '../admin', '12a', '']) {
			await expect(load({ fetch, params: { id } })).rejects.toMatchObject({ status: 404 });
		}
		expect(fetch).not.toHaveBeenCalled();
	});

	it("passes the API's 404 through", async () => {
		const fetch = vi.fn(async () => json(404, { error: 'Player not found' }));

		await expect(load({ fetch, params: { id: '999' } })).rejects.toMatchObject({ status: 404 });
	});
});
