import { fail } from '@sveltejs/kit';
import { apiPost } from '$lib/api';
import { forwardedFor } from '$lib/server/forwarded-for';
import { api } from '$lib/server/urls';

export const actions = {
	/**
	 * Ask for a reset mail. Whatever the API says but 429, the page shows the same
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
			if (err?.status === 429) return fail(429, { error: 'login.throttled' });
		}
		return { sent: true };
	}
};
