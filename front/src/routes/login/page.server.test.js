import { describe, expect, it, vi } from 'vitest';
import { actions } from './+page.server.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const post = (fields) => {
	const body = new FormData();
	for (const [name, value] of Object.entries(fields)) body.append(name, value);
	return new Request('http://localhost/login', { method: 'POST', body });
};

const login = ({ next, response = json(200, { token: 'abc' }), getClientAddress = () => '203.0.113.7' } = {}) => {
	const fetch = vi.fn().mockResolvedValue(response);
	const cookies = { set: vi.fn() };
	const result = actions.login({
		cookies,
		request: post({ username: 'ana', password: 'secret', ...(next === undefined ? {} : { next }) }),
		fetch,
		getClientAddress
	});
	return { result, fetch, cookies };
};

describe('login action', () => {
	it('forwards the visitor address to the API, stores the token and goes home', async () => {
		const { result, fetch, cookies } = login();
		await expect(result).rejects.toMatchObject({ status: 302, location: '/' });
		expect(fetch).toHaveBeenCalledWith('http://api/auth/token/', {
			method: 'POST',
			headers: { 'content-type': 'application/json', 'x-forwarded-for': '203.0.113.7' },
			body: JSON.stringify({ username: 'ana', password: 'secret' })
		});
		expect(cookies.set).toHaveBeenCalledWith('token', 'abc', expect.objectContaining({ httpOnly: true }));
	});

	it('still logs in without the header when the adapter cannot tell the address', async () => {
		const { result, fetch } = login({
			getClientAddress: () => {
				throw new Error('Address header was specified with ADDRESS_HEADER=x-forwarded-for but is absent from request');
			}
		});
		await expect(result).rejects.toMatchObject({ status: 302, location: '/' });
		expect(fetch.mock.calls[0][1].headers).toEqual({ 'content-type': 'application/json' });
	});

	it('flags a throttled attempt apart from wrong credentials', async () => {
		let { result } = login({ response: json(429, { detail: 'Request was throttled. Expected available in 42 seconds.' }) });
		expect(await result).toMatchObject({ status: 429, data: { username: 'ana', throttled: true } });
		({ result } = login({ response: json(400, { non_field_errors: ['Unable to log in with provided credentials.'] }) }));
		expect(await result).toMatchObject({ status: 400, data: { username: 'ana', throttled: false } });
	});

	it('returns to the local path of next, and goes home for anything else', async () => {
		let { result } = login({ next: '/account' });
		await expect(result).rejects.toMatchObject({ status: 302, location: '/account' });
		for (const next of ['https://evil.example', '//evil.example', '/\\evil.example', '']) {
			({ result } = login({ next }));
			await expect(result).rejects.toMatchObject({ status: 302, location: '/' });
		}
	});

	it('hands next back on a refusal, so a retry still returns there', async () => {
		const { result } = login({ next: '/account', response: json(400, {}) });
		expect(await result).toMatchObject({ status: 400, data: { next: '/account' } });
	});
});
