import { error } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE } from '$lib/session';

/**
 * The whole edition in one payload; every page under /<year> reads it via parent().
 * An organiser fetches it with their token (hidden scores included) and may edit the
 * latest edition only.
 */
export const load = async ({ fetch, cookies, params, parent }) => {
	const { organiser, latestYear } = await parent();
	const token = organiser ? (cookies.get(TOKEN_COOKIE) ?? null) : null;
	try {
		const summary = await apiGet(fetch, api(`/edition/year/${params.year}/summary/`), token);
		return { summary, editable: organiser && Number(params.year) === latestYear };
	} catch (err) {
		if (err?.status === 404) error(404, `No edition in ${params.year}`);
		throw err;
	}
};
