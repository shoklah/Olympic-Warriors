import { describe, expect, it } from 'vitest';
import {
	countdownParts,
	disciplineResults,
	editionPhase,
	findDiscipline,
	findTeam,
	formatDifference,
	rankedTeams,
	switchYearPath,
	teamResults
} from './edition.js';
import { summary, summaryAllRevealed } from './fixtures/summary.js';

describe('rankedTeams', () => {
	it('sorts by ranking then name', () => {
		expect(rankedTeams(summary).map((t) => t.name)).toEqual(['Bisons', 'Aigles', 'Cerfs']);
	});

	it('keeps tied teams in name order', () => {
		const tied = {
			...summary,
			teams: [
				{ ...summary.teams[2], ranking: 1 },
				{ ...summary.teams[0], ranking: 1 },
				{ ...summary.teams[1], ranking: 3 }
			]
		};
		expect(rankedTeams(tied).map((t) => t.name)).toEqual(['Aigles', 'Cerfs', 'Bisons']);
	});

	it('does not mutate the summary', () => {
		rankedTeams(summary);
		expect(summary.teams[0].name).toBe('Aigles');
	});
});

describe('disciplineResults', () => {
	it('returns rows in rank order with the team name joined', () => {
		const rows = disciplineResults(summary, 10);
		expect(rows.map((r) => [r.ranking, r.teamName, r.points, r.points_difference])).toEqual([
			[1, 'Bisons', 10, 4],
			[2, 'Aigles', 5, -2],
			[3, 'Cerfs', 0, -2]
		]);
	});

	it('returns null for an unrevealed discipline', () => {
		expect(disciplineResults(summary, 11)).toBeNull();
	});

	it('returns timed rows for a revealed timed discipline', () => {
		const rows = disciplineResults(summaryAllRevealed, 11);
		expect(rows.map((r) => [r.ranking, r.teamName, r.time])).toEqual([
			[1, 'Aigles', '00:12:30'],
			[2, 'Cerfs', '00:13:45'],
			[3, 'Bisons', '00:15:02']
		]);
	});

	it('returns null for an unknown discipline', () => {
		expect(disciplineResults(summary, 999)).toBeNull();
	});

	it('sorts a row without a score last', () => {
		const partial = {
			...summary,
			results: summary.results.map((r) =>
				r.id === 101 ? { ...r, ranking: null, points: null, points_difference: null, global_points: null } : r
			)
		};
		expect(disciplineResults(partial, 10).map((r) => r.teamName)).toEqual(['Aigles', 'Cerfs', 'Bisons']);
	});
});

describe('teamResults', () => {
	it('gives one row per discipline in id order', () => {
		expect(teamResults(summary, 1)).toEqual([
			{
				disciplineId: 10,
				disciplineName: 'Relay',
				result_type: 'PTS',
				revealed: true,
				ranking: 2,
				points: 5,
				time: null
			},
			{
				disciplineId: 11,
				disciplineName: 'Orienteering',
				result_type: 'TIM',
				revealed: false,
				ranking: null,
				points: null,
				time: null
			}
		]);
	});

	it('marks a discipline the team has no result in as unrevealed', () => {
		const missing = { ...summary, results: summary.results.filter((r) => r.team !== 1) };
		expect(teamResults(missing, 1).map((r) => r.revealed)).toEqual([false, false]);
	});
});

describe('findTeam / findDiscipline', () => {
	it('find by numeric id', () => {
		expect(findTeam(summary, 2).name).toBe('Bisons');
		expect(findDiscipline(summary, 11).name).toBe('Orienteering');
	});

	it('return null when missing', () => {
		expect(findTeam(summary, 42)).toBeNull();
		expect(findDiscipline(summary, 42)).toBeNull();
	});
});

describe('editionPhase', () => {
	it('is upcoming before 09:00 on start_date', () => {
		expect(editionPhase(summary.edition, new Date(2026, 8, 19, 8, 59))).toBe('upcoming');
	});

	it('is started from 09:00 on start_date', () => {
		expect(editionPhase(summary.edition, new Date(2026, 8, 19, 9, 0))).toBe('started');
	});

	it('is started long after', () => {
		expect(editionPhase(summary.edition, new Date(2027, 0, 1))).toBe('started');
	});
});

describe('countdownParts', () => {
	it('splits the remaining time', () => {
		expect(countdownParts(summary.edition, new Date(2026, 8, 17, 7, 58, 30))).toEqual({
			days: 2,
			hours: 1,
			minutes: 1,
			seconds: 30
		});
	});

	it('is all zeros once started', () => {
		expect(countdownParts(summary.edition, new Date(2026, 8, 19, 9, 0, 1))).toEqual({
			days: 0,
			hours: 0,
			minutes: 0,
			seconds: 0
		});
	});
});

describe('formatDifference', () => {
	it('signs positives, keeps zero and negatives', () => {
		expect(formatDifference(3)).toBe('+3');
		expect(formatDifference(0)).toBe('0');
		expect(formatDifference(-2)).toBe('-2');
	});
});

describe('switchYearPath', () => {
	it('replaces the year segment and keeps the section', () => {
		expect(switchYearPath('/2026/teams', 2025)).toBe('/2025/teams');
		expect(switchYearPath('/2026/disciplines/12', 2025)).toBe('/2025/disciplines');
		expect(switchYearPath('/2026/teams/3', 2025)).toBe('/2025/teams');
		expect(switchYearPath('/2026', 2025)).toBe('/2025');
	});

	it('goes to the hub from a non-edition page', () => {
		expect(switchYearPath('/', 2025)).toBe('/2025');
		expect(switchYearPath('/login', 2025)).toBe('/2025');
	});
});
