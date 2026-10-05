import { fail, redirect } from '@sveltejs/kit';
import { apiGet, apiPost, statusOf } from '$lib/api';
import { forwardedFor } from '$lib/server/forwarded-for';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE, tokenCookieOptions } from '$lib/session';

/**
 * One part of a password link (a claim or a reset) as Django issues it: the user id in
 * base64url, or the `<timestamp>-<hash>` token, so letters, digits, `-` and `_`, and never
 * long. Both parts are spliced into an API path, where a decoded `..` could otherwise walk to
 * another endpoint; anything else is a dead link anyway, so it gets the invalid state without
 * calling the API.
 */
export const LINK_PART = /^[A-Za-z0-9_-]{1,128}$/;

/**
 * `(params) => path`: the API path under `prefix` of the link in the route's `uid` and
 * `token`, or null for a link not shaped like one.
 */
export const linkPath =
	(prefix) =>
	({ uid, token }) =>
		LINK_PART.test(uid) && LINK_PART.test(token) ? `${prefix}/${uid}/${token}/` : null;

/** The password validator codes the API answers, each worded as `claim.error.<code>`. */
export const PASSWORD_CODES = new Set([
	'password_too_short',
	'password_too_common',
	'password_entirely_numeric',
	'password_too_similar',
	'password_missing'
]);

/**
 * The dictionary keys for the API's validator codes, in its order. A code this page does not
 * know (a validator added on the server) reads as one generic refusal, and so does a 400
 * without any code.
 */
export function passwordErrors(codes) {
	const keys = (Array.isArray(codes) ? codes : []).map((code) =>
		PASSWORD_CODES.has(code) ? `claim.error.${code}` : 'claim.error.invalid'
	);
	return keys.length > 0 ? [...new Set(keys)] : ['claim.error.invalid'];
}

/**
 * The load of a link page: whose link this is, `{ state: 'ready', first_name, username }`, or
 * the state the page shows instead of the form: `invalid` for the API's 404 (a bad, used or
 * expired link, or an account it cannot serve, all answered alike so the link reveals nobody)
 * and `throttled` for a 429. Any other failure is the error page. The API throttles only the
 * POST, not this read; the 429 state and the visitor's address stay as a safeguard should
 * that change. The page carries a live credential in its URL and the username, so no cache
 * (browser or shared) may keep any rendering of it.
 */
export function linkLoad(pathOf) {
	return async ({ params, fetch, getClientAddress, setHeaders }) => {
		setHeaders({ 'cache-control': 'private, no-store' });
		const path = pathOf(params);
		if (!path) return { state: 'invalid' };
		try {
			const { first_name, username } = await apiGet(fetch, api(path), null, forwardedFor(getClientAddress));
			return { state: 'ready', first_name: first_name ?? '', username: username ?? '' };
		} catch (err) {
			if (err?.status === 404) return { state: 'invalid' };
			if (err?.status === 429) return { state: 'throttled' };
			throw err;
		}
	};
}

/**
 * The action of a link page: set the password the person chose, then log them in. The API
 * answers a fresh token (the old one and every session are gone), stored like the login's,
 * then a 303 to `await landing(body, { fetch, token })`: the API's answer, and what the landing needs to ask more. Failures come back as dictionary keys:
 * `password` and `confirmation` for the lines under those fields, `error` for the line above
 * the form, `invalid` when the link died since the page loaded. A password is never sent back
 * to the page.
 */
export function linkAction(pathOf, landing) {
	return async ({ params, request, fetch, cookies, getClientAddress }) => {
		const path = pathOf(params);
		if (!path) return fail(404, { invalid: true });

		const form = await request.formData();
		const password = String(form.get('password') ?? '');
		const confirmation = String(form.get('confirmation') ?? '');
		if (!password || !confirmation) {
			return fail(400, {
				...(password ? {} : { password: ['claim.error.password_missing'] }),
				...(confirmation ? {} : { confirmation: ['claim.error.confirmation_missing'] })
			});
		}
		if (password !== confirmation) return fail(400, { confirmation: ['claim.error.mismatch'] });

		let body;
		try {
			body = await apiPost(fetch, api(path), { password }, null, forwardedFor(getClientAddress));
		} catch (err) {
			const status = statusOf(err);
			if (status === 400) return fail(400, { password: passwordErrors(err?.body?.errors) });
			if (status === 404) return fail(404, { invalid: true });
			if (status === 429) return fail(429, { error: 'login.throttled' });
			return fail(status, { error: 'claim.error.failed' });
		}

		const { token } = body ?? {};
		if (typeof token !== 'string' || token === '') return fail(502, { error: 'claim.error.failed' });
		cookies.set(TOKEN_COOKIE, token, tokenCookieOptions());
		// A 303 so the browser follows with a GET, and a full page load (the form is a plain
		// POST) so the root layout reads the new cookie and the header shows the account.
		redirect(303, await landing(body, { fetch, token }));
	};
}
