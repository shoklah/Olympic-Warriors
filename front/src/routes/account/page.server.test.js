// @vitest-environment node
// The actions read a real Request's form body, so these tests use Node's own FormData and Request.
import { describe, expect, it, vi } from 'vitest';
import { actions, load } from './+page.server.js';
import { profile } from '$lib/fixtures/players.js';
import { tokenCookieOptions } from '$lib/session';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const me = { id: 34, first_name: 'Xavier', username: 'xavierbaby', email: 'x@mail.example', is_staff: false, is_person: true };

const cookiesWith = (token = 't') => ({
	get: (name) => (name === 'token' ? token : undefined),
	set: vi.fn(),
	delete: vi.fn()
});

/** A POST of `fields` to the account page's `action`. */
const post = (action, fields) => {
	const form = new FormData();
	for (const [name, value] of Object.entries(fields)) form.set(name, value);
	return new Request(`http://x/account?/${action}`, { method: 'POST', body: form });
};

describe('account load', () => {
	it('sends a visitor to /login with a 303', async () => {
		const fetch = vi.fn();
		await expect(load({ fetch, cookies: cookiesWith(null), setHeaders: vi.fn() })).rejects.toMatchObject({
			status: 303,
			location: '/login?next=/account'
		});
		expect(fetch).not.toHaveBeenCalled();
	});

	it("returns the account from /me/ and the person's profile, never cached", async () => {
		const fetch = vi.fn(async (url) => (url === 'http://api/me/' ? json(200, me) : json(200, profile)));
		const setHeaders = vi.fn();

		const data = await load({ fetch, cookies: cookiesWith(), setHeaders });

		expect(fetch.mock.calls[0][0]).toBe('http://api/me/');
		expect(fetch.mock.calls[0][1].headers).toEqual({ authorization: 'Token t' });
		expect(fetch.mock.calls[1][0]).toBe('http://api/profile/34/');
		expect(data).toEqual({
			account: { id: 34, username: 'xavierbaby', email: 'x@mail.example', is_staff: false, is_person: true },
			profile
		});
		expect(setHeaders).toHaveBeenCalledWith({ 'cache-control': 'private, no-store' });
	});

	it('gives an empty email when the account has none', async () => {
		const fetch = vi.fn(async (url) =>
			url === 'http://api/me/' ? json(200, { ...me, email: null }) : json(200, profile)
		);
		const data = await load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() });
		expect(data.account.email).toBe('');
	});

	const invitee = { ...me, is_person: false, can_register: true };
	const registrationBody = { edition: { year: 2027 }, state: { is_open: true, reason: '' }, registration: null };

	it('serves an invited newcomer without asking for a profile they do not have', async () => {
		const fetch = vi.fn(async (url) => {
			if (url === 'http://api/me/') return json(200, invitee);
			if (url === 'http://api/registration/') return json(200, registrationBody);
			throw new Error(`unexpected ${url}`);
		});

		const data = await load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() });

		expect(data.profile).toBeNull();
		expect(data.account).toMatchObject({ id: 34, is_person: false });
		expect(fetch.mock.calls.some(([url]) => url.includes('/profile/'))).toBe(false);
	});

	it('still sends someone who cannot register home', async () => {
		const fetch = vi.fn(async () => json(200, { ...me, is_person: false, can_register: false }));

		await expect(load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() })).rejects.toMatchObject({
			status: 303, location: '/'
		});
	});

	it('sends a dead token to /login too', async () => {
		const fetch = vi.fn(async () => json(401, { detail: 'Invalid token.' }));
		await expect(load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() })).rejects.toMatchObject({
			status: 303,
			location: '/login?next=/account'
		});
	});

	it('serves an organiser who plays, flagged as staff', async () => {
		const fetch = vi.fn(async (url) =>
			url === 'http://api/me/' ? json(200, { ...me, is_staff: true }) : json(200, profile)
		);
		const data = await load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() });
		expect(data.account).toEqual({
			id: 34,
			username: 'xavierbaby',
			email: 'x@mail.example',
			is_staff: true,
			is_person: true
		});
		expect(data.profile).toEqual(profile);
	});

	it('sends an organiser who never played home with a 303: they have nothing to edit here', async () => {
		const fetch = vi.fn(async () => json(200, { ...me, is_staff: true, is_person: false }));
		await expect(load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() })).rejects.toMatchObject({
			status: 303,
			location: '/'
		});
		expect(fetch).toHaveBeenCalledTimes(1);
	});

	it('sends someone who is not a person home with a 303 too', async () => {
		const fetch = vi.fn(async () => json(200, { ...me, is_person: false }));
		await expect(load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() })).rejects.toMatchObject({
			status: 303,
			location: '/'
		});
		expect(fetch).toHaveBeenCalledTimes(1);
	});
});

