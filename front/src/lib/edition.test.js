import { describe, expect, it } from 'vitest';
import {
	countdownParts,
	disciplineResults,
	disciplineSchedule,
	editionPhase,
	findDiscipline,
	findTeam,
	formatDateRange,
	formatDifference,
	rankedTeams,
	startInstant,
	switchYearPath,
	teamGames,
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

	it('sorts two unranked rows after the ranked one, by name', () => {
		const partial = {
			...summary,
			results: summary.results.map((r) =>
				r.id === 100 || r.id === 102
					? { ...r, ranking: null, points: null, points_difference: null, global_points: null }
					: r
			)
		};
		expect(disciplineResults(partial, 10).map((r) => r.teamName)).toEqual(['Bisons', 'Aigles', 'Cerfs']);
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

describe('startInstant', () => {
	it('anchors to 09:00 Europe/Paris (CEST, UTC+2) for the fixture edition', () => {
		expect(startInstant(summary.edition).toISOString()).toBe('2026-09-19T07:00:00.000Z');
	});

	it('anchors to 09:00 Europe/Paris (CET, UTC+1) in winter', () => {
		expect(startInstant({ start_date: '2026-01-10' }).toISOString()).toBe('2026-01-10T08:00:00.000Z');
	});
});

describe('editionPhase', () => {
	it('is upcoming before 09:00 Europe/Paris on start_date', () => {
		expect(editionPhase(summary.edition, new Date('2026-09-19T06:59:00Z'))).toBe('upcoming');
	});

	it('is started from 09:00 Europe/Paris on start_date', () => {
		expect(editionPhase(summary.edition, new Date('2026-09-19T07:00:00Z'))).toBe('started');
	});

	it('is started long after', () => {
		expect(editionPhase(summary.edition, new Date('2027-01-01T00:00:00Z'))).toBe('started');
	});
});

describe('countdownParts', () => {
	it('splits the remaining time', () => {
		expect(countdownParts(summary.edition, new Date('2026-09-17T05:58:30Z'))).toEqual({
			days: 2,
			hours: 1,
			minutes: 1,
			seconds: 30
		});
	});

	it('is all zeros once started', () => {
		expect(countdownParts(summary.edition, new Date('2026-09-19T07:00:01Z'))).toEqual({
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

describe('formatDateRange', () => {
	it('prints one date for a single-day edition', () => {
		expect(formatDateRange('2026-09-19', '2026-09-19')).toBe('19 September 2026');
	});

	it('names the month once within a month', () => {
		expect(formatDateRange('2026-09-19', '2026-09-20')).toBe('19 – 20 September 2026');
	});

	it('names both months across a month boundary', () => {
		expect(formatDateRange('2026-09-30', '2026-10-01')).toBe('30 September – 1 October 2026');
	});
});

describe('disciplineSchedule', () => {
	it('groups games by round in order with names joined', () => {
		const rounds = disciplineSchedule(summary, 10);
		expect(rounds.map((r) => [r.order, r.isOver, r.games.length])).toEqual([
			[0, true, 2],
			[1, false, 1]
		]);
		expect(rounds[0].games[0]).toEqual({
			id: 200,
			team1Id: 2,
			team1Name: 'Bisons',
			team2Id: 1,
			team2Name: 'Aigles',
			refereeName: 'Cerfs',
			isPlayed: true,
			score1: 12,
			score2: 9
		});
	});

	it('keeps null scores for an unrevealed discipline', () => {
		const [round] = disciplineSchedule(summary, 11);
		expect(round.games[0]).toMatchObject({ team1Name: 'Aigles', team2Name: 'Bisons', isPlayed: true, score1: null, score2: null });
	});

	it('is null for a discipline without rounds', () => {
		expect(disciplineSchedule({ ...summary, rounds: [], games: [] }, 10)).toBeNull();
		expect(disciplineSchedule(summary, 999)).toBeNull();
	});

	it('names an unknown team Unknown', () => {
		const odd = { ...summary, games: [{ ...summary.games[0], referees: 42 }] };
		expect(disciplineSchedule(odd, 10)[0].games[0].refereeName).toBe('Unknown');
	});

	it('includes a round with no games as an empty entry', () => {
		const withEmptyRound = {
			...summary,
			rounds: [...summary.rounds, { id: 23, discipline: 10, order: 2, is_over: false }]
		};
		const rounds = disciplineSchedule(withEmptyRound, 10);
		expect(rounds[2]).toEqual({ order: 2, isOver: false, games: [] });
	});
});

describe('teamGames', () => {
	it('lists play and referee rows per discipline, own score first', () => {
		const [relay, orienteering] = teamGames(summary, 1);
		expect(relay.disciplineName).toBe('Relay');
		expect(relay.games).toEqual([
			{ id: 200, round: 0, role: 'play', opponentId: 2, opponentName: 'Bisons', team1Name: 'Bisons', team2Name: 'Aigles', isPlayed: true, ownScore: 9, theirScore: 12, result: 'loss' },
			{ id: 201, round: 0, role: 'referee', opponentId: null, opponentName: null, team1Name: 'Cerfs', team2Name: 'Bisons', isPlayed: false, ownScore: null, theirScore: null, result: null },
			{ id: 202, round: 1, role: 'play', opponentId: 3, opponentName: 'Cerfs', team1Name: 'Aigles', team2Name: 'Cerfs', isPlayed: true, ownScore: 7, theirScore: 7, result: 'draw' }
		]);
		expect(orienteering.games[0]).toMatchObject({ role: 'play', opponentName: 'Bisons', isPlayed: true, ownScore: null, result: null });
	});

	it('reports a win and an unplayed game', () => {
		const [relay] = teamGames(summary, 2);
		expect(relay.games.map((g) => [g.role, g.isPlayed, g.result])).toEqual([
			['play', true, 'win'],
			['play', false, null],
			['referee', true, null]
		]);
	});

	it('omits disciplines where the team has no game', () => {
		const none = { ...summary, games: summary.games.filter((g) => g.discipline !== 11) };
		expect(teamGames(none, 3).map((d) => d.disciplineName)).toEqual(['Relay']);
	});

	it('returns an empty array for an unknown team', () => {
		expect(teamGames(summary, 999)).toEqual([]);
	});

	it('treats a team that is both player and referee in one game as playing', () => {
		const odd = { ...summary, games: [{ ...summary.games[0], referees: 2 }] };
		const [discipline] = teamGames(odd, 2);
		expect(discipline.games).toHaveLength(1);
		expect(discipline.games[0].role).toBe('play');
	});
});
