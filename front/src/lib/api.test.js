import { describe, expect, it, vi } from 'vitest';
import { apiGet, apiPost, apiPatch } from './api.js';

const jsonResponse = (status, body) =>
	new Response(JSON.stringify(body), {
		status,
		headers: { 'content-type': 'application/json' }
	});

describe('apiGet', () => {
	it('returns the parsed body on 2xx', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, [{ year: 2026 }]));
		await expect(apiGet(fetch, 'http://api/editions/')).resolves.toEqual([{ year: 2026 }]);
		expect(fetch).toHaveBeenCalledWith('http://api/editions/', { method: 'GET', headers: {} });
	});

	it('throws a SvelteKit error carrying the status and the body message', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(404, { error: 'Edition not found' }));
		await expect(apiGet(fetch, 'http://api/x')).rejects.toMatchObject({
			status: 404,
			body: { message: 'Edition not found' }
		});
	});

	it('uses the DRF detail field when there is no error field', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(401, { detail: 'Not authenticated' }));
		await expect(apiGet(fetch, 'http://api/x')).rejects.toMatchObject({
			status: 401,
			body: { message: 'Not authenticated' }
		});
	});

	it('falls back to the status text for a non-JSON error body', async () => {
		const fetch = vi.fn().mockResolvedValue(
			new Response('<h1>Bad Gateway</h1>', { status: 502, statusText: 'Bad Gateway' })
		);
		await expect(apiGet(fetch, 'http://api/x')).rejects.toMatchObject({
			status: 502,
			body: { message: 'Bad Gateway' }
		});
	});

	it('maps a network failure to 502', async () => {
		const fetch = vi.fn().mockRejectedValue(new TypeError('fetch failed'));
		await expect(apiGet(fetch, 'http://api/x')).rejects.toMatchObject({
			status: 502,
			body: { message: 'API unreachable' }
		});
	});

	it('resolves to null for a 200 labelled JSON with an empty body', async () => {
		const fetch = vi.fn().mockResolvedValue(
			new Response('', { status: 200, headers: { 'content-type': 'application/json' } })
		);
		await expect(apiGet(fetch, 'http://api/x')).resolves.toBeNull();
	});

	it('falls back to the status text for a 500 labelled JSON with an unparsable body', async () => {
		const fetch = vi.fn().mockResolvedValue(
			new Response('<h1>oops</h1>', {
				status: 500,
				statusText: 'Internal Server Error',
				headers: { 'content-type': 'application/json' }
			})
		);
		await expect(apiGet(fetch, 'http://api/x')).rejects.toMatchObject({
			status: 500,
			body: { message: 'Internal Server Error' }
		});
	});

	it('maps a non-error-range status (304) to 502', async () => {
		const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 304 }));
		await expect(apiGet(fetch, 'http://api/x')).rejects.toMatchObject({
			status: 502,
			body: { message: 'API error' }
		});
	});
});

describe('apiPost', () => {
	it('sends JSON and returns the parsed body', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, { token: 'abc' }));
		await expect(apiPost(fetch, 'http://api/auth/token/', { username: 'u' })).resolves.toEqual({
			token: 'abc'
		});
		expect(fetch).toHaveBeenCalledWith('http://api/auth/token/', {
			method: 'POST',
			headers: { 'content-type': 'application/json' },
			body: '{"username":"u"}'
		});
	});

	it('adds extra headers to the JSON content type', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, { token: 'abc' }));
		await apiPost(fetch, 'http://api/auth/token/', {}, null, { 'x-forwarded-for': '203.0.113.7' });
		expect(fetch.mock.calls[0][1].headers).toEqual({
			'content-type': 'application/json',
			'x-forwarded-for': '203.0.113.7'
		});
	});

	it('throws on a 400 with the first field error as message', async () => {
		const fetch = vi.fn().mockResolvedValue(
			jsonResponse(400, { non_field_errors: ['Unable to log in with provided credentials.'] })
		);
		await expect(apiPost(fetch, 'http://api/auth/token/', {})).rejects.toMatchObject({
			status: 400,
			body: { message: 'Unable to log in with provided credentials.' }
		});
	});
});

describe('token header', () => {
	it('apiGet sends the DRF token header when given a token', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, { is_staff: true }));
		await apiGet(fetch, 'http://api/user/current/', 'abc');
		expect(fetch).toHaveBeenCalledWith('http://api/user/current/', {
			method: 'GET',
			headers: { authorization: 'Token abc' }
		});
	});

	it('apiPatch sends the JSON body and the token', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, { id: 1 }));
		await apiPatch(fetch, 'http://api/game/1/score/', { score1: 1 }, 'abc');
		expect(fetch).toHaveBeenCalledWith('http://api/game/1/score/', {
			method: 'PATCH',
			headers: { 'content-type': 'application/json', authorization: 'Token abc' },
			body: JSON.stringify({ score1: 1 })
		});
	});
});
