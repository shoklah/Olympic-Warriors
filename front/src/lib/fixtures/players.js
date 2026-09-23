/**
 * Payloads of the public profile endpoints. `leaderboard` is /profiles/: two players
 * tied 1st, one 3rd, then two not ranked yet. `profile` is /profile/34/: a running
 * edition, two ranked ones and one without a team. `profileUnranked` has nothing counted.
 */
export const leaderboard = [
	{ id: 12, first_name: 'Léa', last_name: 'Martin', played: 2, counted: 2, average_rank: 1, average_beaten: 100, position: 1 },
	{ id: 7, first_name: 'Hugo', last_name: 'Maurinier', played: 1, counted: 1, average_rank: 1, average_beaten: 100, position: 1 },
	{ id: 34, first_name: 'Xavier', last_name: 'Baby', played: 4, counted: 2, average_rank: 2.5, average_beaten: 76, position: 3 },
	{ id: 40, first_name: 'Ana', last_name: 'Petit', played: 1, counted: 0, average_rank: null, average_beaten: null, position: null },
	{ id: 41, first_name: 'Jules', last_name: 'Roux', played: 2, counted: 0, average_rank: null, average_beaten: null, position: null }
];

export const profile = {
	id: 34,
	first_name: 'Xavier',
	last_name: 'Baby',
	position: 3,
	counted: 2,
	average_rank: 2.5,
	average_beaten: 76,
	editions: [
		{ year: 2030, team: { id: 40, name: 'Les Aigles' }, rank: null, teams: 4, finished: false },
		{ year: 2026, team: { id: 21, name: 'MxM' }, rank: 2, teams: 6, finished: true },
		{ year: 2024, team: null, rank: null, teams: 8, finished: true },
		{ year: 2023, team: { id: 5, name: 'Bisons' }, rank: 3, teams: 8, finished: true }
	]
};

export const profileUnranked = {
	id: 40,
	first_name: 'Ana',
	last_name: 'Petit',
	position: null,
	counted: 0,
	average_rank: null,
	average_beaten: null,
	editions: [{ year: 2030, team: { id: 41, name: 'Renards' }, rank: null, teams: 4, finished: false }]
};
