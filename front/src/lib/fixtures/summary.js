/**
 * One edition as the summary endpoint returns it: a revealed points discipline (Relay),
 * a hidden timed one (Orienteering), three teams. Bisons lead, Aigles second, Cerfs last.
 * Roster players carry `photo`, the small URL or null: Ana has one, Bob and Chloé don't.
 */
export const summary = {
	edition: {
		id: 1,
		year: 2026,
		host: 'Paris',
		start_date: '2026-09-19',
		end_date: '2026-09-20',
		photos_url: null
	},
	disciplines: [
		{ id: 10, name: 'Relay', result_type: 'PTS', reveal_score: true, pairing_system: 'RR' },
		{ id: 11, name: 'Orienteering', result_type: 'TIM', reveal_score: false, pairing_system: 'SW' }
	],
	teams: [
		{
			id: 1,
			name: 'Aigles',
			ranking: 2,
			total_points: 3,
			players: [
				{ id: 1, user: 11, first_name: 'Ana', last_name: 'Lopez', photo: '/media/avatars/11-7c3e9a1f5b2d-sm.webp' },
				{ id: 2, user: 12, first_name: 'Bob', last_name: 'Martin', photo: null }
			]
		},
		{
			id: 2,
			name: 'Bisons',
			ranking: 1,
			total_points: 5,
			players: [{ id: 3, user: 13, first_name: 'Chloé', last_name: 'Nguyen', photo: null }]
		},
		{ id: 3, name: 'Cerfs', ranking: 3, total_points: 2, players: [] }
	],
	results: [
		{ id: 100, team: 1, discipline: 10, result_type: 'PTS', ranking: 2, points: 5, time: null, points_difference: -2, global_points: 3 },
		{ id: 101, team: 2, discipline: 10, result_type: 'PTS', ranking: 1, points: 10, time: null, points_difference: 4, global_points: 5 },
		{ id: 102, team: 3, discipline: 10, result_type: 'PTS', ranking: 3, points: 0, time: null, points_difference: -2, global_points: 2 },
		{ id: 103, team: 1, discipline: 11, result_type: 'TIM', ranking: null, points: null, time: null, points_difference: null, global_points: null },
		{ id: 104, team: 2, discipline: 11, result_type: 'TIM', ranking: null, points: null, time: null, points_difference: null, global_points: null },
		{ id: 105, team: 3, discipline: 11, result_type: 'TIM', ranking: null, points: null, time: null, points_difference: null, global_points: null }
	],
	rounds: [
		{ id: 20, discipline: 10, order: 0, is_over: true },
		{ id: 21, discipline: 10, order: 1, is_over: false },
		{ id: 22, discipline: 11, order: 0, is_over: false }
	],
	games: [
		{ id: 200, discipline: 10, round: 20, team1: 2, team2: 1, referees: 3, is_played: true, score1: 12, score2: 9 },
		{ id: 201, discipline: 10, round: 20, team1: 3, team2: 2, referees: 1, is_played: false, score1: 0, score2: 0 },
		{ id: 202, discipline: 10, round: 21, team1: 1, team2: 3, referees: 2, is_played: true, score1: 7, score2: 7 },
		{ id: 203, discipline: 11, round: 22, team1: 1, team2: 2, referees: 3, is_played: true, score1: null, score2: null }
	]
};

/** Same edition with Orienteering revealed and timed results filled in. */
export const summaryAllRevealed = {
	...summary,
	disciplines: [
		summary.disciplines[0],
		{ ...summary.disciplines[1], reveal_score: true }
	],
	results: [
		...summary.results.slice(0, 3),
		{ id: 103, team: 1, discipline: 11, result_type: 'TIM', ranking: 1, points: null, time: '00:12:30', points_difference: 0, global_points: 5 },
		{ id: 104, team: 2, discipline: 11, result_type: 'TIM', ranking: 3, points: null, time: '00:15:02', points_difference: 0, global_points: 2 },
		{ id: 105, team: 3, discipline: 11, result_type: 'TIM', ranking: 2, points: null, time: '00:13:45', points_difference: 0, global_points: 3 }
	],
	games: [...summary.games.slice(0, 3), { ...summary.games[3], score1: 3, score2: 1 }]
};

/**
 * What a staff user gets on the same edition: hidden game scores and stored results
 * visible, rankings still null, plus a hidden Darts (points) and Crossfit (time) without
 * rounds, both awaiting entry.
 */
export const summaryStaff = {
	...summary,
	disciplines: [
		...summary.disciplines,
		{ id: 12, name: 'Darts', result_type: 'PTS', reveal_score: false, pairing_system: 'NO' },
		{ id: 13, name: 'Crossfit', result_type: 'TIM', reveal_score: false, pairing_system: 'NO' }
	],
	results: [
		...summary.results.slice(0, 3),
		{ id: 103, team: 1, discipline: 11, result_type: 'TIM', ranking: null, points: null, time: '00:12:30', points_difference: null, global_points: null },
		{ id: 104, team: 2, discipline: 11, result_type: 'TIM', ranking: null, points: null, time: null, points_difference: null, global_points: null },
		{ id: 105, team: 3, discipline: 11, result_type: 'TIM', ranking: null, points: null, time: '00:13:45', points_difference: null, global_points: null },
		{ id: 106, team: 1, discipline: 12, result_type: 'PTS', ranking: null, points: 20, time: null, points_difference: null, global_points: null },
		{ id: 107, team: 2, discipline: 12, result_type: 'PTS', ranking: null, points: null, time: null, points_difference: null, global_points: null },
		{ id: 108, team: 3, discipline: 12, result_type: 'PTS', ranking: null, points: 15, time: null, points_difference: null, global_points: null },
		{ id: 109, team: 1, discipline: 13, result_type: 'TIM', ranking: null, points: null, time: '00:12:30', points_difference: null, global_points: null },
		{ id: 110, team: 2, discipline: 13, result_type: 'TIM', ranking: null, points: null, time: null, points_difference: null, global_points: null },
		{ id: 111, team: 3, discipline: 13, result_type: 'TIM', ranking: null, points: null, time: '01:02:03', points_difference: null, global_points: null }
	],
	games: [...summary.games.slice(0, 3), { ...summary.games[3], score1: 3, score2: 1 }]
};

/**
 * An old edition ranked by hand: Bisons first, Aigles second, Cerfs without a rank,
 * no totals, every result hidden.
 */
export const summaryManual = {
	...summary,
	edition: { ...summary.edition, year: 2022 },
	teams: [
		{ ...summary.teams[0], ranking: 2, total_points: null },
		{ ...summary.teams[1], ranking: 1, total_points: null },
		{ ...summary.teams[2], ranking: null, total_points: null }
	],
	disciplines: summary.disciplines.map((d) => ({ ...d, reveal_score: false })),
	results: summary.results.map((r) => ({
		...r,
		ranking: null,
		points: null,
		time: null,
		points_difference: null,
		global_points: null
	})),
	rounds: [],
	games: []
};
