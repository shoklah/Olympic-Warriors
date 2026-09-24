// @vitest-environment node
// The actions run on Node: under jsdom, a Blob in a FormData is jsdom's, which Node's
// Request cannot read back, so these tests use Node's own Blob, FormData and Request.
import { describe, expect, it, vi } from 'vitest';
import { actions, load } from './+page.server.js';
import { profile } from '$lib/fixtures/players.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('player profile load', () => {
	it('loads the profile of a numeric id', async () => {
		const fetch = vi.fn(async () => json(200, profile));

		const data = await load({ fetch, params: { id: '34' } });

		expect(fetch.mock.calls[0][0]).toBe('http://api/profile/34/');
		expect(data.profile).toEqual(profile);
	});

	it('answers 404 to anything but a canonical id without calling the API', async () => {
		const fetch = vi.fn();

		for (const id of ['abc', '../admin', '12a', '', '0055', '0', '123456789012']) {
			await expect(load({ fetch, params: { id } })).rejects.toMatchObject({ status: 404 });
		}
		expect(fetch).not.toHaveBeenCalled();
	});

	it("passes the API's 404 through", async () => {
		const fetch = vi.fn(async () => json(404, { error: 'Player not found' }));

		await expect(load({ fetch, params: { id: '999' } })).rejects.toMatchObject({ status: 404 });
	});
});

/** A POST to the profile page carrying `photo` (a Blob), or no field at all for null. */
const post = (photo) => {
	const body = new FormData();
	if (photo !== null) body.append('photo', photo, 'photo.jpg');
	return new Request('http://localhost/players/34?/photo', { method: 'POST', body });
};

const jpeg = () => new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xe0])], { type: 'image/jpeg' });

/**
 * Run `action` on /players/<id> with the token cookie, `/me/` answering the caller's id and
 * the photo endpoint answering `photoResponse`. "None" is `null`, never `undefined`, which
 * the defaults below would replace.
 */
const run = async (
	action,
	{ id = '34', token = 'abc', meId = 34, me = null, photo = jpeg(), photoResponse = json(200, {}) } = {}
) => {
	const fetch = vi.fn(async (url) => {
		if (url === 'http://api/me/') return me ?? json(200, { id: meId, first_name: 'Xavier', is_person: true });
		if (url === 'http://api/me/photo/') return typeof photoResponse === 'function' ? photoResponse() : photoResponse;
		throw new Error(`unexpected ${url}`);
	});
	const cookies = { get: (name) => (name === 'token' ? token : undefined) };
	const result = await actions[action]({ params: { id }, request: post(photo), fetch, cookies });
	const photoCall = fetch.mock.calls.find(([url]) => url === 'http://api/me/photo/');
	return { result, fetch, photoCall };
};

