import { error, fail, redirect } from '@sveltejs/kit';
import { apiGet, apiSend } from '$lib/api';
import { ownerActions, statusOf } from '$lib/server/owner-actions';
import { PASSWORD_CODES } from '$lib/server/password-link';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE, tokenCookieOptions } from '$lib/session';

/** The word that confirms a deletion, in either language, compared trimmed and lower-cased. */
const CONFIRM_WORDS = new Set(['supprimer', 'delete']);

/**
 * The page is the caller's own: a visitor (or a dead token) goes to /login, anyone who is
 * not a non-staff person gets a 404. Never cached: it shows the username and the email.
 */
export const load = async ({ fetch, cookies, setHeaders }) => {
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) redirect(303, '/login');
	setHeaders({ 'cache-control': 'private, no-store' });
	let account;
	try {
		account = await apiGet(fetch, api('/me/'), token);
	} catch (err) {
		if (err?.status === 401 || err?.status === 403) redirect(303, '/login');
		throw err;
	}
	if (account.is_staff || !account.is_person) error(404, 'No such page');
	const profile = await apiGet(fetch, api(`/profile/${account.id}/`));
	return {
		account: { id: account.id, username: account.username, email: account.email ?? '' },
		profile
	};
};

/** Dictionary key of a failed account call: the API's `{error: code}` (in the error message) or a status. */
function accountError(err) {
	if (statusOf(err) === 429) return 'account.error.throttled';
	const code = err?.body?.message;
	if (code === 'wrong_password' || code === 'invalid_email') return `account.error.${code}`;
	return 'account.error.failed';
}

const jsonCall = (event, token, method, path, body) =>
	apiSend(event.fetch, api(path), {
		method,
		token,
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(body)
	});

/** The posted form, or an empty one for a body that is not a form. */
async function formOf(request) {
	try {
		return await request.formData();
	} catch {
		return new FormData();
	}
}

export const actions = {
	// The photo and showcase actions of the profile page; /account is always the caller's own.
	...ownerActions(() => null),

	/** A new email address, saved at once once the current password checks out. */
	email: async (event) => {
		const token = event.cookies.get(TOKEN_COOKIE);
		if (!token) return fail(403, { action: 'email', error: 'account.error.failed' });
		const form = await formOf(event.request);
		const password = String(form.get('password') ?? '');
		const email = String(form.get('email') ?? '').trim();
		// The typed address comes back on a refusal, so the field keeps it (it is no secret); the
		// password never does.
		if (!password || !email) return fail(400, { action: 'email', error: 'account.error.missing', email });
		try {
			await jsonCall(event, token, 'PUT', '/me/email/', { password, email });
		} catch (err) {
			return fail(statusOf(err), { action: 'email', error: accountError(err), email });
		}
		return { ok: true, action: 'email' };
	},

	/**
	 * A new password. The API ends every session on success and answers a fresh token, stored
	 * here so this browser stays logged in.
	 */
	password: async (event) => {
		const token = event.cookies.get(TOKEN_COOKIE);
		if (!token) return fail(403, { action: 'password', error: 'account.error.failed' });
		const form = await formOf(event.request);
		const current = String(form.get('current') ?? '');
		const next = String(form.get('new') ?? '');
		const confirmation = String(form.get('confirmation') ?? '');
		if (!current || !next) return fail(400, { action: 'password', error: 'account.error.missing' });
		if (next !== confirmation) return fail(400, { action: 'password', error: 'account.error.mismatch' });
		let body;
		try {
			body = await jsonCall(event, token, 'PUT', '/me/password/', { current, new: next });
		} catch (err) {
			const codes = err?.body?.errors;
			if (statusOf(err) === 400 && Array.isArray(codes)) {
				const keys = codes.map((c) => (PASSWORD_CODES.has(c) ? `claim.error.${c}` : 'claim.error.invalid'));
				return fail(400, { action: 'password', errors: [...new Set(keys)] });
			}
			return fail(statusOf(err), { action: 'password', error: accountError(err) });
		}
		if (typeof body?.token !== 'string' || !body.token) {
			return fail(502, { action: 'password', error: 'account.error.failed' });
		}
		event.cookies.set(TOKEN_COOKIE, body.token, tokenCookieOptions());
		return { ok: true, action: 'password' };
	},

	/**
	 * Delete the account (the API deactivates it and masks the name): the typed word, then the
	 * password. On success the session is gone, so the cookie goes too and the visitor lands home.
	 */
	deactivate: async (event) => {
		const token = event.cookies.get(TOKEN_COOKIE);
		if (!token) return fail(403, { action: 'deactivate', error: 'account.error.failed' });
		const form = await formOf(event.request);
		const password = String(form.get('password') ?? '');
		const word = String(form.get('confirmation') ?? '').trim().toLowerCase();
		if (!CONFIRM_WORDS.has(word)) return fail(400, { action: 'deactivate', error: 'account.error.confirmation' });
		if (!password) return fail(400, { action: 'deactivate', error: 'account.error.missing' });
		try {
			await jsonCall(event, token, 'POST', '/me/deactivate/', { password });
		} catch (err) {
			return fail(statusOf(err), { action: 'deactivate', error: accountError(err) });
		}
		event.cookies.delete(TOKEN_COOKIE, { path: '/' });
		redirect(303, '/');
	}
};
