import { describe, expect, it, vi } from 'vitest';
import { apiGet, apiPost, apiPatch, apiSend } from './api.js';

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

	it('adds extra headers, such as the visitor address', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, { username: 'leamartin' }));
		await apiGet(fetch, 'http://api/claim/MzQ/abc-123/', null, { 'x-forwarded-for': '203.0.113.7' });
		expect(fetch).toHaveBeenCalledWith('http://api/claim/MzQ/abc-123/', {
			method: 'GET',
			headers: { 'x-forwarded-for': '203.0.113.7' }
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

	it("keeps the API's whole list of error codes, not only the first as the message", async () => {
		const fetch = vi.fn().mockResolvedValue(
			jsonResponse(400, { errors: ['password_too_common', 'password_entirely_numeric'] })
		);
		await expect(apiPost(fetch, 'http://api/claim/MzQ/abc-123/', {})).rejects.toMatchObject({
			status: 400,
			body: {
				message: 'password_too_common',
				errors: ['password_too_common', 'password_entirely_numeric']
			}
		});
	});

	it('carries no error codes for a body without a list of them', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(400, { errors: 'not a list', detail: 'Bad' }));
		const failure = await apiPost(fetch, 'http://api/x', {}).catch((err) => err);
		expect(failure.body).toEqual({ message: 'Bad' });
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

describe('apiSend', () => {
	it('sends a FormData body as is, with no content type, so fetch writes the multipart boundary', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, { photo: { large: '/l.webp', small: '/s.webp' } }));
		const body = new FormData();
		body.append('photo', new Blob(['jpeg'], { type: 'image/jpeg' }), 'photo.jpg');

		await expect(apiSend(fetch, 'http://api/me/photo/', { method: 'PUT', token: 'abc', body })).resolves.toEqual({
			photo: { large: '/l.webp', small: '/s.webp' }
		});
		const [url, options] = fetch.mock.calls[0];
		expect(url).toBe('http://api/me/photo/');
		expect(options.method).toBe('PUT');
		expect(options.headers).toEqual({ authorization: 'Token abc' });
		expect(options.body).toBe(body);
	});

	it('sends no body when given none, as for a DELETE', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, {}));
		await apiSend(fetch, 'http://api/me/photo/', { method: 'DELETE', token: 'abc' });
		expect(fetch).toHaveBeenCalledWith('http://api/me/photo/', {
			method: 'DELETE',
			headers: { authorization: 'Token abc' }
		});
	});

	it('adds extra headers', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, {}));
		await apiSend(fetch, 'http://api/x', { method: 'DELETE', headers: { 'x-forwarded-for': '203.0.113.7' } });
		expect(fetch.mock.calls[0][1].headers).toEqual({ 'x-forwarded-for': '203.0.113.7' });
	});

	it('resolves to null for a 204 with no body, and for an empty 200', async () => {
		let fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
		await expect(apiSend(fetch, 'http://api/me/photo/', { method: 'DELETE', token: 'abc' })).resolves.toBeNull();
		fetch = vi.fn().mockResolvedValue(new Response('', { status: 200 }));
		await expect(apiSend(fetch, 'http://api/me/photo/', { method: 'DELETE', token: 'abc' })).resolves.toBeNull();
	});

	it('throws the API error code as the message, like the other helpers', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(403, { error: 'photo_locked' }));
		await expect(apiSend(fetch, 'http://api/me/photo/', { method: 'PUT', token: 'abc' })).rejects.toMatchObject({
			status: 403,
			body: { message: 'photo_locked' }
		});
	});

	it("keeps the status of a proxy's non-JSON refusal (nginx's 413)", async () => {
		const fetch = vi.fn().mockResolvedValue(
			new Response('<html>413 Request Entity Too Large</html>', {
				status: 413,
				statusText: 'Request Entity Too Large',
				headers: { 'content-type': 'text/html' }
			})
		);
		await expect(apiSend(fetch, 'http://api/me/photo/', { method: 'PUT', token: 'abc' })).rejects.toMatchObject({
			status: 413,
			body: { message: 'Request Entity Too Large' }
		});
	});

	it('maps a network failure to 502', async () => {
		const fetch = vi.fn().mockRejectedValue(new TypeError('fetch failed'));
		await expect(apiSend(fetch, 'http://api/me/photo/', { method: 'DELETE' })).rejects.toMatchObject({ status: 502 });
	});
});
