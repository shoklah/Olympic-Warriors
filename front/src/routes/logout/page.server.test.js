import { describe, expect, it, vi } from 'vitest';
import { actions, load } from './+page.server.js';

const post = (fields) => {
	const body = new FormData();
	for (const [name, value] of Object.entries(fields)) body.append(name, value);
	return new Request('http://localhost/logout', { method: 'POST', body });
};

describe('logout action', () => {
	it('deletes the token cookie and goes back where the form was', async () => {
		const cookies = { delete: vi.fn() };
		await expect(
			actions.default({ cookies, request: post({ redirectTo: '/2026/disciplines/10' }) })
		).rejects.toMatchObject({ status: 303, location: '/2026/disciplines/10' });
		expect(cookies.delete).toHaveBeenCalledWith('token', { path: '/' });
	});

	it('refuses a non-local redirect', async () => {
		const cookies = { delete: vi.fn() };
		await expect(
			actions.default({ cookies, request: post({ redirectTo: '//evil.example' }) })
		).rejects.toMatchObject({ location: '/' });
	});
});

describe('logout load', () => {
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
