/**
 * Payloads of the public profile endpoints. `leaderboard` is /profiles/: Léa 1st (a 1st
 * and a 2nd place, average rank 1.5), Hugo and Inès tied 2nd (one 1st place each, average
 * rank 1), Xavier 4th (a 2nd, a 3rd and a 4th place, average rank 3), then two not ranked
 * yet (no average rank). `profile` is /profile/34/: a running edition, two ranked ones and
 * one without a team, places in three disciplines (Relay 1st, Crossfit 2nd, Darts 3rd),
 * and five badges in catalogue order: veteran at tier 1, comrades with Léa, a Relay
 * specialist, clean sweep twice and a code the front does not know. The badges exercise
 * the badge collection's slot and sheet shapes (tier, partner link, discipline, a repeat,
 * an unknown code); they are not derived from the editions and places above.
 * `profileUnranked` has nothing counted, no discipline places and no badge.
 */
export const leaderboard = [
	{ id: 12, first_name: 'Léa', last_name: 'Martin', played: 3, counted: 2, places: [{ year: 2024, rank: 1 }, { year: 2026, rank: 2 }], position: 1, average_rank: 1.5 },
	{ id: 7, first_name: 'Hugo', last_name: 'Maurinier', played: 1, counted: 1, places: [{ year: 2025, rank: 1 }], position: 2, average_rank: 1 },
	{ id: 9, first_name: 'Inès', last_name: 'Moreau', played: 1, counted: 1, places: [{ year: 2025, rank: 1 }], position: 2, average_rank: 1 },
	{ id: 34, first_name: 'Xavier', last_name: 'Baby', played: 4, counted: 3, places: [{ year: 2026, rank: 2 }, { year: 2023, rank: 3 }, { year: 2021, rank: 4 }], position: 4, average_rank: 3 },
	{ id: 40, first_name: 'Ana', last_name: 'Petit', played: 1, counted: 0, places: [], position: null, average_rank: null },
	{ id: 41, first_name: 'Jules', last_name: 'Roux', played: 2, counted: 0, places: [], position: null, average_rank: null }
];

export const profile = {
	id: 34,
	first_name: 'Xavier',
	last_name: 'Baby',
	position: 3,
	counted: 2,
	average_rank: 2.5,
	editions: [
		{ year: 2030, team: { id: 40, name: 'Les Aigles' }, rank: null, teams: 4, finished: false },
		{ year: 2026, team: { id: 21, name: 'MxM' }, rank: 2, teams: 6, finished: true },
		{ year: 2024, team: null, rank: null, teams: 8, finished: true },
		{ year: 2023, team: { id: 5, name: 'Bisons' }, rank: 3, teams: 8, finished: true }
	],
	disciplines: [
		{ name: 'Relay', position: 1, places: [{ year: 2026, rank: 1 }, { year: 2023, rank: 2 }] },
		{ name: 'Crossfit', position: 2, places: [{ year: 2026, rank: 1 }, { year: 2023, rank: 4 }] },
		{ name: 'Darts', position: 3, places: [{ year: 2026, rank: 3 }] }
	],
	badges: [
		{ code: 'veteran', tier: 1, years: [2026], discipline: null, partner: null },
		{ code: 'comrades', tier: 0, years: [2026], discipline: null, partner: { id: 12, first_name: 'Léa', last_name: 'Martin' } },
		{ code: 'specialist', tier: 1, years: [2026], discipline: 'Relay', partner: null },
		{ code: 'clean-sweep', tier: 0, years: [2023, 2026], discipline: null, partner: null },
		{ code: 'future-badge', tier: 0, years: [2026], discipline: null, partner: null }
	]
};

export const profileUnranked = {
	id: 40,
	first_name: 'Ana',
	last_name: 'Petit',
	position: null,
	counted: 0,
	average_rank: null,
	editions: [{ year: 2030, team: { id: 41, name: 'Renards' }, rank: null, teams: 4, finished: false }],
	disciplines: [],
	badges: []
};
