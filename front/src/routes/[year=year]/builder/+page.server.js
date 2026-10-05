import { error, redirect } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE } from '$lib/session';

/** The team builder: organisers only, the latest edition only, never cached (private answers). */
export const load = async ({ params, cookies, fetch, parent, setHeaders }) => {
	const { organiser, latestYear } = await parent();
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) redirect(303, `/login?next=/${params.year}/builder`);
	if (!organiser) error(403, 'Organisers only');
	if (Number(params.year) !== latestYear) error(404, `No builder for ${params.year}`);
	setHeaders({ 'cache-control': 'private, no-store' });
	return { builder: await apiGet(fetch, api(`/builder/${params.year}/`), token) };
};
