import { describe, expect, it } from 'vitest';
import fr from './fr.js';
import en from './en.js';

describe('dictionaries', () => {
	it('have the same keys', () => {
		expect(Object.keys(en).sort()).toEqual(Object.keys(fr).sort());
	});

	it('give every plural message a one and an other form in both languages', () => {
		for (const [key, message] of Object.entries(fr)) {
			if (typeof message === 'string') continue;
			expect(message, key).toEqual({ one: expect.any(String), other: expect.any(String) });
			expect(en[key], key).toEqual({ one: expect.any(String), other: expect.any(String) });
		}
	});

	it('use the same placeholders in both languages', () => {
		const names = (message) =>
			[...(typeof message === 'string' ? message : message.other).matchAll(/\{(\w+)\}/g)]
				.map((m) => m[1])
				.sort();
		for (const key of Object.keys(fr)) {
			expect(names(en[key]), key).toEqual(names(fr[key]));
		}
	});
});
