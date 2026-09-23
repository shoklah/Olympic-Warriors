import { describe, expect, it, vi } from 'vitest';
import { load } from './+layout.server.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const run = async ({ year, organiser, latestYear, token }) => {
	const fetch = vi.fn(async () => json(200, { edition: { year: Number(year) } }));
	const cookies = { get: (name) => (name === 'token' ? token : undefined) };
	const parent = async () => ({ organiser, latestYear });
	const data = await load({ fetch, cookies, params: { year }, parent });
	return { data, fetch };
};

describe('year layout load', () => {
	it('is editable for an organiser on the latest year only', async () => {
		expect((await run({ year: '2026', organiser: true, latestYear: 2026, token: 'abc' })).data.editable).toBe(true);
		expect((await run({ year: '2024', organiser: true, latestYear: 2026, token: 'abc' })).data.editable).toBe(false);
		expect((await run({ year: '2026', organiser: false, latestYear: 2026 })).data.editable).toBe(false);
		expect((await run({ year: '2026', organiser: true, latestYear: null, token: 'abc' })).data.editable).toBe(
			false
		);
	});

	it('fetches the summary with the token for an organiser and without it otherwise', async () => {
		const staff = await run({ year: '2026', organiser: true, latestYear: 2026, token: 'abc' });
		expect(staff.fetch.mock.calls[0][1].headers).toEqual({ authorization: 'Token abc' });
		const anon = await run({ year: '2026', organiser: false, latestYear: 2026, token: 'abc' });
		expect(anon.fetch.mock.calls[0][1].headers).toEqual({});
		const noCookie = await run({ year: '2026', organiser: true, latestYear: 2026, token: undefined });
		expect(noCookie.fetch.mock.calls[0][1].headers).toEqual({});
	});
});
