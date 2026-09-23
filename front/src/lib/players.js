import { localeFrom } from '$lib/i18n/locale.js';

/**
 * Formatting and small helpers for player pages. `formatAverage` prints the average rank
 * shown on both the leaderboard rows and the profile page. Pure and locale-aware: anything
 * but `en` is French, like `t` and `ordinal`. A missing figure prints as a dash.
 */
const missing = (value) => value === null || value === undefined;

/** A mean rank with one decimal: 2.5 in English, 2,5 in French. */
export function formatAverage(value, locale) {
	if (missing(value)) return '—';
	return new Intl.NumberFormat(localeFrom(locale), {
		minimumFractionDigits: 1,
		maximumFractionDigits: 1
	}).format(value);
}

/** How a profile's edition row reads: ranked, still running, or over without a rank. */
export function editionStatus(participation) {
	if (!participation.finished) return 'inProgress';
	return participation.rank === null ? 'unranked' : 'ranked';
}

/** "First Last", either half dropped when blank; "—" when both are (a bare auth.User allows it). */
export function fullName(person) {
	return [person.first_name, person.last_name].filter(Boolean).join(' ') || '—';
}

/** How many places a leaderboard row shows before it counts the rest as +N. */
export const MAX_PLACES = 8;

/** The best `max` places (already sorted best first by the API) and how many are left out. */
export function shownPlaces(places, max = MAX_PLACES) {
	return { shown: places.slice(0, max), more: Math.max(0, places.length - max) };
}
