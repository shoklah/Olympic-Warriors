import { describe, expect, it, vi } from 'vitest';
import { actions, load } from './+page.server.js';

const post = (fields) => {
	const body = new FormData();
	for (const [name, value] of Object.entries(fields)) body.append(name, value);
	return new Request('http://localhost/lang', { method: 'POST', body });
};

const call = (fields) => {
	const cookies = { set: vi.fn() };
	return { cookies, promise: actions.default({ cookies, request: post(fields) }) };
};

describe('lang action', () => {
	it('sets the cookie for a year and goes back where the form was', async () => {
		const { cookies, promise } = call({ lang: 'en', redirectTo: '/2026/ranking' });

		await expect(promise).rejects.toMatchObject({ status: 303, location: '/2026/ranking' });
		expect(cookies.set).toHaveBeenCalledWith('lang', 'en', {
			path: '/',
			maxAge: 60 * 60 * 24 * 365,
			sameSite: 'lax',
			httpOnly: false
		});
	});

	it('stores French for an unknown language', async () => {
		const { cookies, promise } = call({ lang: 'de', redirectTo: '/' });

		await expect(promise).rejects.toMatchObject({ status: 303, location: '/' });
		expect(cookies.set.mock.calls[0][1]).toBe('fr');
	});

	it('refuses a non-local redirect', async () => {
		await expect(call({ lang: 'en', redirectTo: '//evil.example' }).promise).rejects.toMatchObject({
			location: '/'
		});
		await expect(call({ lang: 'en', redirectTo: 'https://evil.example/' }).promise).rejects.toMatchObject({
			location: '/'
		});
		await expect(call({ lang: 'en' }).promise).rejects.toMatchObject({ location: '/' });
	});
});

describe('lang load', () => {
	it('sends a GET to the hub', () => {
		let thrown = null;
		try {
			load();
		} catch (e) {
			thrown = e;
		}
		expect(thrown).toMatchObject({ status: 303, location: '/' });
	});
});
