/**
 * French name of a discipline by its database name (the `self.name` each model sets).
 * A discipline absent from here keeps its database name in French too (Rugby,
 * Basketball, Crossfit, Blindtest). icons.test.js checks every model is covered.
 */
export const FRENCH_NAMES = {
	Relay: 'Relais',
	Orienteering: "Course d'orientation",
	'Hide and Seek': 'Cache-cache',
	Fair: 'Fête foraine',
	Dodgeball: 'Balle au prisonnier',
	'Obstacle Course': "Parcours d'obstacles",
	'Geography Quizz': 'Quiz de géographie',
	'General Culture Quizz': 'Quiz culture générale',
	Petanque: 'Pétanque',
	Darts: 'Fléchettes'
};

/** Disciplines whose database name is already the French one. */
export const SAME_IN_FRENCH = ['Rugby', 'Basketball', 'Crossfit', 'Blindtest'];