describe('email action', () => {
	it('sends the password and the address, and returns ok', async () => {
		const fetch = vi.fn(async () => json(200, { email: 'a@b.co' }));
		const result = await actions.email({
			request: post('email', { password: 'pw', email: ' a@b.co ' }),
			fetch,
			cookies: cookiesWith()
		});

		expect(fetch).toHaveBeenCalledTimes(1);
		const [url, options] = fetch.mock.calls[0];
		expect(url).toBe('http://api/me/email/');
		expect(options.method).toBe('PUT');
		expect(options.headers).toEqual({ 'content-type': 'application/json', authorization: 'Token t' });
		expect(JSON.parse(options.body)).toEqual({ password: 'pw', email: 'a@b.co' });
		expect(result).toEqual({ ok: true, action: 'email' });
	});

	it('maps the API codes and the throttle to dictionary keys', async () => {
		const cases = [
			[json(400, { error: 'wrong_password' }), 400, 'account.error.wrong_password'],
			[json(400, { error: 'invalid_email' }), 400, 'account.error.invalid_email'],
			[json(429, { detail: 'Request was throttled.' }), 429, 'account.error.throttled'],
			[json(404, { error: 'not_a_person' }), 404, 'account.error.failed'],
			[json(500, {}), 500, 'account.error.failed']
		];
		for (const [response, status, error] of cases) {
			const fetch = vi.fn(async () => response);
			const result = await actions.email({
				request: post('email', { password: 'pw', email: 'a@b.co' }),
				fetch,
				cookies: cookiesWith()
			});
			expect(result.status).toBe(status);
			expect(result.data).toEqual({ action: 'email', error, email: 'a@b.co' });
		}
	});

	it('gives the typed address back on a refusal, so the field keeps it', async () => {
		const fetch = vi.fn(async () => json(400, { error: 'invalid_email' }));
		const result = await actions.email({
			request: post('email', { password: 'pw', email: ' typo@mail ' }),
			fetch,
			cookies: cookiesWith()
		});
		expect(result.data.email).toBe('typo@mail');
	});

	it('refuses an empty field and a missing token without calling the API', async () => {
		const fetch = vi.fn();
		const empty = await actions.email({
			request: post('email', { password: '', email: 'a@b.co' }),
			fetch,
			cookies: cookiesWith()
		});
		expect(empty.status).toBe(400);
		expect(empty.data).toEqual({ action: 'email', error: 'account.error.missing', email: 'a@b.co' });

		const anonymous = await actions.email({
			request: post('email', { password: 'pw', email: 'a@b.co' }),
			fetch,
			cookies: cookiesWith(null)
		});
		expect(anonymous.status).toBe(403);
		expect(fetch).not.toHaveBeenCalled();
	});
});

