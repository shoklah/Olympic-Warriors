import { describe, expect, it } from 'vitest';
import { DEFAULT_LOCALE, LOCALES, localeFrom } from './locale.js';

describe('localeFrom', () => {
	it('keeps a known locale', () => {
		expect(localeFrom('en')).toBe('en');
		expect(localeFrom('fr')).toBe('fr');
	});

	it('falls back to French for anything else', () => {
		expect(localeFrom('de')).toBe('fr');
		expect(localeFrom(undefined)).toBe('fr');
		expect(localeFrom(null)).toBe('fr');
		expect(localeFrom('')).toBe('fr');
	});

	it('exposes the constants', () => {
		expect(LOCALES).toEqual(['fr', 'en']);
		expect(DEFAULT_LOCALE).toBe('fr');
	});
});
