import { describe, expect, it } from 'vitest';
import { iconFor, iconSlug } from './icons.js';
import { FRENCH_NAMES, SAME_IN_FRENCH } from './i18n/disciplines.js';

describe('iconSlug', () => {
	it('lowercases and strips spaces and apostrophes', () => {
		expect(iconSlug('Hide and Seek')).toBe('hideandseek');
		expect(iconSlug("Course d'orientation")).toBe('coursedorientation');
		expect(iconSlug('Course d’orientation')).toBe('coursedorientation');
		expect(iconSlug('Rugby')).toBe('rugby');
	});
});

describe('iconFor', () => {
	it('returns the matching svg url', () => {
		expect(iconFor('Rugby')).toMatch(/rugby\.svg$/);
		expect(iconFor('Hide and Seek')).toMatch(/hideandseek\.svg$/);
		expect(iconFor('Darts')).toMatch(/darts\.svg$/);
	});

	it('falls back to default.svg for an unknown discipline', () => {
		expect(iconFor('Underwater Chess')).toMatch(/default\.svg$/);
	});
});

/** Every `self.name = '...'` in server/olympic_warriors/models/*.py. Keep in sync by hand. */
const DISCIPLINE_NAMES = [
	'Basketball',
	'Blindfolded Obstacle Course',
	'Blindtest',
	'Burger Quizz',
	'Crossfit',
	'Dance',
	'Darts',
	'Disc Throw',
	'Dodgeball',
	'Fair',
	'Football',
	'Frisbee',
	'General Culture Quizz',
	'Geoguessr',
	'Geography Quizz',
	'Handball',
	'Hide and Seek',
	'Jumping Rope',
	'Obstacle Course',
	'Orienteering',
	'Petanque',
	'Relay',
	'Rugby',
	'Volleyball'
];

describe('every discipline model has an icon', () => {
	it.each(DISCIPLINE_NAMES)('%s', (name) => {
		expect(iconFor(name)).not.toMatch(/default\.svg$/);
	});
});

describe('every discipline model has a French name', () => {
	it.each(DISCIPLINE_NAMES)('%s', (name) => {
		expect(name in FRENCH_NAMES || SAME_IN_FRENCH.includes(name)).toBe(true);
	});

	it('lists no discipline twice', () => {
		for (const name of Object.keys(FRENCH_NAMES)) expect(SAME_IN_FRENCH).not.toContain(name);
	});
});
