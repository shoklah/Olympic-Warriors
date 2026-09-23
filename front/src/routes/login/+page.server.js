import { fail, redirect } from '@sveltejs/kit';
import { apiPost } from '$lib/api';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE, tokenCookieOptions } from '$lib/session';

/**
 * The visitor's address for the API's login throttle, which counts attempts per client IP.
 * This server calls the API itself, so without the header every visitor would share its
 * address. Behind nginx, adapter-node needs ADDRESS_HEADER to see past the proxy, and throws
 * when that header is missing from a request: the API then falls back to this server's address.
 */
function forwardedFor(getClientAddress) {
	try {
		const address = getClientAddress();
		return address ? { 'x-forwarded-for': address } : {};
	} catch {
		return {};
	}
}

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
