// @vitest-environment node
import { describe, expect, it, vi } from 'vitest';
import { load } from './+page.server.js';
import { builderPayload } from '$lib/fixtures/builder.js';

vi.mock('$lib/server/urls', () => ({ api: (p) => `http://api${p}` }));

const event = (over = {}) => ({
	params: { year: '2029' },
	cookies: { get: () => 'tok' },
	setHeaders: vi.fn(),
	fetch: vi.fn(async () => new Response(JSON.stringify(builderPayload), { headers: { 'content-type': 'application/json' } })),
	parent: async () => ({ organiser: true, latestYear: 2029 }),
	url: new URL('http://site/2029/builder'),
	...over
});

describe('builder load', () => {
	it('sends a visitor to the login, a player home with a 403', async () => {
		await expect(load(event({ cookies: { get: () => undefined }, parent: async () => ({ organiser: false, latestYear: 2029 }) }))).rejects.toMatchObject({ status: 303, location: '/login?next=/2029/builder' });
		await expect(load(event({ parent: async () => ({ organiser: false, latestYear: 2029 }) }))).rejects.toMatchObject({ status: 403 });
	});

	it('is 404 for a year that is not the latest', async () => {
		await expect(load(event({ params: { year: '2028' } }))).rejects.toMatchObject({ status: 404 });
	});

	it('loads the payload with the token and never caches it', async () => {
		const e = event();

		const data = await load(e);

		expect(data.builder).toEqual(builderPayload);
		expect(e.fetch.mock.calls[0][0]).toBe('http://api/builder/2029/');
		expect(e.fetch.mock.calls[0][1].headers.authorization).toBe('Token tok');
		expect(e.setHeaders).toHaveBeenCalledWith({ 'cache-control': 'private, no-store' });
	});
});
