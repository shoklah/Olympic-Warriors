import { describe, expect, it, vi } from 'vitest';
import { load } from './+layout.server.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const editions = [{ id: 1, year: 2026, host: 'Paris', photos_url: null }];

// The whole /me/ payload (spec §5): the layout keeps only what the pages need.
const meBody = (overrides = {}) => ({
	id: 7,
	first_name: 'Léa',
	last_name: 'Martin',
	username: 'leamartin',
	is_staff: false,
	is_person: true,
	photo: { large: '/media/avatars/7-abc.webp', small: '/media/avatars/7-abc-sm.webp' },
	photo_locked: false,
	showcase: { auto: true, codes: [] },
	...overrides
});

const run = async ({ token, user }) => {
	const cookies = { get: (name) => (name === 'token' ? token : undefined), delete: vi.fn() };
	const fetch = vi.fn(async (url) => {
		if (url.endsWith('/editions/')) return json(200, editions);
		if (url.endsWith('/me/')) return user;
		throw new Error(`unexpected ${url}`);
	});
	const data = await load({ fetch, cookies });
	return { data, cookies, fetch };
};

const asked = (fetch, path) => fetch.mock.calls.some(([url]) => url.endsWith(path));

describe('root layout load', () => {
	it('is anonymous without a cookie and never asks who the user is', async () => {
		const { data, fetch } = await run({ token: undefined });
		expect(data.organiser).toBe(false);
		expect(data.me).toBeNull();
		expect(data.latestYear).toBe(2026);
		expect(asked(fetch, '/me/')).toBe(false);
	});

	it('asks /me/ with the token, never /user/current/', async () => {
		const { fetch } = await run({ token: 'abc', user: json(200, meBody()) });
		const call = fetch.mock.calls.find(([url]) => url.endsWith('/me/'));
		expect(call[1].headers).toEqual({ authorization: 'Token abc' });
		expect(asked(fetch, '/user/current/')).toBe(false);
	});

	it('is an organiser for a staff token, and keeps who they are', async () => {
		const { data } = await run({ token: 'abc', user: json(200, meBody({ is_staff: true })) });
		expect(data.organiser).toBe(true);
		expect(data.me).toEqual({
			id: 7,
			first_name: 'Léa',
			photo: { large: '/media/avatars/7-abc.webp', small: '/media/avatars/7-abc-sm.webp' },
			is_person: true
		});
	});

	it('keeps only the id, the first name, the photo and whether they are a person', async () => {
		const { data, cookies } = await run({ token: 'abc', user: json(200, meBody({ photo: null })) });
		expect(data.organiser).toBe(false);
		// Never the username, the last name, the lock or the pins: the layout data reaches the page.
		expect(data.me).toEqual({ id: 7, first_name: 'Léa', photo: null, is_person: true });
		expect(cookies.delete).not.toHaveBeenCalled();
	});

	it('knows a staff user who never played is not a person', async () => {
		const { data } = await run({
			token: 'abc',
			user: json(200, meBody({ is_staff: true, is_person: false, photo: null }))
		});
		expect(data.organiser).toBe(true);
		expect(data.me).toEqual({ id: 7, first_name: 'Léa', photo: null, is_person: false });
	});

	it.each([401, 403])('drops a dead token (%i)', async (status) => {
		const { data, cookies } = await run({ token: 'abc', user: json(status, { detail: 'Invalid token.' }) });
		expect(data.organiser).toBe(false);
		expect(data.me).toBeNull();
		expect(cookies.delete).toHaveBeenCalledWith('token', { path: '/' });
	});

	it('keeps the token when the API is down, and counts as a visitor', async () => {
		const { data, cookies } = await run({ token: 'abc', user: json(502, { error: 'x' }) });
		expect(data.organiser).toBe(false);
		expect(data.me).toBeNull();
		expect(cookies.delete).not.toHaveBeenCalled();
	});

	it('is a visitor for a non-JSON 200 and keeps the token', async () => {
		const { data, cookies } = await run({ token: 'abc', user: new Response('<html>', { status: 200 }) });
		expect(data.organiser).toBe(false);
		expect(data.me).toBeNull();
		expect(cookies.delete).not.toHaveBeenCalled();
	});
});
