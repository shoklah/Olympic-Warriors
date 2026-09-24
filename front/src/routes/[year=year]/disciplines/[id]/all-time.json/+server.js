import { error, json } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/**
 * A discipline's all-time table (GET /discipline/<id>/all-time/), for the discipline
 * page's « Palmarès » tab: its universal load fetches this only on that tab, since API_URL
 * is server-only. The table does not depend on the year. Only a canonical id reaches the
 * API, since it is spliced into the API path.
 */
export const GET = async ({ fetch, params }) => {
	if (!/^[1-9]\d{0,9}$/.test(params.id)) error(404, 'No such discipline');
	return json(await apiGet(fetch, api(`/discipline/${params.id}/all-time/`)));
};
