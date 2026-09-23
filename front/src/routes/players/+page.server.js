import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/** The all-time leaderboard, in the order the API ranks it (the page never re-sorts). */
export const load = async ({ fetch }) => ({ players: await apiGet(fetch, api('/profiles/')) });