describe('password action', () => {
	const fields = { current: 'old', new: 'fresh-one', confirmation: 'fresh-one' };

	it('refuses a mismatch before calling the API', async () => {
		const fetch = vi.fn();
		const result = await actions.password({
			request: post('password', { ...fields, confirmation: 'other' }),
			fetch,
			cookies: cookiesWith()
		});
		expect(result.status).toBe(400);
		expect(result.data).toEqual({ action: 'password', error: 'account.error.mismatch' });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('refuses an empty field before calling the API', async () => {
		const fetch = vi.fn();
		const result = await actions.password({
			request: post('password', { ...fields, current: '' }),
			fetch,
			cookies: cookiesWith()
		});
		expect(result.data).toEqual({ action: 'password', error: 'account.error.missing' });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('sends both passwords and stores the new token on success', async () => {
		const fetch = vi.fn(async () => json(200, { token: 'new-token' }));
		const cookies = cookiesWith();
		const result = await actions.password({ request: post('password', fields), fetch, cookies });

		const [url, options] = fetch.mock.calls[0];
		expect(url).toBe('http://api/me/password/');
		expect(options.method).toBe('PUT');
		expect(JSON.parse(options.body)).toEqual({ current: 'old', new: 'fresh-one' });
		expect(cookies.set).toHaveBeenCalledWith('token', 'new-token', tokenCookieOptions());
		expect(result).toEqual({ ok: true, action: 'password' });
	});

	it("maps the validators' codes, an unknown one to the generic refusal", async () => {
		const fetch = vi.fn(async () => json(400, { errors: ['password_too_short', 'password_too_common', 'weird'] }));
		const cookies = cookiesWith();
		const result = await actions.password({ request: post('password', fields), fetch, cookies });
		expect(result.status).toBe(400);
		expect(result.data).toEqual({
			action: 'password',
			errors: ['claim.error.password_too_short', 'claim.error.password_too_common', 'claim.error.invalid']
		});
		expect(cookies.set).not.toHaveBeenCalled();
	});

	it('maps a wrong current password and the throttle', async () => {
		for (const [response, status, error] of [
			[json(400, { error: 'wrong_password' }), 400, 'account.error.wrong_password'],
			[json(429, { detail: 'Request was throttled.' }), 429, 'account.error.throttled']
		]) {
			const fetch = vi.fn(async () => response);
			const result = await actions.password({ request: post('password', fields), fetch, cookies: cookiesWith() });
			expect(result.status).toBe(status);
			expect(result.data).toEqual({ action: 'password', error });
		}
	});

	it('fails without storing anything when the API answers no token', async () => {
		const fetch = vi.fn(async () => json(200, {}));
		const cookies = cookiesWith();
		const result = await actions.password({ request: post('password', fields), fetch, cookies });
		expect(result.data).toEqual({ action: 'password', error: 'account.error.failed' });
		expect(cookies.set).not.toHaveBeenCalled();
	});
});

describe('deactivate action', () => {
	it('needs the typed word before calling the API', async () => {
		for (const confirmation of ['', 'oui', 'SUPPRIME', 'delete me']) {
			const fetch = vi.fn();
			const cookies = cookiesWith();
			const result = await actions.deactivate({
				request: post('deactivate', { password: 'pw', confirmation }),
				fetch,
				cookies
			});
			expect(result.status).toBe(400);
			expect(result.data).toEqual({ action: 'deactivate', error: 'account.error.confirmation' });
			expect(fetch).not.toHaveBeenCalled();
			expect(cookies.delete).not.toHaveBeenCalled();
		}
	});

	it('calls the API, clears the cookie and redirects home, whatever the case of the word', async () => {
		for (const confirmation of ['SUPPRIMER', ' supprimer ', 'delete', 'Delete']) {
			const fetch = vi.fn(async () => new Response(null, { status: 204 }));
			const cookies = cookiesWith();
			await expect(
				actions.deactivate({ request: post('deactivate', { password: 'pw', confirmation }), fetch, cookies })
			).rejects.toMatchObject({ status: 303, location: '/' });

			const [url, options] = fetch.mock.calls[0];
			expect(url).toBe('http://api/me/deactivate/');
			expect(options.method).toBe('POST');
			expect(JSON.parse(options.body)).toEqual({ password: 'pw' });
			expect(cookies.delete).toHaveBeenCalledWith('token', { path: '/' });
		}
	});

	it('keeps the session and maps the refusal on failure', async () => {
		for (const [response, status, error] of [
			[json(400, { error: 'wrong_password' }), 400, 'account.error.wrong_password'],
			[json(429, { detail: 'Request was throttled.' }), 429, 'account.error.throttled'],
			// The page offers no deletion to an organiser; the API refuses one all the same.
			[json(400, { error: 'organiser_cannot_deactivate' }), 400, 'account.error.organiser']
		]) {
			const fetch = vi.fn(async () => response);
			const cookies = cookiesWith();
			const result = await actions.deactivate({
				request: post('deactivate', { password: 'pw', confirmation: 'DELETE' }),
				fetch,
				cookies
			});
			expect(result.status).toBe(status);
			expect(result.data).toEqual({ action: 'deactivate', error });
			expect(cookies.delete).not.toHaveBeenCalled();
		}
	});

	it('refuses a missing password without calling the API', async () => {
		const fetch = vi.fn();
		const result = await actions.deactivate({
			request: post('deactivate', { password: '', confirmation: 'DELETE' }),
			fetch,
			cookies: cookiesWith()
		});
		expect(result.data).toEqual({ action: 'deactivate', error: 'account.error.missing' });
		expect(fetch).not.toHaveBeenCalled();
	});
});

describe('owner actions', () => {
	it('are the shared photo, removePhoto and showcase actions', () => {
		expect(Object.keys(actions).sort()).toEqual(['deactivate', 'email', 'password', 'photo', 'removePhoto', 'showcase']);
	});

	it("skip the page id check: /me/ answering is enough", async () => {
		const fetch = vi.fn(async (url) => (url === 'http://api/me/' ? json(200, me) : new Response(null, { status: 204 })));
		const result = await actions.removePhoto({ request: post('removePhoto', {}), fetch, cookies: cookiesWith(), params: {} });
		expect(result).toEqual({ ok: true, action: 'removePhoto' });
		expect(fetch.mock.calls[1][0]).toBe('http://api/me/photo/');
	});
});

describe('account actions and secrets', () => {
	const responses = [
		() => json(400, { error: 'wrong_password' }),
		() => json(400, { error: 'invalid_email' }),
		() => json(400, { errors: ['password_too_short'] }),
		() => json(429, { detail: 'Request was throttled.' }),
		() => json(500, {}),
		() => json(200, {})
	];
	const posts = [
		['email', { password: 'secret-current', email: 'a@b.co' }],
		['email', { password: 'secret-current', email: '' }],
		['password', { current: 'secret-current', new: 'secret-new', confirmation: 'secret-new' }],
		['password', { current: 'secret-current', new: 'secret-new', confirmation: 'secret-other' }],
		['password', { current: '', new: 'secret-new', confirmation: 'secret-new' }],
		['deactivate', { password: 'secret-current', confirmation: 'DELETE' }],
		['deactivate', { password: 'secret-current', confirmation: 'nope' }]
	];

	it('never send a password back to the page', async () => {
		for (const [action, fields] of posts) {
			for (const response of responses) {
				const fetch = vi.fn(async () => response());
				// A success redirects (deactivate), which carries no data at all.
				const result = await actions[action]({ request: post(action, fields), fetch, cookies: cookiesWith() }).catch(
					(redirect) => ({ status: redirect.status })
				);
				const text = JSON.stringify(result?.data ?? result);
				for (const secret of ['secret-current', 'secret-new', 'secret-other']) {
					expect(text, `${action} ${text}`).not.toContain(secret);
				}
			}
		}
	});
});
