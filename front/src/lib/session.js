import { getContext } from 'svelte';

/** Svelte context key under which the root layout stores whether the visitor is an organiser. */
export const ORGANISER = 'organiser';

/**
 * Svelte context key under which the root layout stores who is logged in:
 * `{ id, first_name, last_name, photo, is_person, photo_locked }` (`photo` being
 * `{ large, small }` or null), or null. Set once at init, so it is for what cannot change within a page's
 * lifetime, such as `me.id` (whose profile this is): logging in and out reload the page.
 * The photo and the lock in it go stale after an in-page `invalidateAll()`, so a component
 * showing them reads the layout's `data.me` reactively instead (Header takes it as a prop,
 * the profile page reads it from its merged `data`).
 */
export const ME = 'me';

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

/** Who is logged in (see ME), or null for a visitor and outside any layout (tests). Init only. */
export const useMe = () => getContext(ME) ?? null;
