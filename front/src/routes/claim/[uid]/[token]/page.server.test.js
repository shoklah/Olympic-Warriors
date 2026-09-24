import { describe, expect, it, vi } from 'vitest';
import { actions, load } from './+page.server.js';
import { tokenCookieOptions } from '$lib/session';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

// A user id as Django encodes it (base64url of "34") and a `<timestamp>-<hash>` token.
const params = { uid: 'MzQ', token: 'cxqh2p-3f9a8b7c6d5e4f3a2b1c' };
const API_PATH = 'http://api/claim/MzQ/cxqh2p-3f9a8b7c6d5e4f3a2b1c/';
const address = () => '203.0.113.7';

const post = (fields) => {
	const body = new FormData();
	for (const [name, value] of Object.entries(fields)) body.append(name, value);
	return new Request('http://localhost/claim/MzQ/cxqh2p-3f9a8b7c6d5e4f3a2b1c?/claim', {
		method: 'POST',
		body
	});
};

const claim = ({
	response = json(200, { token: 'fresh', user_id: 34 }),
	fields = { password: 'Tr3s-Olympique', confirmation: 'Tr3s-Olympique' },
	getClientAddress = address,
	linkParams = params
} = {}) => {
	const fetch = vi.fn().mockResolvedValue(response);
	const cookies = { set: vi.fn() };
	const result = actions.claim({ params: linkParams, request: post(fields), fetch, cookies, getClientAddress });
	return { result, fetch, cookies };
};

describe('claim load', () => {
	it('greets the person behind the link, forwarding the visitor address for the throttle', async () => {
		const fetch = vi.fn(async () => json(200, { first_name: 'Léa', username: 'leamartin' }));

		const data = await load({ params, fetch, getClientAddress: address });

		expect(data).toEqual({ state: 'ready', first_name: 'Léa', username: 'leamartin' });
		expect(fetch).toHaveBeenCalledWith(API_PATH, {
			method: 'GET',
			headers: { 'x-forwarded-for': '203.0.113.7' }
		});
	});

	it("renders the invalid-link state for the API's 404, not the error page", async () => {
		const fetch = vi.fn(async () => json(404, { detail: 'Not found.' }));

		await expect(load({ params, fetch, getClientAddress: address })).resolves.toEqual({ state: 'invalid' });
	});

	it('renders the throttled state for a 429', async () => {
		const fetch = vi.fn(async () => json(429, { detail: 'Request was throttled.' }));

		await expect(load({ params, fetch, getClientAddress: address })).resolves.toEqual({ state: 'throttled' });
	});

	it('throws any other failure to the error page', async () => {
		const fetch = vi.fn(async () => json(500, { detail: 'Server error' }));
		await expect(load({ params, fetch, getClientAddress: address })).rejects.toMatchObject({ status: 500 });

		const down = vi.fn().mockRejectedValue(new TypeError('fetch failed'));
		await expect(load({ params, fetch: down, getClientAddress: address })).rejects.toMatchObject({ status: 502 });
	});

	it('calls the API without the header when the adapter cannot tell the address', async () => {
		const fetch = vi.fn(async () => json(200, { first_name: 'Léa', username: 'leamartin' }));
		const getClientAddress = () => {
			throw new Error('Address header was specified with ADDRESS_HEADER=x-forwarded-for but is absent from request');
		};

		await load({ params, fetch, getClientAddress });

		expect(fetch.mock.calls[0][1].headers).toEqual({});
	});

	it('treats a link not shaped like a Django one as invalid without calling the API', async () => {
		const fetch = vi.fn();

		for (const linkParams of [
			{ uid: '..', token: 'me' },
			{ uid: 'MzQ', token: '..' },
			{ uid: 'MzQ', token: 'a b' },
			{ uid: '', token: 'abc' },
			{ uid: 'M'.repeat(200), token: 'abc' }
		]) {
			await expect(load({ params: linkParams, fetch, getClientAddress: address })).resolves.toEqual({
				state: 'invalid'
			});
		}
		expect(fetch).not.toHaveBeenCalled();
	});
});

