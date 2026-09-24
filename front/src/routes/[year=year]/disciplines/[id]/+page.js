import { error } from '@sveltejs/kit';
import { disciplineEntries, disciplineResults, disciplineSchedule, findDiscipline } from '$lib/edition';

/** `data` is the server load's (the tab and the all-time table): SvelteKit hands it over
    but does not merge it into what this load returns. */
export const load = async ({ params, parent, data }) => {
	const { summary } = await parent();
	const discipline = findDiscipline(summary, Number(params.id));
	if (!discipline) error(404, 'Discipline not found');
	return {
		...data,
		discipline,
		results: disciplineResults(summary, discipline.id),
		schedule: disciplineSchedule(summary, discipline.id),
		entries: disciplineEntries(summary, discipline.id)
	};
};
