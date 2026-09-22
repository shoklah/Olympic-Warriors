import { error } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/** The whole edition in one payload; every page under /<year> reads it via parent(). */
export const load = async ({ fetch, params }) => {
	try {
		const summary = await apiGet(fetch, api(`/edition/year/${params.year}/summary/`));
		return { summary };
	} catch (err) {
		if (err?.status === 404) error(404, `No edition in ${params.year}`);
		throw err;
	}
};
