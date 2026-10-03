import { describe, expect, it, vi } from 'vitest';
import { linkPath, passwordErrors } from './password-link.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

describe('linkPath', () => {
	it('splices a Django-shaped link under its prefix', () => {
		expect(linkPath('/claim')({ uid: 'MzQ', token: 'claim-token-demo' })).toBe('/claim/MzQ/claim-token-demo/');
		expect(linkPath('/password-reset')({ uid: 'MzQ', token: 'a_b-c' })).toBe('/password-reset/MzQ/a_b-c/');
	});

	it('refuses any other part', () => {
		const path = linkPath('/claim');
		for (const params of [
			{ uid: '..', token: 'me' },
			{ uid: 'MzQ', token: 'a/b' },
			{ uid: '', token: 'abc' },
			{ uid: 'MzQ', token: 'x'.repeat(129) }
		]) {
			expect(path(params)).toBeNull();
		}
	});
});

describe('passwordErrors', () => {
	it('words known codes in order, unknown ones once as the generic refusal', () => {
		expect(passwordErrors(['password_too_short', 'weird', 'other', 'password_missing'])).toEqual([
			'claim.error.password_too_short',
			'claim.error.invalid',
			'claim.error.password_missing'
		]);
	});

	it('words no code at all as the generic refusal', () => {
		expect(passwordErrors(undefined)).toEqual(['claim.error.invalid']);
		expect(passwordErrors([])).toEqual(['claim.error.invalid']);
	});
});
