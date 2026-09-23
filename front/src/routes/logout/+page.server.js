import { redirect } from '@sveltejs/kit';
import { TOKEN_COOKIE } from '$lib/session';

/** Same guard as /lang: one leading slash, no control characters. */
const localPath = (value) =>
	typeof value === 'string' && /^\/(?![/\\])[^\s\x00-\x1f\x7f]*$/.test(value) ? value : '/';

export const load = () => {
	redirect(303, '/');
};

export const actions = {
	/** The header's ORGA pill: forget the token, come back to the same page as a visitor. */
	default: async ({ cookies, request }) => {
		const form = await request.formData();
		cookies.delete(TOKEN_COOKIE, { path: '/' });
		// Also drop the old pre-Task-3 login cookie, in case it is still lingering in a browser.
		cookies.delete('Authorization', { path: '/' });
		redirect(303, localPath(form.get('redirectTo')));
	}
};
