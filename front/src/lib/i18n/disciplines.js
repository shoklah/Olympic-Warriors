/**
 * French name of a discipline by its database name (the `self.name` each model sets).
 * A discipline absent from here keeps its database name in French too (Rugby,
 * Football, Frisbee…). icons.test.js checks every model is covered.
 */
export const FRENCH_NAMES = {
	Relay: 'Relais',
	Orienteering: "Course d'orientation",
	'Hide and Seek': 'Cache-cache',
	Fair: 'Fête foraine',
	Dodgeball: 'Balle au prisonnier',
	'Obstacle Course': "Parcours d'obstacles",
	'Geography Quizz': 'Quiz de géographie',
	'General Culture Quizz': 'Quiz de culture générale',
	Petanque: 'Pétanque',
	Darts: 'Fléchettes',
	Volleyball: 'Volley-ball',
	'Jumping Rope': 'Corde à sauter',
	Dance: 'Danse',
	'Burger Quizz': 'Burger Quiz',
	'Blindfolded Obstacle Course': "Parcours d'obstacles à l'aveugle",
	'Disc Throw': 'Lancer de disque'
};

/** Disciplines whose database name is already the French one. */
export const SAME_IN_FRENCH = [
	'Rugby',
	'Basketball',
	'Crossfit',
	'Blindtest',
	'Frisbee',
	'Geoguessr',
	'Football',
	'Handball'
];
