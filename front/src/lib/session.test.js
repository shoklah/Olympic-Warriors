import { describe, expect, it } from 'vitest';
import { ME, ORGANISER, TOKEN_COOKIE, tokenCookieOptions } from './session.js';

describe('session constants', () => {
	it('names the context keys and the cookie', () => {
		expect(ORGANISER).toBe('organiser');
		expect(ME).toBe('me');
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
