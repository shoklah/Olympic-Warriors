import { describe, expect, it } from 'vitest';
import { initials } from './avatar.js';

describe('initials', () => {
	it('takes the first letter of the first and the last name, uppercased', () => {
		expect(initials('Léa', 'Martin')).toBe('LM');
		expect(initials('léa', 'martin')).toBe('LM');
	});

	it('keeps the accents', () => {
		expect(initials('élodie', 'Évrard')).toBe('ÉÉ');
		// A decomposed accent (e + combining acute) comes out as one composed letter.
		expect(initials('e\u0301lise', 'Ogier')).toBe('\u00c9O');
	});

	it('skips what is not a letter', () => {
		expect(initials(' Léa ', "d'Artagnan")).toBe('LD');
		expect(initials('(Léa)', '')).toBe('L');
	});

	it('gives one letter when a part is missing', () => {
		expect(initials('Léa', '')).toBe('L');
		expect(initials('Léa')).toBe('L');
		expect(initials(null, 'Martin')).toBe('M');
		expect(initials('', '   ')).toBe('?');
	});

	it('gives a question mark when there is nothing at all', () => {
		expect(initials()).toBe('?');
		expect(initials(null, null)).toBe('?');
		expect(initials('', '')).toBe('?');
		expect(initials('42', '-')).toBe('?');
	});
});
