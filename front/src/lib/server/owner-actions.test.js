// @vitest-environment node
// Node's own Request, FormData and Blob, as in the profile's server test.
import { describe, expect, it, vi } from 'vitest';
import { ownerActions } from './owner-actions.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const cookies = { get: () => 't' };

function event(action, fetch) {
	const form = new FormData();
	if (action === 'photo') form.set('photo', new Blob(['x'], { type: 'image/jpeg' }), 'p.jpg');
	if (action === 'showcase') form.append('codes', 'champion');
	return { request: new Request('http://x/p', { method: 'POST', body: form }), fetch, cookies, params: {} };
}

const forbidden = { photo: 'photo.error.forbidden', removePhoto: 'photo.error.forbidden', showcase: 'showcase.error.forbidden' };

describe.each(['photo', 'removePhoto', 'showcase'])('owner action %s', (name) => {
	it('with a null expected id only requires /me/ to answer, and writes', async () => {
		const fetch = vi.fn(async (url) => (String(url).endsWith('/me/') ? json(200, { id: 7 }) : json(200, {})));
		const result = await ownerActions(() => null)[name](event(name, fetch));
		expect(result).toEqual({ ok: true, action: name });
		expect(fetch).toHaveBeenCalledTimes(2);
	});

	it('refuses with a 403 when /me/ answers 401', async () => {
		const fetch = vi.fn(async () => json(401, { detail: 'no' }));
		const result = await ownerActions(() => null)[name](event(name, fetch));
		expect(result.status).toBe(403);
		expect(result.data).toEqual({ action: name, error: forbidden[name] });
		expect(fetch).toHaveBeenCalledTimes(1);
	});

	it('refuses with a 403 when /me/ carries no integer id', async () => {
		const fetch = vi.fn(async () => json(200, { id: 'x' }));
		const result = await ownerActions(() => null)[name](event(name, fetch));
		expect(result.status).toBe(403);
		expect(result.data.error).toBe(forbidden[name]);
		expect(fetch).toHaveBeenCalledTimes(1);
	});

	it('refuses a mismatching id without calling the write endpoint', async () => {
		const fetch = vi.fn(async () => json(200, { id: 7 }));
		const result = await ownerActions(() => '8')[name](event(name, fetch));
		expect(result.status).toBe(403);
		expect(result.data.error).toBe(forbidden[name]);
		expect(fetch).toHaveBeenCalledTimes(1);
	});
});
