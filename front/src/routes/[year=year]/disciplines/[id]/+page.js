import { error } from '@sveltejs/kit';
import { disciplineResults, disciplineSchedule, findDiscipline } from '$lib/edition';

export const load = async ({ params, parent }) => {
	const { summary } = await parent();
	const discipline = findDiscipline(summary, Number(params.id));
	if (!discipline) error(404, 'Discipline not found');
	return {
		discipline,
		results: disciplineResults(summary, discipline.id),
		schedule: disciplineSchedule(summary, discipline.id)
	};
};
