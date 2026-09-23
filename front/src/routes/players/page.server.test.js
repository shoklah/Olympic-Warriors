import { describe, expect, it, vi } from 'vitest';
import { load } from './+page.server.js';
import { leaderboard } from '$lib/fixtures/players.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('players leaderboard load', () => {
	it('loads the leaderboard as the API orders it', async () => {
		const fetch = vi.fn(async () => json(200, leaderboard));

		const data = await load({ fetch });

		expect(fetch.mock.calls[0][0]).toBe('http://api/profiles/');
		expect(data.players).toEqual(leaderboard);
	});
});
