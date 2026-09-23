import { describe, expect, it, vi } from 'vitest';
import { load } from './+layout.server.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const editions = [{ id: 1, year: 2026, host: 'Paris', photos_url: null }];

const run = async ({ token, user }) => {
	const cookies = { get: (name) => (name === 'token' ? token : undefined), delete: vi.fn() };
	const fetch = vi.fn(async (url) => {
		if (url.endsWith('/editions/')) return json(200, editions);
		if (url.endsWith('/user/current/')) return user;
		throw new Error(`unexpected ${url}`);
	});
	const data = await load({ fetch, cookies });
	return { data, cookies, fetch };
};

describe('root layout load', () => {
	it('is anonymous without a cookie and never asks who the user is', async () => {
		const { data, fetch } = await run({ token: undefined });
		expect(data.organiser).toBe(false);
		expect(data.latestYear).toBe(2026);
		expect(fetch.mock.calls.some(([url]) => url.endsWith('/user/current/'))).toBe(false);
	});

	it('is an organiser for a staff token', async () => {
		const { data, fetch } = await run({ token: 'abc', user: json(200, { is_staff: true }) });
		expect(data.organiser).toBe(true);
		const call = fetch.mock.calls.find(([url]) => url.endsWith('/user/current/'));
		expect(call[1].headers).toEqual({ authorization: 'Token abc' });
	});

	it('is not an organiser for a player token', async () => {
		const { data, cookies } = await run({ token: 'abc', user: json(200, { is_staff: false }) });
		expect(data.organiser).toBe(false);
		expect(cookies.delete).not.toHaveBeenCalled();
	});

	it('drops a dead token', async () => {
		const { data, cookies } = await run({ token: 'abc', user: json(401, { detail: 'Invalid token.' }) });
		expect(data.organiser).toBe(false);
		expect(cookies.delete).toHaveBeenCalledWith('token', { path: '/' });
	});

	it('keeps the token when the API is down', async () => {
		const { data, cookies } = await run({ token: 'abc', user: json(502, { error: 'x' }) });
		expect(data.organiser).toBe(false);
		expect(cookies.delete).not.toHaveBeenCalled();
	});

	it('is not an organiser for a non-JSON 200 and keeps the token', async () => {
		const { data, cookies } = await run({ token: 'abc', user: new Response('<html>', { status: 200 }) });
		expect(data.organiser).toBe(false);
		expect(cookies.delete).not.toHaveBeenCalled();
	});
});
