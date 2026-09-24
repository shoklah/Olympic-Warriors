/**
 * Payloads of the public profile endpoints. `leaderboard` is /profiles/: Léa 1st (a 1st
 * and a 2nd place, average rank 1.5), Hugo and Inès tied 2nd (one 1st place each, average
 * rank 1), Xavier 4th (a 2nd, a 3rd and a 4th place, average rank 3), then two not ranked
 * yet (no average rank). Each row carries `photo` (the small URL, or null: Léa, Xavier and
 * Jules have one) and `showcase` (0 to 3 `{code, tier, discipline}` in display order:
 * Léa three, Inès a Relay specialist, Xavier the automatic showcase of his profile below,
 * Jules a rookie, Hugo and Ana none). `profile` is /profile/34/: a running edition, two
 * ranked ones and one without a team, places in three disciplines (Relay 1st, Crossfit 2nd,
 * Darts 3rd), and five badges in catalogue order: veteran at tier 1, comrades with Léa (her
 * small photo on the partner), a Relay specialist, clean sweep twice and a code the front
 * does not know. The badges exercise the badge collection's slot and sheet shapes (tier,
 * partner link, discipline, a repeat, an unknown code); they are not derived from the
 * editions and places above. `badge_stats` (47 players) gives holders for the earned codes
 * above, plus tiers for the two tiered ones (veteran, specialist), to exercise the sheet's
 * rarity lines. The profile's `photo` has both sizes, and its `showcase` is automatic:
 * Xavier's three rarest earned codes by those holders (clean sweep 3, specialist 5,
 * comrades 8).
 * `profileUnranked` has nothing counted, no discipline places, no badge and no photo.
 * `allTime` is /discipline/10/all-time/ (Relay, 2024 and 2025): Léa and Hugo tied 1st on a
 * 1st and a 2nd place each, Inès 3rd on a single 1st place, Xavier 4th on a 4th place.
 * `allTimeEmpty` is a discipline without any revealed result yet.
 */
export const leaderboard = [
	{
		id: 12, first_name: 'Léa', last_name: 'Martin', played: 3, counted: 2, places: [{ year: 2024, rank: 1 }, { year: 2026, rank: 2 }], position: 1, average_rank: 1.5,
		photo: '/media/avatars/12-4f1c2a9b7e3d-sm.webp',
		showcase: [
			{ code: 'champion', tier: 0, discipline: null },
			{ code: 'veteran', tier: 2, discipline: null },
			{ code: 'networker', tier: 1, discipline: null }
		]
	},
	{ id: 7, first_name: 'Hugo', last_name: 'Maurinier', played: 1, counted: 1, places: [{ year: 2025, rank: 1 }], position: 2, average_rank: 1, photo: null, showcase: [] },
	{
		id: 9, first_name: 'Inès', last_name: 'Moreau', played: 1, counted: 1, places: [{ year: 2025, rank: 1 }], position: 2, average_rank: 1,
		photo: null,
		showcase: [{ code: 'specialist', tier: 1, discipline: 'Relay' }]
	},
	{
		id: 34, first_name: 'Xavier', last_name: 'Baby', played: 4, counted: 3, places: [{ year: 2026, rank: 2 }, { year: 2023, rank: 3 }, { year: 2021, rank: 4 }], position: 4, average_rank: 3,
		photo: '/media/avatars/34-9b8a7c6d5e4f-sm.webp',
		showcase: [
			{ code: 'clean-sweep', tier: 0, discipline: null },
			{ code: 'specialist', tier: 1, discipline: 'Relay' },
			{ code: 'comrades', tier: 0, discipline: null }
		]
	},
	{ id: 40, first_name: 'Ana', last_name: 'Petit', played: 1, counted: 0, places: [], position: null, average_rank: null, photo: null, showcase: [] },
	{
		id: 41, first_name: 'Jules', last_name: 'Roux', played: 2, counted: 0, places: [], position: null, average_rank: null,
		photo: '/media/avatars/41-0a1b2c3d4e5f-sm.webp',
		showcase: [{ code: 'rookie', tier: 0, discipline: null }]
	}
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
		{ name: 'Relay', position: 1, places: [{ year: 2026, rank: 1 }, { year: 2023, rank: 2 }], latest: { year: 2026, discipline: 10 } },
		{ name: 'Crossfit', position: 2, places: [{ year: 2026, rank: 1 }, { year: 2023, rank: 4 }], latest: { year: 2026, discipline: 13 } },
		{ name: 'Darts', position: 3, places: [{ year: 2026, rank: 3 }], latest: { year: 2026, discipline: 12 } }
	],
	badges: [
		{ code: 'veteran', tier: 1, years: [2026], discipline: null, partner: null },
		{
			code: 'comrades',
			tier: 0,
			years: [2026],
			discipline: null,
			partner: { id: 12, first_name: 'Léa', last_name: 'Martin', photo: '/media/avatars/12-4f1c2a9b7e3d-sm.webp' }
		},
		{ code: 'specialist', tier: 1, years: [2026], discipline: 'Relay', partner: null },
		{ code: 'clean-sweep', tier: 0, years: [2023, 2026], discipline: null, partner: null },
		{ code: 'future-badge', tier: 0, years: [2026], discipline: null, partner: null }
	],
	badge_stats: {
		players: 47,
		holders: { veteran: 20, comrades: 8, specialist: 5, 'clean-sweep': 3 },
		tiers: { veteran: [20, 6, 1], specialist: [5, 2, 0] }
	},
	photo: { large: '/media/avatars/34-9b8a7c6d5e4f.webp', small: '/media/avatars/34-9b8a7c6d5e4f-sm.webp' },
	showcase: {
		auto: true,
		badges: [
			{ code: 'clean-sweep', tier: 0, discipline: null },
			{ code: 'specialist', tier: 1, discipline: 'Relay' },
			{ code: 'comrades', tier: 0, discipline: null }
		]
	}
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
	badges: [],
	photo: null,
	showcase: { auto: true, badges: [] }
};

export const allTime = {
	name: 'Relay',
	years: [2024, 2025],
	players: [
		{ id: 12, first_name: 'Léa', last_name: 'Martin', position: 1, places: [{ year: 2025, rank: 1 }, { year: 2024, rank: 2 }] },
		{ id: 7, first_name: 'Hugo', last_name: 'Maurinier', position: 1, places: [{ year: 2024, rank: 1 }, { year: 2025, rank: 2 }] },
		{ id: 9, first_name: 'Inès', last_name: 'Moreau', position: 3, places: [{ year: 2025, rank: 1 }] },
		{ id: 34, first_name: 'Xavier', last_name: 'Baby', position: 4, places: [{ year: 2024, rank: 4 }] }
	]
};

export const allTimeEmpty = { name: 'Darts', years: [], players: [] };
