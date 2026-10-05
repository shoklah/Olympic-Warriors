import { json } from '@sveltejs/kit';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE } from '$lib/session';

/**
 * Forward one of the builder page's JSON calls to the API with the organiser's token, and
 * hand the answer back as it is (status and body: a 409 carries the stored draft).
 * `year` is spliced into an API path, so only four digits reach it.
 */
export async function forward({ fetch, cookies, params, request }, method, path, withBody = false) {
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) return json({ error: 'unauthorised' }, { status: 401 });
	if (!/^\d{4}$/.test(params.year)) return json({ error: 'not_found' }, { status: 404 });
	const headers = { authorization: `Token ${token}` };
	const options = { method, headers };
	if (withBody) {
		headers['content-type'] = 'application/json';
		options.body = await request.text();
	}
	let response;
	try {
		response = await fetch(api(`/builder/${params.year}${path}`), options);
	} catch {
		return json({ error: 'unreachable' }, { status: 502 });
	}
	const body = response.status === 204 ? null : await response.text();
	return new Response(body, {
		status: response.status,
		headers: { 'content-type': 'application/json', 'cache-control': 'private, no-store' }
	});
}
