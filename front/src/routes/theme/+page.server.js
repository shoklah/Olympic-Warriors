import { redirect } from '@sveltejs/kit';
import { localPath } from '$lib/local-path';
import { THEMES, THEME_COOKIE } from '$lib/theme';

/** Nothing to show here: a GET goes to the hub. */
export const load = () => {
	redirect(303, '/');
};

export const actions = {
	/**
	 * The header's theme switch: store the choice for a year, come back to the same page.
	 * Any other value forgets the choice, handing the theme back to the device setting.
	 */
	default: async ({ cookies, request }) => {
		const form = await request.formData();
		const theme = form.get('theme');
		if (THEMES.includes(theme)) {
			cookies.set(THEME_COOKIE, theme, {
				path: '/',
				maxAge: 60 * 60 * 24 * 365,
				sameSite: 'lax',
				httpOnly: false
			});
		} else {
			cookies.delete(THEME_COOKIE, { path: '/' });
		}
		redirect(303, localPath(form.get('redirectTo')));
	}
};
