import { describe, expect, it } from 'vitest';
import { load } from './+page.server.js';

describe('year teams redirect', () => {
	it('sends the old teams grid URL to the ranking of that year', () => {
		let thrown = null;
		try {
			load({ params: { year: '2026' } });
		} catch (e) {
			thrown = e;
		}
		expect(thrown).toMatchObject({ status: 302, location: '/2026/ranking' });
	});
});
