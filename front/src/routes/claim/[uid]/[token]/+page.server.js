import { fail, redirect } from '@sveltejs/kit';
import { apiGet, apiPost } from '$lib/api';
import { forwardedFor } from '$lib/server/forwarded-for';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE, tokenCookieOptions } from '$lib/session';

/**
 * One part of a claim link as Django issues it: the user id in base64url, or the
 * `<timestamp>-<hash>` token, so letters, digits, `-` and `_`, and never long. Both parts are
 * spliced into an API path, where a decoded `..` could otherwise walk to another endpoint;
 * anything else is a dead link anyway, so it gets the invalid state without costing the
 * visitor a throttled attempt.
 */
const LINK_PART = /^[A-Za-z0-9_-]{1,128}$/;

/** The API path of the claim link, or null for a link not shaped like one. */
const claimPath = ({ uid, token }) =>
	LINK_PART.test(uid) && LINK_PART.test(token) ? `/claim/${uid}/${token}/` : null;

/** The password validator codes the API answers, each worded as `claim.error.<code>`. */
const PASSWORD_CODES = new Set([
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
function passwordErrors(codes) {
	const keys = (Array.isArray(codes) ? codes : []).map((code) =>
		PASSWORD_CODES.has(code) ? `claim.error.${code}` : 'claim.error.invalid'
	);
	return keys.length > 0 ? [...new Set(keys)] : ['claim.error.invalid'];
}

/**
 * Whose link this is, `{ state: 'ready', first_name, username }`, or the state the page shows
 * instead of the form: `invalid` for the API's 404 (a bad, used or expired link, or an account
 * that cannot be claimed, all answered alike so the link reveals nobody) and `throttled` for
 * its 429. Any other failure is the error page. The API throttles this read per client IP, like
 * the login, so the visitor's address goes along.
 */
export const load = async ({ params, fetch, getClientAddress }) => {
	const path = claimPath(params);
	if (!path) return { state: 'invalid' };
	try {
		const { first_name, username } = await apiGet(
			fetch,
			api(path),
			null,
			forwardedFor(getClientAddress)
		);
		return { state: 'ready', first_name: first_name ?? '', username: username ?? '' };
	} catch (err) {
		if (err?.status === 404) return { state: 'invalid' };
		if (err?.status === 429) return { state: 'throttled' };
		throw err;
	}
};

export const actions = {
	/**
	 * Set the password the person chose, then log them in: the API answers a fresh token (the
	 * old one and every session are gone), stored like the login's, and the profile opens.
	 * Failures come back as dictionary keys: `password` and `confirmation` for the lines under
	 * those fields, `error` for the line above the form, `invalid` when the link died since
	 * the page loaded. A password is never sent back to the page.
	 */
	claim: async ({ params, request, fetch, cookies, getClientAddress }) => {
		const path = claimPath(params);
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
			const status =
				Number.isInteger(err?.status) && err.status >= 400 && err.status <= 599 ? err.status : 500;
			if (status === 400) return fail(400, { password: passwordErrors(err?.body?.errors) });
			if (status === 404) return fail(404, { invalid: true });
			if (status === 429) return fail(429, { error: 'login.throttled' });
			return fail(status, { error: 'claim.error.failed' });
		}

		const { token, user_id } = body ?? {};
		if (typeof token !== 'string' || token === '') return fail(502, { error: 'claim.error.failed' });
		cookies.set(TOKEN_COOKIE, token, tokenCookieOptions());
		// A 303 so the browser follows with a GET, and a full page load (the form is a plain
		// POST) so the root layout reads the new cookie and the header shows the account.
		redirect(303, Number.isInteger(user_id) && user_id > 0 ? `/players/${user_id}` : '/');
	}
};
