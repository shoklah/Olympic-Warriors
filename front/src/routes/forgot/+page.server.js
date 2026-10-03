import { fail } from '@sveltejs/kit';
import { apiPost, statusOf } from '$lib/api';
import { forwardedFor } from '$lib/server/forwarded-for';
import { api } from '$lib/server/urls';

export const actions = {
	/**
	 * Ask for a reset mail. Whatever the API says but 429 and an outage (5xx or no answer), the page shows the same
	 * confirmation: it must not reveal which emails exist, and the API does not either. The
	 * visitor's address is forwarded so the API's per-IP throttle counts visitors, not this
	 * server.
	 */
	request: async ({ request, fetch, getClientAddress }) => {
		const email = String((await request.formData()).get('email') ?? '').trim();
		if (!email) return fail(400, { error: 'forgot.error.missing' });
		try {
			await apiPost(fetch, api('/password-reset/'), { email }, null, forwardedFor(getClientAddress));
		} catch (err) {
			const status = statusOf(err);
			if (status === 429) return fail(429, { error: 'login.throttled' });
			if (status >= 500) return fail(502, { error: 'forgot.error.failed' });
		}
		return { sent: true };
	}
};
