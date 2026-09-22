import { describe, expect, it, vi } from 'vitest';
import { apiGet, apiPost } from './api.js';

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
