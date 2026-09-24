import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/**
 * Every discipline ever held, for the deck under this edition's disciplines; the edition's
 * own come from the layout's summary. It reads no param, so switching years reuses it.
 */
export const load = async ({ fetch }) => ({ held: await apiGet(fetch, api('/disciplines/all-time/')) });
