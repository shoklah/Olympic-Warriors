import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/** Every active edition, newest first, plus the year the bare URLs default to. */
export const load = async ({ fetch }) => {
	const editions = (await apiGet(fetch, api('/editions/'))).sort((a, b) => b.year - a.year);
	return { editions, latestYear: editions[0]?.year ?? null };
};
