import { fail, redirect } from '@sveltejs/kit';
import { apiGet, apiSend, statusOf } from '$lib/api';
import { bodyFromValues, errorKeys, valuesFromForm } from '$lib/registration';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE } from '$lib/session';

/** Where a visitor goes to log in, then comes back here. */
const LOGIN = '/login?next=/register';

/** The refusals the API words with an `{error}` code, each with its own sentence. */
const REFUSALS = new Set([
	'closed', 'not_yet_open', 'not_configured', 'removed_by_organiser', 'has_team'
]);

/**
 * The page is the caller's own registration for the latest edition: a visitor (or a dead
 * token) goes to /login, someone who cannot register (neither a person nor invited) goes
 * home, anything else, such as no edition at all, reaches the error page. Never cached: it
 * shows the person's answers.
 */
export const load = async ({ fetch, cookies, setHeaders }) => {
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) redirect(303, LOGIN);
	setHeaders({ 'cache-control': 'private, no-store' });
	try {
		return { registration: await apiGet(fetch, api('/registration/'), token) };
	} catch (err) {
		if (err?.status === 401 || err?.status === 403) redirect(303, LOGIN);
		if (err?.status === 404 && err?.body?.message === 'not_a_person') redirect(303, '/');
		throw err;
	}
};

/** Dictionary key of a failed registration call: its `{error}` code (in the message) or a status. */
function registrationError(err) {
	if (statusOf(err) === 429) return 'register.error.throttled';
	const code = err?.body?.message;
	return REFUSALS.has(code) ? `register.error.${code}` : 'register.error.failed';
}

/** The posted form, or an empty one for a body that is not a form. */
async function formOf(request) {
	try {
		return await request.formData();
	} catch {
		return new FormData();
	}
}

export const actions = {
	/**
	 * Register, or edit the registration. A plain POST (never use:enhance): the page reloads
	 * with the saved answers. A refusal comes back with the codes as dictionary keys and the
	 * form model as typed, so the page keeps what the person wrote.
	 */
	save: async ({ request, cookies, fetch }) => {
		const token = cookies.get(TOKEN_COOKIE);
		if (!token) return fail(403, { action: 'save', error: 'register.error.failed' });
		const form = await formOf(request);
		const values = valuesFromForm(form);
		const body = bodyFromValues(values, form.has('email'));
		try {
			await apiSend(fetch, api('/registration/'), {
				method: 'PUT',
				token,
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify(body)
			});
		} catch (err) {
			const codes = err?.body?.errors;
			if (statusOf(err) === 400 && Array.isArray(codes)) {
				return fail(400, { action: 'save', errors: errorKeys(codes), values });
			}
			return fail(statusOf(err), { action: 'save', error: registrationError(err), values });
		}
		return { ok: true, action: 'save' };
	},

	/** Withdraw; the answers are kept for a later registration. */
	withdraw: async ({ cookies, fetch }) => {
		const token = cookies.get(TOKEN_COOKIE);
		if (!token) return fail(403, { action: 'withdraw', error: 'register.error.failed' });
		try {
			await apiSend(fetch, api('/registration/'), { method: 'DELETE', token });
		} catch (err) {
			return fail(statusOf(err), { action: 'withdraw', error: registrationError(err) });
		}
		return { ok: true, action: 'withdraw' };
	}
};