describe('claim action', () => {
	it('posts the password with the visitor address, stores the token and opens the profile', async () => {
		const { result, fetch, cookies } = claim();

		await expect(result).rejects.toMatchObject({ status: 303, location: '/players/34' });
		expect(fetch).toHaveBeenCalledWith(API_PATH, {
			method: 'POST',
			headers: { 'content-type': 'application/json', 'x-forwarded-for': '203.0.113.7' },
			body: JSON.stringify({ password: 'Tr3s-Olympique' })
		});
		expect(cookies.set).toHaveBeenCalledWith('token', 'fresh', tokenCookieOptions());
		expect(tokenCookieOptions()).toMatchObject({ httpOnly: true, sameSite: 'lax', path: '/' });
	});

	it('still claims without the header when the adapter cannot tell the address', async () => {
		const { result, fetch } = claim({
			getClientAddress: () => {
				throw new Error('Address header was specified with ADDRESS_HEADER=x-forwarded-for but is absent from request');
			}
		});

		await expect(result).rejects.toMatchObject({ status: 303, location: '/players/34' });
		expect(fetch.mock.calls[0][1].headers).toEqual({ 'content-type': 'application/json' });
	});

	it('asks for both fields before calling the API', async () => {
		let { result, fetch } = claim({ fields: { password: '', confirmation: '' } });
		expect(await result).toMatchObject({
			status: 400,
			data: {
				password: ['claim.error.password_missing'],
				confirmation: ['claim.error.confirmation_missing']
			}
		});
		expect(fetch).not.toHaveBeenCalled();

		({ result, fetch } = claim({ fields: { password: 'Tr3s-Olympique' } }));
		const { data } = await result;
		expect(data).toEqual({ confirmation: ['claim.error.confirmation_missing'] });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('refuses two different passwords before calling the API', async () => {
		const { result, fetch, cookies } = claim({
			fields: { password: 'Tr3s-Olympique', confirmation: 'Tr3s-Olympiqve' }
		});

		expect(await result).toMatchObject({ status: 400, data: { confirmation: ['claim.error.mismatch'] } });
		expect(fetch).not.toHaveBeenCalled();
		expect(cookies.set).not.toHaveBeenCalled();
	});

	it('words every validator code the API answers, in its order', async () => {
		const codes = [
			'password_too_similar',
			'password_too_short',
			'password_too_common',
			'password_entirely_numeric',
			'password_missing'
		];
		const { result, cookies } = claim({ response: json(400, { errors: codes }) });

		expect(await result).toMatchObject({
			status: 400,
			data: { password: codes.map((code) => `claim.error.${code}`) }
		});
		expect(cookies.set).not.toHaveBeenCalled();
	});

	it('words each validator code on its own', async () => {
		for (const code of [
			'password_too_short',
			'password_too_common',
			'password_entirely_numeric',
			'password_too_similar',
			'password_missing'
		]) {
			const { result } = claim({ response: json(400, { errors: [code] }) });
			expect((await result).data).toEqual({ password: [`claim.error.${code}`] });
		}
	});

	it('words an unknown code, or a 400 without codes, as one generic refusal', async () => {
		let { result } = claim({ response: json(400, { errors: ['password_too_fancy', 'password_too_short', 'other'] }) });
		expect((await result).data).toEqual({
			password: ['claim.error.invalid', 'claim.error.password_too_short']
		});

		({ result } = claim({ response: json(400, { detail: 'JSON parse error' }) }));
		expect(await result).toMatchObject({ status: 400, data: { password: ['claim.error.invalid'] } });
	});

	it('turns a link that died since the page loaded into the invalid-link state', async () => {
		const { result, cookies } = claim({ response: json(404, { detail: 'Not found.' }) });

		expect(await result).toMatchObject({ status: 404, data: { invalid: true } });
		expect(cookies.set).not.toHaveBeenCalled();
	});

	it('asks to wait once the API throttles the attempts', async () => {
		const { result } = claim({ response: json(429, { detail: 'Request was throttled.' }) });

		expect(await result).toMatchObject({ status: 429, data: { error: 'login.throttled' } });
	});

	it('words any other failure as a failed activation', async () => {
		let { result, cookies } = claim({ response: json(500, { detail: 'Server error' }) });
		expect(await result).toMatchObject({ status: 500, data: { error: 'claim.error.failed' } });

		({ result, cookies } = claim({ response: json(200, { user_id: 34 }) }));
		expect(await result).toMatchObject({ status: 502, data: { error: 'claim.error.failed' } });
		expect(cookies.set).not.toHaveBeenCalled();
	});

	it('still logs the person in when the API gives no usable user id', async () => {
		const { result, cookies } = claim({ response: json(200, { token: 'fresh' }) });

		await expect(result).rejects.toMatchObject({ status: 303, location: '/' });
		expect(cookies.set).toHaveBeenCalledWith('token', 'fresh', tokenCookieOptions());
	});

	it('treats a malformed link as invalid without calling the API', async () => {
		const { result, fetch } = claim({ linkParams: { uid: '..', token: 'me' } });

		expect(await result).toMatchObject({ status: 404, data: { invalid: true } });
		expect(fetch).not.toHaveBeenCalled();
	});
});
