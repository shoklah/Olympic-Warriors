import { error, redirect } from '@sveltejs/kit';

export const load = async ({ parent }) => {
	const { latestYear } = await parent();
	if (latestYear === null) error(404, 'No edition yet');
	redirect(301, `/${latestYear}/teams`);
};
