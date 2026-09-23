import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';
import { localeFrom } from '$lib/i18n/locale.js';

/**
 * Every active edition, newest first, plus the year the bare URLs default to, and
 * the visitor's language from the `lang` cookie (French unless they switched).
 * Only the fields the nav and hub need, so nothing else rides along in the hydration data.
 */
export const load = async ({ fetch, cookies }) => {
	const editions = (await apiGet(fetch, api('/editions/')))
		.map(({ id, year, host, photos_url }) => ({ id, year, host, photos_url }))
		.sort((a, b) => b.year - a.year);
	return { editions, latestYear: editions[0]?.year ?? null, locale: localeFrom(cookies.get('lang')) };
};
