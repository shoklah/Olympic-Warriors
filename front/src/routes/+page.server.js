import { error } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/** The bare URL shows the latest edition's hub without changing the address. */
export const load = async ({ fetch, parent }) => {
	const { latestYear } = await parent();
	if (latestYear === null) error(404, 'No edition yet');
	const summary = await apiGet(fetch, api(`/edition/year/${latestYear}/summary/`));
	return { summary };
};
