import { describe, expect, it, vi } from 'vitest';
import { actions } from './+page.server.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const request = (email) => {
	const form = new FormData();
	if (email !== undefined) form.set('email', email);
	return new Request('http://x/forgot', { method: 'POST', body: form });
};

const run = (email, response = json(200, {}), getClientAddress = () => '203.0.113.9') => {
	const fetch = vi.fn(async () => response);
	return { fetch, result: actions.request({ request: request(email), fetch, getClientAddress }) };
};

describe('forgot request action', () => {
	it('posts the email with the visitor address and shows the neutral state', async () => {
		const { fetch, result } = run(' lea@mail.example ');

		await expect(result).resolves.toEqual({ sent: true });
		expect(fetch.mock.calls[0][0]).toBe('http://api/password-reset/');
		expect(fetch.mock.calls[0][1].method).toBe('POST');
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ email: 'lea@mail.example' });
		expect(fetch.mock.calls[0][1].headers['x-forwarded-for']).toBe('203.0.113.9');
	});

	it('still posts when the adapter cannot tell the address', async () => {
		const { fetch, result } = run('lea@mail.example', json(200, {}), () => {
			throw new Error('absent');
		});

		await expect(result).resolves.toEqual({ sent: true });
		expect(fetch.mock.calls[0][1].headers['x-forwarded-for']).toBeUndefined();
	});

	it('refuses an empty email without calling the API', async () => {
		for (const email of [undefined, '', '   ']) {
			const { fetch, result } = run(email);
			expect(await result).toMatchObject({ status: 400, data: { error: 'forgot.error.missing' } });
			expect(fetch).not.toHaveBeenCalled();
		}
	});

	it('maps a 429 to the throttle line', async () => {
		const { result } = run('lea@mail.example', json(429, { detail: 'Request was throttled.' }));

		expect(await result).toMatchObject({ status: 429, data: { error: 'login.throttled' } });
	});

	it('shows the neutral state for a 4xx other than 429', async () => {
		for (const response of [json(400, { detail: 'x' }), json(404, {})]) {
			const { result } = run('lea@mail.example', response);
			await expect(result).resolves.toEqual({ sent: true });
		}
	});

	it('reports a failed send for a 5xx or a network error', async () => {
		const { result } = run('lea@mail.example', json(500, { detail: 'boom' }));
		expect(await result).toMatchObject({ status: 502, data: { error: 'forgot.error.failed' } });
		const fetch = vi.fn(async () => {
			throw new TypeError('network down');
		});
		expect(
			await actions.request({ request: request('lea@mail.example'), fetch, getClientAddress: () => '1.1.1.1' })
		).toMatchObject({ status: 502, data: { error: 'forgot.error.failed' } });
	});
});
