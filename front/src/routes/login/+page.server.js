import { fail, redirect } from '@sveltejs/kit';
import { apiPost } from '$lib/api';
import { forwardedFor } from '$lib/server/forwarded-for';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE, tokenCookieOptions } from '$lib/session';

export const actions = {
	login: async ({ cookies, request, fetch, getClientAddress }) => {
		const { username, password } = Object.fromEntries(await request.formData());

		const missing = {};
		if (!username) missing.username = true;
		if (!password) missing.password = true;
		if (Object.keys(missing).length > 0) {
			return fail(400, { missing, username });
		}

		let token;
		try {
			({ token } = await apiPost(
				fetch,
				api('/auth/token/'),
				{ username, password },
				null,
				forwardedFor(getClientAddress)
			));
		} catch (err) {
			const status = err?.status ?? 500;
			return fail(status, {
				username,
				error: err?.body?.message ?? 'Login failed',
				throttled: status === 429
			});
		}

		if (!token) {
			return fail(500, { username, error: 'Authentication failed: token not received' });
		}

		cookies.set(TOKEN_COOKIE, token, tokenCookieOptions());
		redirect(302, '/');
	}
};
