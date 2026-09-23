import { describe, expect, it } from 'vitest';
import { ORGANISER, TOKEN_COOKIE, tokenCookieOptions } from './session.js';

describe('session constants', () => {
	it('names the context key and the cookie', () => {
		expect(ORGANISER).toBe('organiser');
		expect(TOKEN_COOKIE).toBe('token');
	});

	it('scopes the cookie to the site for a week, lax, unreadable by scripts', () => {
		expect(tokenCookieOptions()).toEqual({
			httpOnly: true,
			sameSite: 'lax',
			maxAge: 60 * 60 * 24 * 7,
			path: '/'
		});
	});
});
