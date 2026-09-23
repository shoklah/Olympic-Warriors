import { redirect } from '@sveltejs/kit';

/** The teams grid merged into the ranking page (same rows, plus the rosters); old links land there. */
export const load = ({ params }) => {
	redirect(302, `/${params.year}/ranking`);
};
