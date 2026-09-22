import { fail, redirect } from '@sveltejs/kit';
import { apiPost } from '$lib/api';
import { api } from '$lib/server/urls';

const setAuthToken = ({ cookies, token }) => {
	cookies.set('Authorization', `Bearer ${token}`, {
		httpOnly: true,
		secure: true,
		sameSite: 'strict',
		maxAge: 60 * 60 * 24 * 7, // 1 week
		path: '/'
	});
};

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

		setAuthToken({ cookies, token });
		redirect(302, '/');
	}
};
