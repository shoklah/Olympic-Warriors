const player = (id, first, last, over = {}) => ({
	id, first_name: first, last_name: last, rating: 5, global_level: 5,
	ratings: { CARD: 5, STR: 5 }, sport_frequency: 'hour', sports: [],
	team_with: '', team_avoid: '', team: null, ...over
});

export const builderPayload = {
	edition: { year: 2029 },
	skills: [
		{ identifier: 'CARD', name_fr: 'Cardio', name_en: 'Cardio' },
		{ identifier: 'STR', name_fr: 'Force', name_en: 'Strength' }
	],
	registration_open: false,
	teams_exist: false,
	players: [
		player(1, 'Léa', 'Martin', { rating: 8, ratings: { CARD: 9, STR: 7 }, sport_frequency: 'four_hours', team_with: 'Paul Durand', team_avoid: 'Zoé' }),
		player(2, 'Paul', 'Durand', { rating: 6, ratings: { CARD: 5, STR: 7 }, team_with: 'Léa' }),
		player(3, 'Paul', 'Petit', { rating: 4, ratings: { CARD: 3, STR: 5 }, sports: [{ sport: 'Judo', level: 'league' }] }),
		player(4, 'Inès', 'Moreau', { rating: 7, ratings: { CARD: 6, STR: 8 }, team_avoid: 'Bob' }),
		player(5, 'Bob', 'Roux', { rating: 3, ratings: {}, sport_frequency: '' }),
		player(6, 'Zoé', 'Blanc', { rating: 5, ratings: { CARD: 5, STR: 5 } })
	],
	draft: null
};
