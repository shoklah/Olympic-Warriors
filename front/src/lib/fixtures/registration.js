/** `GET /registration/` for the 2027 edition, open, nothing saved yet. */
export const registrationPayload = {
	edition: {
		year: 2027,
		opens: '2027-01-01',
		closes: '2027-09-17',
		start_date: '2027-09-18',
		dates_confirmed: true
	},
	state: { is_open: true, reason: '' },
	intro: { fr: 'Bienvenue aux inscriptions', en: 'Welcome to registration' },
	skills_month: { fr: 'août', en: 'August' },
	skills: [
		{ identifier: 'CARD', name_fr: 'Cardio', name_en: 'Cardio' },
		{ identifier: 'STR', name_fr: 'Force', name_en: 'Strength' }
	],
	disciplines: ['Relay', 'Darts'],
	choices: {
		frequency: [
			{ value: 'rare', label: "Moins d'une fois par mois" },
			{ value: 'monthly', label: 'Moins d’une fois par semaine mais plusieurs fois par mois' },
			{ value: 'hour', label: 'Environ une heure par semaine' },
			{ value: 'two_hours', label: 'Au moins deux heures par semaine' },
			{ value: 'four_hours', label: 'Au moins quatre heures par semaine' }
		],
		level: [
			{ value: 'fun', label: 'Pour le plaisir, entre amis' },
			{ value: 'informal', label: 'Régulièrement, hors club' },
			{ value: 'club', label: 'En club, sans compétition' },
			{ value: 'league', label: 'En club, avec compétitions' },
			{ value: 'regional', label: 'Niveau régional ou supérieur' }
		],
		practice: [
			{ value: 'no_longer', label: 'Ne pratique plus' },
			{ value: 'occasionally', label: 'Pratique occasionnelle' },
			{ value: 'regularly', label: 'Pratique régulière' }
		]
	},
	email: { value: 'lea@example.com', editable: false },
	registration: null,
	suggested: null
};

/** What a registered player's `registration` holds. */
export const savedAnswers = {
	registered: true,
	removed_by_organiser: false,
	ratings: { CARD: 6, STR: 7 },
	global_level: 8,
	sport_frequency: 'two_hours',
	sports: [
		{ sport: 'Judo', level: 'informal', practice: 'no_longer', duration_months: 30, notes: 'Ceinture orange' }
	],
	team_with: 'Avec Bob',
	team_avoid: 'Pas Carl',
	dietary_restrictions: 'Végane',
	attendance_confirmed: true
};
