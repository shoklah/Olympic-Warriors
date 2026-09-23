import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';
import { localeFrom } from '$lib/i18n/locale.js';
import { TOKEN_COOKIE } from '$lib/session';

/**
 * Whether the token cookie belongs to a staff user. A dead token (401/403) is dropped;
 * any other failure (API down) keeps it and counts as a visitor for this request.
 */
async function resolveOrganiser(fetch, cookies) {
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) return false;
	try {
		const user = await apiGet(fetch, api('/user/current/'), token);
		return Boolean(user?.is_staff);
	} catch (err) {
		if (err?.status === 401 || err?.status === 403) cookies.delete(TOKEN_COOKIE, { path: '/' });
		return false;
	}
}

/** Every active edition, newest first, with only the fields the nav and hub need. */
async function loadEditions(fetch) {
	return (await apiGet(fetch, api('/editions/')))
		.map(({ id, year, host, photos_url }) => ({ id, year, host, photos_url }))
		.sort((a, b) => b.year - a.year);
}

/**
 * Every active edition, newest first, plus the year the bare URLs default to, the
 * visitor's language from the `lang` cookie (French unless they switched) and whether
 * they are an organiser. Only the fields the nav and hub need ride along.
 */
export const load = async ({ fetch, cookies }) => {
	const [editions, organiser] = await Promise.all([loadEditions(fetch), resolveOrganiser(fetch, cookies)]);
	return {
		editions,
		latestYear: editions[0]?.year ?? null,
		locale: localeFrom(cookies.get('lang')),
		organiser
	};
};
