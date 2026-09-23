import { error } from '@sveltejs/kit';

/**
 * Pick a human message out of a DRF error body.
 * {error}, {detail}, or the first string of the first field error list.
 */
function messageFrom(body, fallback) {
	if (body && typeof body === 'object') {
		if (typeof body.error === 'string') return body.error;
		if (typeof body.detail === 'string') return body.detail;
		for (const value of Object.values(body)) {
			if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
			if (typeof value === 'string') return value;
		}
	}
	return fallback;
}

/** The DRF token header when a token is given, nothing otherwise. */
const authHeaders = (token) => (token ? { authorization: `Token ${token}` } : {});

async function request(fetch, url, options, token = null) {
	const headers = { ...(options.headers ?? {}), ...authHeaders(token) };
	let response;
	try {
		response = await fetch(url, { ...options, headers });
	} catch {
		error(502, 'API unreachable');
	}

	const isJson = (response.headers.get('content-type') ?? '').includes('application/json');
	let body = null;
	try {
		body = isJson ? await response.json() : await response.text();
	} catch {
		body = null;
	}

	if (!response.ok) {
		// SvelteKit's error() only accepts 400-599; anything else (e.g. a stray 3xx) becomes a 502.
		const inRange = response.status >= 400 && response.status <= 599;
		const status = inRange ? response.status : 502;
		const fallback = inRange ? response.statusText || 'API error' : 'API error';
		error(status, messageFrom(isJson ? body : null, fallback));
	}
	return body;
}

/** GET a JSON resource; throws a SvelteKit error on any failure. */
export function apiGet(fetch, url, token = null) {
	return request(fetch, url, { method: 'GET', headers: {} }, token);
}

/** POST a JSON body, with any extra `headers`; throws a SvelteKit error on any failure. */
export function apiPost(fetch, url, body, token = null, headers = {}) {
	return request(fetch, url, jsonOptions('POST', body, headers), token);
}

/** PATCH a JSON body; throws a SvelteKit error on any failure. */
export function apiPatch(fetch, url, body, token = null) {
	return request(fetch, url, jsonOptions('PATCH', body), token);
}

const jsonOptions = (method, body, headers = {}) => ({
	method,
	headers: { 'content-type': 'application/json', ...headers },
	body: JSON.stringify(body)
});