describe('photo action', () => {
	it("forwards the upload to PUT /me/photo/ as multipart, with the caller's token", async () => {
		const { result, fetch, photoCall } = await run('photo', {
			photoResponse: json(200, { photo: { large: '/media/avatars/34-a.webp', small: '/media/avatars/34-a-sm.webp' } })
		});

		expect(result).toEqual({ ok: true, action: 'photo' });
		expect(fetch.mock.calls[0][0]).toBe('http://api/me/');
		expect(fetch.mock.calls[0][1].headers).toEqual({ authorization: 'Token abc' });
		const [, options] = photoCall;
		expect(options.method).toBe('PUT');
		expect(options.headers).toEqual({ authorization: 'Token abc' });
		// No content type of its own: fetch writes the multipart boundary.
		const sent = options.body;
		expect(sent).toBeInstanceOf(FormData);
		const file = sent.get('photo');
		expect(file).toBeInstanceOf(Blob);
		expect(file.type).toBe('image/jpeg');
		expect(new Uint8Array(await file.arrayBuffer())).toEqual(new Uint8Array([0xff, 0xd8, 0xff, 0xe0]));
	});

	it('treats any 2xx as saved, an empty 204 included', async () => {
		const { result } = await run('photo', { photoResponse: new Response(null, { status: 204 }) });
		expect(result).toEqual({ ok: true, action: 'photo' });
	});

	it('refuses without a token cookie, calling no API', async () => {
		const { result, fetch } = await run('photo', { token: null });
		expect(result).toMatchObject({ status: 403, data: { action: 'photo', error: 'photo.error.forbidden' } });
		expect(fetch).not.toHaveBeenCalled();
	});

	it("refuses someone else's profile, checked against /me/, never uploading", async () => {
		const { result, fetch, photoCall } = await run('photo', { id: '12', meId: 34 });
		expect(result).toMatchObject({ status: 403, data: { action: 'photo', error: 'photo.error.forbidden' } });
		expect(fetch.mock.calls[0][0]).toBe('http://api/me/');
		expect(photoCall).toBeUndefined();
	});

	it('refuses an id that is not the canonical form of the caller\'s', async () => {
		for (const id of ['034', '34a', '']) {
			const { result, photoCall } = await run('photo', { id });
			expect(result).toMatchObject({ status: 403, data: { error: 'photo.error.forbidden' } });
			expect(photoCall).toBeUndefined();
		}
	});

	it('refuses when /me/ no longer knows the token', async () => {
		const { result, photoCall } = await run('photo', { me: json(401, { detail: 'Invalid token.' }) });
		expect(result).toMatchObject({ status: 403, data: { action: 'photo', error: 'photo.error.forbidden' } });
		expect(photoCall).toBeUndefined();
	});

	it('fails plainly when /me/ is down', async () => {
		const { result, photoCall } = await run('photo', { me: json(502, { error: 'x' }) });
		expect(result).toMatchObject({ status: 502, data: { action: 'photo', error: 'photo.error.failed' } });
		expect(photoCall).toBeUndefined();
	});

	it('refuses a form without a file, or with an empty one, before calling the API', async () => {
		for (const photo of [null, new Blob([], { type: 'image/jpeg' })]) {
			const { result, fetch } = await run('photo', { photo });
			expect(result).toMatchObject({ status: 400, data: { action: 'photo', error: 'photo.error.missing' } });
			expect(fetch).not.toHaveBeenCalled();
		}
	});

	it('refuses a text field named photo before calling the API', async () => {
		const body = new FormData();
		body.append('photo', 'not a file');
		const fetch = vi.fn();
		const cookies = { get: () => 'abc' };
		const request = new Request('http://localhost/players/34?/photo', { method: 'POST', body });
		const result = await actions.photo({ params: { id: '34' }, request, fetch, cookies });
		expect(result).toMatchObject({ status: 400, data: { error: 'photo.error.missing' } });
		expect(fetch).not.toHaveBeenCalled();
	});

	it.each([
		[400, 'missing'],
		[400, 'too_large'],
		[400, 'bad_format'],
		[400, 'too_many_pixels'],
		[403, 'photo_locked']
	])('maps the API refusal %i %s to its dictionary key', async (status, code) => {
		const { result } = await run('photo', { photoResponse: json(status, { error: code }) });
		expect(result).toMatchObject({ status, data: { action: 'photo', error: `photo.error.${code}` } });
	});

	it("maps nginx's 413, which has no JSON body, to too_large", async () => {
		const { result } = await run('photo', {
			photoResponse: new Response('<html><center>413 Request Entity Too Large</center></html>', {
				status: 413,
				headers: { 'content-type': 'text/html' }
			})
		});
		expect(result).toMatchObject({ status: 413, data: { action: 'photo', error: 'photo.error.too_large' } });
	});

	it('maps the throttle (429) to its own key', async () => {
		const { result } = await run('photo', {
			photoResponse: json(429, { detail: 'Request was throttled. Expected available in 3599 seconds.' })
		});
		expect(result).toMatchObject({ status: 429, data: { action: 'photo', error: 'photo.error.throttled' } });
	});

	it('maps an unknown code, a 404 (not a person) and a network failure to the generic key', async () => {
		let { result } = await run('photo', { photoResponse: json(400, { error: 'something_new' }) });
		expect(result).toMatchObject({ status: 400, data: { error: 'photo.error.failed' } });
		({ result } = await run('photo', { photoResponse: json(404, { detail: 'Not found.' }) }));
		expect(result).toMatchObject({ status: 404, data: { error: 'photo.error.failed' } });
		({ result } = await run('photo', {
			photoResponse: () => {
				throw new TypeError('fetch failed');
			}
		}));
		expect(result).toMatchObject({ status: 502, data: { error: 'photo.error.failed' } });
	});
});

describe('removePhoto action', () => {
	it('sends DELETE /me/photo/ with the token, an empty 204 being a success', async () => {
		const { result, photoCall } = await run('removePhoto', {
			photo: null,
			photoResponse: new Response(null, { status: 204 })
		});
		expect(result).toEqual({ ok: true, action: 'removePhoto' });
		expect(photoCall[1]).toEqual({ method: 'DELETE', headers: { authorization: 'Token abc' } });
	});

	it("refuses without a token or on someone else's profile", async () => {
		let { result, fetch } = await run('removePhoto', { token: null, photo: null });
		expect(result).toMatchObject({ status: 403, data: { action: 'removePhoto', error: 'photo.error.forbidden' } });
		expect(fetch).not.toHaveBeenCalled();
		let photoCall;
		({ result, photoCall } = await run('removePhoto', { id: '12', photo: null }));
		expect(result).toMatchObject({ status: 403, data: { action: 'removePhoto', error: 'photo.error.forbidden' } });
		expect(photoCall).toBeUndefined();
	});

	it('maps a failure to its dictionary key', async () => {
		const { result } = await run('removePhoto', { photo: null, photoResponse: json(500, { error: 'x' }) });
		expect(result).toMatchObject({ status: 500, data: { action: 'removePhoto', error: 'photo.error.failed' } });
	});
});
