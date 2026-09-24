import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';
import { localeFrom } from '$lib/i18n/locale.js';
import { TOKEN_COOKIE } from '$lib/session';

const VISITOR = { organiser: false, me: null };

/**
 * Who the token cookie belongs to, from `/me/`: whether they are an organiser (`is_staff`)
 * and `me`, the few fields the pages need (`id`, `first_name`, `photo` as `{ large, small }`
 * or null, `is_person`). The rest of `/me/` stays here: no page needs it, and layout data is
 * serialised into every page. A dead token (401/403) is dropped; any other
 * failure (API down, a body that is not the expected object) keeps it and counts as a
 * visitor for this request.
 */
async function resolveViewer(fetch, cookies) {
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) return VISITOR;
	try {
		const user = await apiGet(fetch, api('/me/'), token);
		if (typeof user !== 'object' || user === null || user.id == null) return VISITOR;
		const { id, first_name, photo, is_person } = user;
		return {
			organiser: Boolean(user.is_staff),
			me: { id, first_name: first_name ?? '', photo: photo ?? null, is_person: Boolean(is_person) }
		};
	} catch (err) {
		if (err?.status === 401 || err?.status === 403) cookies.delete(TOKEN_COOKIE, { path: '/' });
		return VISITOR;
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
 * visitor's language from the `lang` cookie (French unless they switched), whether they
 * are an organiser and who is logged in (`me`). Only the fields the nav and hub need ride along.
 */
export const load = async ({ fetch, cookies }) => {
	const [editions, { organiser, me }] = await Promise.all([
		loadEditions(fetch),
		resolveViewer(fetch, cookies)
	]);
	return {
		editions,
		latestYear: editions[0]?.year ?? null,
		locale: localeFrom(cookies.get('lang')),
		organiser,
		me
	};
};
