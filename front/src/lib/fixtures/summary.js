/**
 * One edition as the summary endpoint returns it: a revealed points discipline (Relay),
 * a hidden timed one (Orienteering), three teams. Bisons lead, Aigles second, Cerfs last.
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
		{ id: 10, name: 'Relay', result_type: 'PTS', reveal_score: true },
		{ id: 11, name: 'Orienteering', result_type: 'TIM', reveal_score: false }
	],
	teams: [
		{
			id: 1,
			name: 'Aigles',
			ranking: 2,
			total_points: 3,
			players: [
				{ id: 1, first_name: 'Ana', last_name: 'Lopez' },
				{ id: 2, first_name: 'Bob', last_name: 'Martin' }
			]
		},
		{
			id: 2,
			name: 'Bisons',
			ranking: 1,
			total_points: 5,
			players: [{ id: 3, first_name: 'Chloé', last_name: 'Nguyen' }]
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
	]
};
