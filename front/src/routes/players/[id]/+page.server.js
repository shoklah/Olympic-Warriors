import { error } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/**
 * One person's profile by user id. Only a canonical decimal integer reaches the API: the id
 * is spliced into an API path, a decoded `..` could otherwise walk to another endpoint, a
 * leading zero would give the same player two URLs (`/players/0055` and `/players/55`), and
 * the digit run is capped so an absurdly long string is refused up front. The API's 404
 * (unknown id, or a user who never played) becomes the error page through apiGet.
 */
export const load = async ({ fetch, params }) => {
	if (!/^[1-9]\d{0,9}$/.test(params.id)) error(404, 'No such player');
	return { profile: await apiGet(fetch, api(`/profile/${params.id}/`)) };
};
