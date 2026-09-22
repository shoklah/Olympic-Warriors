import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/**
 * Every active edition, newest first, plus the year the bare URLs default to.
 * Only the fields the nav and hub need, so nothing else rides along in the hydration data.
 */
export const load = async ({ fetch }) => {
	const editions = (await apiGet(fetch, api('/editions/')))
		.map(({ id, year, host, photos_url }) => ({ id, year, host, photos_url }))
		.sort((a, b) => b.year - a.year);
	return { editions, latestYear: editions[0]?.year ?? null };
};
