import { describe, expect, it } from 'vitest';
import {
	countdownParts,
	disciplineEntries,
	disciplineResults,
	disciplineSchedule,
	disciplineSubtitle,
	editionPhase,
	entryTime,
	findDiscipline,
	findTeam,
	formatDateRange,
	formatDifference,
	formatTime,
	ordinal,
	rankedTeams,
	roundCount,
	startInstant,
	switchYearPath,
	ALL_TIME_TAB,
	disciplinePath,
	teamGames,
	teamResults
} from './edition.js';
import { summary, summaryAllRevealed, summaryManual, summaryStaff } from './fixtures/summary.js';

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

	it('sorts an unranked team last', () => {
		expect(rankedTeams(summaryManual).map((t) => [t.name, t.ranking])).toEqual([
			['Bisons', 1],
			['Aigles', 2],
			['Cerfs', null]
		]);
	});

	it('keeps two unranked teams in name order after the ranked ones', () => {
		const twoUnranked = {
			...summaryManual,
			teams: summaryManual.teams.map((t) => (t.name === 'Aigles' ? { ...t, ranking: null } : t))
		};
		expect(rankedTeams(twoUnranked).map((t) => t.name)).toEqual(['Bisons', 'Aigles', 'Cerfs']);
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

describe('ordinal', () => {
	it('suffixes the usual English ranks', () => {
		expect(ordinal(1, 'en')).toBe('1st');
		expect(ordinal(2, 'en')).toBe('2nd');
		expect(ordinal(3, 'en')).toBe('3rd');
		expect(ordinal(4, 'en')).toBe('4th');
	});

	it('keeps the English teens in th', () => {
		expect(ordinal(11, 'en')).toBe('11th');
		expect(ordinal(12, 'en')).toBe('12th');
		expect(ordinal(13, 'en')).toBe('13th');
	});

	it('suffixes above twenty and above a hundred in English', () => {
		expect(ordinal(21, 'en')).toBe('21st');
		expect(ordinal(22, 'en')).toBe('22nd');
		expect(ordinal(23, 'en')).toBe('23rd');
		expect(ordinal(101, 'en')).toBe('101st');
		expect(ordinal(111, 'en')).toBe('111th');
	});

	it('writes French ranks for a team: 1re then Ne', () => {
		expect(ordinal(1, 'fr')).toBe('1re');
		expect(ordinal(2, 'fr')).toBe('2e');
		expect(ordinal(3, 'fr')).toBe('3e');
		expect(ordinal(11, 'fr')).toBe('11e');
		expect(ordinal(21, 'fr')).toBe('21e');
	});

	it('falls back to French for an unknown locale', () => {
		expect(ordinal(2, 'de')).toBe('2e');
		expect(ordinal(2)).toBe('2e');
	});
});

describe('switchYearPath', () => {
	it('replaces the year segment and keeps the section', () => {
		expect(switchYearPath('/2026/teams', 2025)).toBe('/2025/ranking');
		expect(switchYearPath('/2026/disciplines/12', 2025)).toBe('/2025/disciplines');
		expect(switchYearPath('/2026/teams/3', 2025)).toBe('/2025/ranking');
		expect(switchYearPath('/2026', 2025)).toBe('/2025');
	});

	it('goes to the hub from a non-edition page', () => {
		expect(switchYearPath('/', 2025)).toBe('/2025');
		expect(switchYearPath('/login', 2025)).toBe('/2025');
	});
});

describe('formatDateRange', () => {
	it('prints one date for a single-day edition', () => {
		expect(formatDateRange('2026-09-19', '2026-09-19', 'en')).toBe('19 September 2026');
		expect(formatDateRange('2026-09-19', '2026-09-19', 'fr')).toBe('19 septembre 2026');
	});

	it('names the month once within a month', () => {
		expect(formatDateRange('2026-09-19', '2026-09-20', 'en')).toBe('19 – 20 September 2026');
		expect(formatDateRange('2026-09-19', '2026-09-20', 'fr')).toBe('19 – 20 septembre 2026');
	});

	it('names both months across a month boundary', () => {
		expect(formatDateRange('2026-09-30', '2026-10-01', 'en')).toBe('30 September – 1 October 2026');
		expect(formatDateRange('2026-09-30', '2026-10-01', 'fr')).toBe('30 septembre – 1er octobre 2026');
		expect(formatDateRange('2026-10-01', '2026-10-01', 'fr')).toBe('1er octobre 2026');
		expect(formatDateRange('2026-10-01', '2026-10-02', 'fr')).toBe('1er – 2 octobre 2026');
	});

	it('falls back to French for an unknown locale', () => {
		expect(formatDateRange('2026-09-19', '2026-09-19', 'de')).toBe('19 septembre 2026');
		expect(formatDateRange('2026-09-19', '2026-09-19')).toBe('19 septembre 2026');
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

	it('gives a null name to an unknown or missing referee', () => {
		const odd = { ...summary, games: [{ ...summary.games[0], referees: 42 }] };
		expect(disciplineSchedule(odd, 10)[0].games[0].refereeName).toBeNull();
		const none = { ...summary, games: [{ ...summary.games[0], referees: null }] };
		expect(disciplineSchedule(none, 10)[0].games[0].refereeName).toBeNull();
	});

	it('includes a round with no games as an empty entry', () => {
		const withEmptyRound = {
			...summary,
			rounds: [...summary.rounds, { id: 23, discipline: 10, order: 2, is_over: false }]
		};
		const rounds = disciplineSchedule(withEmptyRound, 10);
		expect(rounds[2]).toEqual({ id: 23, order: 2, isOver: false, games: [] });
	});
});

describe('disciplineSubtitle', () => {
	it('counts the rounds and the games of the discipline', () => {
		expect(disciplineSubtitle(summary, summary.disciplines[0])).toEqual({ rounds: 2, games: 3 });
		expect(disciplineSubtitle(summary, summary.disciplines[1])).toEqual({ rounds: 1, games: 1 });
	});

	it('counts the games even when the discipline has none yet', () => {
		const noGames = { ...summary, games: summary.games.filter((g) => g.discipline !== 10) };
		expect(disciplineSubtitle(noGames, summary.disciplines[0])).toEqual({ rounds: 2, games: 0 });
	});

	it('gives the result type when the discipline has no round', () => {
		const noRounds = { ...summary, rounds: [], games: [] };
		expect(disciplineSubtitle(noRounds, { id: 10, result_type: 'PTS' })).toEqual({ resultType: 'PTS' });
		expect(disciplineSubtitle(noRounds, { id: 10, result_type: 'TIM' })).toEqual({ resultType: 'TIM' });
		expect(disciplineSubtitle(noRounds, { id: 10, result_type: 'NON' })).toEqual({ resultType: 'NON' });
	});

	it('ignores reveal_score', () => {
		const hidden = { ...summary.disciplines[0], reveal_score: false };
		expect(disciplineSubtitle(summary, hidden)).toEqual({ rounds: 2, games: 3 });
	});
});

describe('roundCount', () => {
	const round = (...played) => ({ games: played.map((isPlayed) => ({ isPlayed })) });

	it('counts the games and what is left to play', () => {
		expect(roundCount(round(true, true, true))).toEqual({ left: 0, total: 3 });
		expect(roundCount(round(true))).toEqual({ left: 0, total: 1 });
		expect(roundCount(round(true, false, false))).toEqual({ left: 2, total: 3 });
	});
});

describe('teamGames', () => {
	it('lists the games the team played per discipline, in round order, referee named', () => {
		const [relay, orienteering] = teamGames(summary, 1);
		expect(relay.disciplineName).toBe('Relay');
		expect(relay.games).toEqual([
			{ id: 200, round: 0, team1Id: 2, team2Id: 1, team1Name: 'Bisons', team2Name: 'Aigles', refereeName: 'Cerfs', isPlayed: true, score1: 12, score2: 9 },
			{ id: 202, round: 1, team1Id: 1, team2Id: 3, team1Name: 'Aigles', team2Name: 'Cerfs', refereeName: 'Bisons', isPlayed: true, score1: 7, score2: 7 }
		]);
		expect(orienteering.games).toEqual([
			{ id: 203, round: 0, team1Id: 1, team2Id: 2, team1Name: 'Aigles', team2Name: 'Bisons', refereeName: 'Cerfs', isPlayed: true, score1: null, score2: null }
		]);
	});

	it('leaves out the games the team only referees', () => {
		expect(teamGames(summary, 1).flatMap((d) => d.games.map((g) => g.id))).not.toContain(201);
		const [relay] = teamGames(summary, 3);
		expect(relay.games.map((g) => g.id)).toEqual([201, 202]);
	});

	it('omits disciplines where the team has no game', () => {
		// Cerfs only referee the Orienteering game, so that discipline is not listed for them.
		expect(teamGames(summary, 3).map((d) => d.disciplineName)).toEqual(['Relay']);
		const none = { ...summary, games: summary.games.filter((g) => g.discipline !== 11) };
		expect(teamGames(none, 1).map((d) => d.disciplineName)).toEqual(['Relay']);
	});

	it('returns an empty array for an unknown team', () => {
		expect(teamGames(summary, 999)).toEqual([]);
	});

	it('keeps a game whose referee is unknown, with a null name', () => {
		const odd = { ...summary, games: [{ ...summary.games[0], referees: 42 }] };
		expect(teamGames(odd, 2)[0].games[0].refereeName).toBeNull();
	});

	it('gives no round to a game whose round is not in the summary, sorted last', () => {
		const odd = { ...summary, games: [...summary.games, { ...summary.games[0], id: 299, round: 99 }] };
		const [relay] = teamGames(odd, 2);
		expect(relay.games.map((g) => [g.id, g.round])).toEqual([[200, 0], [201, 0], [299, null]]);
	});

	it('lists a game the team both plays and referees once, as played', () => {
		const odd = { ...summary, games: [{ ...summary.games[0], referees: 2 }] };
		const [relay] = teamGames(odd, 2);
		expect(relay.games).toHaveLength(1);
		expect(relay.games[0].refereeName).toBe('Bisons');
	});
});

describe('formatTime', () => {
	it('drops zero hours and keeps them otherwise', () => {
		expect(formatTime('00:13:15')).toBe('13:15');
		expect(formatTime('01:02:03')).toBe('1:02:03');
		expect(formatTime('00:00:07')).toBe('00:07');
		expect(formatTime(null)).toBeNull();
	});
});

describe('entryTime', () => {
	it('gives the mm:ss the field and the API accept, minutes above 59 included', () => {
		expect(entryTime('00:13:15')).toBe('13:15');
		expect(entryTime('01:02:03')).toBe('62:03');
		expect(entryTime('00:00:07')).toBe('0:07');
		expect(entryTime(null)).toBeNull();
		expect(entryTime(undefined)).toBeNull();
	});
});

describe('disciplineEntries', () => {
	it('lists one line per team with the stored value, by name while hidden', () => {
		expect(disciplineEntries(summaryStaff, 12)).toEqual([
			{ id: 106, team: 1, teamName: 'Aigles', points: 20, time: null, ranking: null },
			{ id: 107, team: 2, teamName: 'Bisons', points: null, time: null, ranking: null },
			{ id: 108, team: 3, teamName: 'Cerfs', points: 15, time: null, ranking: null }
		]);
	});

	it('orders by rank once revealed', () => {
		expect(disciplineEntries(summaryAllRevealed, 11).map((e) => e.teamName)).toEqual([
			'Aigles',
			'Cerfs',
			'Bisons'
		]);
	});

	it('is empty for an unknown discipline', () => {
		expect(disciplineEntries(summaryStaff, 99)).toEqual([]);
	});
});

describe('disciplinePath', () => {
	it('points to the edition tab by default and to the all-time tab on request', () => {
		expect(disciplinePath(2026, 10)).toBe('/2026/disciplines/10');
		expect(disciplinePath(2025, 3, true)).toBe(`/2025/disciplines/3?tab=${ALL_TIME_TAB}`);
		expect(ALL_TIME_TAB).toBe('all-time');
	});
});
