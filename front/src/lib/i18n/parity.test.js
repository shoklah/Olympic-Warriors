import { describe, expect, it } from 'vitest';
import fr from './fr.js';
import en from './en.js';

describe('dictionaries', () => {
	it('have the same keys', () => {
		expect(Object.keys(en).sort()).toEqual(Object.keys(fr).sort());
	});

	it('give every plural message a one and an other form in both languages', () => {
		for (const [key, message] of Object.entries(fr)) {
			expect(typeof en[key], key).toBe(typeof message);
			if (typeof message === 'string') continue;
			expect(message, key).toEqual({ one: expect.any(String), other: expect.any(String) });
			expect(en[key], key).toEqual({ one: expect.any(String), other: expect.any(String) });
		}
	});

	it('use the same placeholders in both languages', () => {
		const forms = (m) => (typeof m === 'string' ? [m] : [m.one, m.other]);
		const names = (m) => forms(m).map((f) => [...f.matchAll(/\{(\w+)\}/g)].map((x) => x[1]).sort());
		for (const key of Object.keys(fr)) {
			expect(names(en[key]), key).toEqual(names(fr[key]));
		}
	});
});
