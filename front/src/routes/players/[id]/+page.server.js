import { error } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/**
 * One person's profile by user id. Only digits reach the API: the id is spliced into an
 * API path, and a decoded `..` could otherwise walk to another endpoint. The API's 404
 * (unknown id, or a user who never played) becomes the error page through apiGet.
 */
export const load = async ({ fetch, params }) => {
	if (!/^\d+$/.test(params.id)) error(404, 'No such player');
	return { profile: await apiGet(fetch, api(`/profile/${params.id}/`)) };
};
