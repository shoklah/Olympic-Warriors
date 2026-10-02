import { getContext } from 'svelte';

/** Svelte context key under which the root layout stores whether the visitor is an organiser. */
export const ORGANISER = 'organiser';

/** Cookie holding the bare DRF token after /login; deleted by /logout. */
export const TOKEN_COOKIE = 'token';

/**
 * httpOnly, site-wide, one week; lax so an organiser arriving from an outside link is still
 * logged in (SvelteKit's origin check covers CSRF). `secure` is left to SvelteKit (true off localhost).
 */
export const tokenCookieOptions = () => ({
	httpOnly: true,
	sameSite: 'lax',
	maxAge: 60 * 60 * 24 * 7,
	path: '/'
});

/** Whether the visitor is a staff user; false outside any layout (tests). Init only. */
export const useOrganiser = () => getContext(ORGANISER) ?? false;
