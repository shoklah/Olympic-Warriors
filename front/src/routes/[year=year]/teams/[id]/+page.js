import { error } from '@sveltejs/kit';
import { findTeam, teamResults } from '$lib/edition';

export const load = async ({ params, parent }) => {
	const { summary } = await parent();
	const team = findTeam(summary, Number(params.id));
	if (!team) error(404, 'Team not found');
	return { team, results: teamResults(summary, team.id) };
};
