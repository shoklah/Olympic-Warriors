import { describe, expect, it } from 'vitest';
import { editionStatus, formatAverage, formatShare } from './players.js';

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
		expect(formatShare(71, 'fr')).toBe('71 %');
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
