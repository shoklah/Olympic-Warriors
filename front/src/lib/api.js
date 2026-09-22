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

async function request(fetch, url, options) {
	let response;
	try {
		response = await fetch(url, options);
	} catch {
		error(502, 'API unreachable');
	}

	const isJson = (response.headers.get('content-type') ?? '').includes('application/json');
	const body = isJson ? await response.json() : await response.text();

	if (!response.ok) {
		error(response.status, messageFrom(isJson ? body : null, response.statusText || 'API error'));
	}
	return body;
}

/** GET a JSON resource; throws a SvelteKit error on any failure. */
export function apiGet(fetch, url) {
	return request(fetch, url, { method: 'GET', headers: {} });
}

/** POST a JSON body; throws a SvelteKit error on any failure. */
export function apiPost(fetch, url, body) {
	return request(fetch, url, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(body)
	});
}
