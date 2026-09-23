import { describe, expect, it } from 'vitest';
import { MAX_PLACES, editionStatus, formatAverage, formatShare, fullName, shownPlaces } from './players.js';

describe('formatAverage', () => {
	it('prints one decimal with the locale separator', () => {
		expect(formatAverage(2.5, 'en')).toBe('2.5');
		expect(formatAverage(2.5, 'fr')).toBe('2,5');
		expect(formatAverage(1, 'en')).toBe('1.0');
	});

	it('treats anything but en as French', () => {
		expect(formatAverage(1.5, 'de')).toBe('1,5');
	});

	it('dashes a missing average', () => {
		expect(formatAverage(null, 'en')).toBe('—');
	});
});

describe('formatShare', () => {
	it('prints a whole percentage, with a no-break space in French', () => {
		expect(formatShare(71, 'en')).toBe('71%');
		// Node 22's ICU puts U+00A0 (not the narrow U+202F) before % in French.
		expect(formatShare(71, 'fr')).toBe('71\u00a0%');
		expect(formatShare(0, 'en')).toBe('0%');
		expect(formatShare(100, 'en')).toBe('100%');
	});

	it('dashes a missing share', () => {
		expect(formatShare(null, 'fr')).toBe('—');
	});
});

describe('editionStatus', () => {
	it('is ranked when finished with a rank', () => {
		expect(editionStatus({ finished: true, rank: 2 })).toBe('ranked');
	});

	it('is in progress until the edition is over, whatever the rank', () => {
		expect(editionStatus({ finished: false, rank: null })).toBe('inProgress');
	});

	it('is unranked when over without a rank', () => {
		expect(editionStatus({ finished: true, rank: null })).toBe('unranked');
	});
});

describe('fullName', () => {
	it('joins first and last name', () => {
		expect(fullName({ first_name: 'Xavier', last_name: 'Baby' })).toBe('Xavier Baby');
	});

	it('keeps just the first name when the last name is blank', () => {
		expect(fullName({ first_name: 'Xavier', last_name: '' })).toBe('Xavier');
	});

	it('keeps just the last name when the first name is blank', () => {
		expect(fullName({ first_name: '', last_name: 'Baby' })).toBe('Baby');
	});

	it('dashes when both are blank', () => {
		expect(fullName({ first_name: '', last_name: '' })).toBe('—');
	});
});

describe('shownPlaces', () => {
	const places = (n) => Array.from({ length: n }, (_, i) => ({ year: 2030 - i, rank: i + 1 }));

	it('shows every place up to the cap', () => {
		expect(shownPlaces(places(3))).toEqual({ shown: places(3), more: 0 });
		expect(shownPlaces(places(MAX_PLACES)).more).toBe(0);
	});

	it('keeps the best places and counts the rest', () => {
		const { shown, more } = shownPlaces(places(MAX_PLACES + 2));
		expect(shown).toEqual(places(MAX_PLACES));
		expect(more).toBe(2);
	});
});
