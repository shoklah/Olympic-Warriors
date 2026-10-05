// @vitest-environment node
import { describe, expect, it, vi } from 'vitest';
import { load } from './+page.server.js';

const event = (over = {}) => ({
	params: { year: '2029' },
	cookies: { get: () => 'tok' },
	setHeaders: vi.fn(),
	parent: async () => ({ organiser: true, latestYear: 2029 }),
	...over
});

describe('announce load', () => {
	it('sends a visitor to the login and refuses a player', async () => {
		await expect(load(event({ cookies: { get: () => undefined }, parent: async () => ({ organiser: false, latestYear: 2029 }) }))).rejects.toMatchObject({ status: 303, location: '/login?next=/2029/announce' });
		await expect(load(event({ parent: async () => ({ organiser: false, latestYear: 2029 }) }))).rejects.toMatchObject({ status: 403 });
	});

	it('is 404 for a year that is not the latest', async () => {
		await expect(load(event({ params: { year: '2028' } }))).rejects.toMatchObject({ status: 404 });
	});

	it('lets an organiser in and never caches the page', async () => {
		const e = event();

		await load(e);

		expect(e.setHeaders).toHaveBeenCalledWith({ 'cache-control': 'private, no-store' });
	});
});
