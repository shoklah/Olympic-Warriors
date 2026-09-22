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
