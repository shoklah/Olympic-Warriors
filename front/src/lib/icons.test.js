import { describe, expect, it } from 'vitest';
import { iconFor, iconSlug } from './icons.js';

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
	'Blindtest',
	'Crossfit',
	'Darts',
	'Dodgeball',
	'Fair',
	'General Culture Quizz',
	'Geography Quizz',
	'Hide and Seek',
	'Obstacle Course',
	'Orienteering',
	'Petanque',
	'Relay',
	'Rugby'
];

describe('every discipline model has an icon', () => {
	it.each(DISCIPLINE_NAMES)('%s', (name) => {
		expect(iconFor(name)).not.toMatch(/default\.svg$/);
	});
});
