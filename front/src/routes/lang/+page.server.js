import { redirect } from '@sveltejs/kit';
import { localeFrom } from '$lib/i18n/locale.js';

/**
 * Only a path on this site: one leading slash, so `//host`, `/\host` (which browsers
 * read as scheme-relative) and absolute URLs go home.
 */
const localPath = (value) => (typeof value === 'string' && /^\/(?![/\\])/.test(value) ? value : '/');

/** Nothing to show here: a GET goes to the hub. */
export const load = () => {
	redirect(303, '/');
};

export const actions = {
	/** The header's FR | EN form: store the choice for a year, come back to the same page. */
	default: async ({ cookies, request }) => {
		const form = await request.formData();
		cookies.set('lang', localeFrom(form.get('lang')), {
			path: '/',
			maxAge: 60 * 60 * 24 * 365,
			sameSite: 'lax',
			httpOnly: false
		});
		redirect(303, localPath(form.get('redirectTo')));
	}
};
