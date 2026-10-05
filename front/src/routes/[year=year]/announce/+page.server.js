import { error, redirect } from '@sveltejs/kit';
import { TOKEN_COOKIE } from '$lib/session';

/**
 * The announcement visuals: organisers only, the latest edition only, never cached. It reads
 * the summary the year layout already loads, so it fetches nothing itself.
 */
export const load = async ({ params, cookies, parent, setHeaders }) => {
	const { organiser, latestYear } = await parent();
	if (!cookies.get(TOKEN_COOKIE)) redirect(303, `/login?next=/${params.year}/announce`);
	if (!organiser) error(403, 'Organisers only');
	if (Number(params.year) !== latestYear) error(404, `No announcement for ${params.year}`);
	setHeaders({ 'cache-control': 'private, no-store' });
	return {};
};
