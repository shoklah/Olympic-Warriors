import { error } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import {
	ALL_TIME_TAB,
	disciplineEntries,
	disciplinePath,
	disciplineResults,
	disciplineSchedule,
	findDiscipline
} from '$lib/edition';

/**
 * The discipline out of the year's summary, and on the « Palmarès » tab only, its all-time
 * table from the page's JSON endpoint (all-time.json). The edition tab, the busiest page on
 * event day, renders from the summary alone, with no request: a server load here would
 * cost a round trip on every visit.
 */
export const load = async ({ fetch, params, parent, url }) => {
	const { summary } = await parent();
	const discipline = findDiscipline(summary, Number(params.id));
	if (!discipline) error(404, 'Discipline not found');
	const allTime = url.searchParams.get('tab') === ALL_TIME_TAB;
	const path = disciplinePath(summary.edition.year, discipline.id);
	return {
		tab: allTime ? ALL_TIME_TAB : 'edition',
		allTime: allTime ? await apiGet(fetch, `${path}/all-time.json`) : null,
		discipline,
		results: disciplineResults(summary, discipline.id),
		schedule: disciplineSchedule(summary, discipline.id),
		entries: disciplineEntries(summary, discipline.id)
	};
};
