import { fail, redirect } from '@sveltejs/kit';
import { apiPost } from '$lib/api';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE, tokenCookieOptions } from '$lib/session';

export const actions = {
	login: async ({ cookies, request, fetch }) => {
		const { username, password } = Object.fromEntries(await request.formData());

		const missing = {};
		if (!username) missing.username = true;
		if (!password) missing.password = true;
		if (Object.keys(missing).length > 0) {
			return fail(400, { missing, username });
		}

		let token;
		try {
			({ token } = await apiPost(fetch, api('/auth/token/'), { username, password }));
		} catch (err) {
			return fail(err?.status ?? 500, { username, error: err?.body?.message ?? 'Login failed' });
		}

		if (!token) {
			return fail(500, { username, error: 'Authentication failed: token not received' });
		}

		cookies.set(TOKEN_COOKIE, token, tokenCookieOptions());
		redirect(302, '/');
	}
};
