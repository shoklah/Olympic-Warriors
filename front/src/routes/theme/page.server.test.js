import { describe, expect, it, vi } from 'vitest';
import { actions, load } from './+page.server.js';

const post = (fields) => {
	const body = new FormData();
	for (const [name, value] of Object.entries(fields)) body.append(name, value);
	return new Request('http://localhost/theme', { method: 'POST', body });
};

const call = (fields) => {
	const cookies = { set: vi.fn(), delete: vi.fn() };
	return { cookies, promise: actions.default({ cookies, request: post(fields) }) };
};

describe('theme action', () => {
	it('stores the choice for a year and goes back where the form was', async () => {
		const { cookies, promise } = call({ theme: 'light', redirectTo: '/2026/ranking' });

		await expect(promise).rejects.toMatchObject({ status: 303, location: '/2026/ranking' });
		expect(cookies.set).toHaveBeenCalledWith('theme', 'light', {
			path: '/',
			maxAge: 60 * 60 * 24 * 365,
			sameSite: 'lax',
			httpOnly: false
		});
		expect(cookies.delete).not.toHaveBeenCalled();
	});

	it('stores dark too', async () => {
		const { cookies, promise } = call({ theme: 'dark', redirectTo: '/' });

		await expect(promise).rejects.toMatchObject({ status: 303, location: '/' });
		expect(cookies.set.mock.calls[0][1]).toBe('dark');
	});

	it('hands an unknown or missing theme back to the device', async () => {
		for (const fields of [{ theme: 'system' }, { theme: 'sepia' }, {}]) {
			const { cookies, promise } = call({ ...fields, redirectTo: '/players' });

			await expect(promise).rejects.toMatchObject({ status: 303, location: '/players' });
			expect(cookies.set).not.toHaveBeenCalled();
			expect(cookies.delete).toHaveBeenCalledWith('theme', { path: '/' });
		}
	});

	it('refuses a non-local redirect', async () => {
		await expect(call({ theme: 'light', redirectTo: '//evil.example' }).promise).rejects.toMatchObject({
			location: '/'
		});
		await expect(call({ theme: 'light', redirectTo: 'https://evil.example/' }).promise).rejects.toMatchObject({
			location: '/'
		});
		await expect(call({ theme: 'light' }).promise).rejects.toMatchObject({ location: '/' });
	});
});

describe('theme load', () => {
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
