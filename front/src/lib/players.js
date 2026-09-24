import { isKnownBadge } from '$lib/badge-codes';
import { ordinal } from '$lib/edition';
import { disciplineName, t } from '$lib/i18n';
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

/**
 * The player's best disciplines (position 1, ties included), the first `max` of them and
 * how many more there are. Pass disciplines already through `byDisplayedName` so a tie
 * breaks on the name shown in the current locale, not the server's English one.
 */
export function bestDisciplines(disciplines, max = 3) {
	const best = disciplines.filter((d) => d.position === 1);
	return { shown: best.slice(0, max), more: Math.max(0, best.length - max), count: best.length };
}

/**
 * `disciplines` (already ordered by `position`, strongest first), with each group of tied
 * disciplines (equal `position`) re-sorted by the name as displayed in `locale` rather than
 * the server's database-name order. Positions stay in the server's order; only ties move.
 */
export function byDisplayedName(disciplines, locale) {
	return [...disciplines].sort(
		(a, b) =>
			a.position - b.position ||
			disciplineName(locale, a.name).localeCompare(disciplineName(locale, b.name), locale)
	);
}

/** "1st place in 2026, 2nd place in 2023" for screen readers. */
export function spokenPlaces(places, locale) {
	return places.map((p) => t(locale, 'players.placeIn', { place: ordinal(p.rank, locale), year: p.year })).join(', ');
}

/**
 * The showcase's part of a leaderboard row's spoken sentence, the row being one link that
 * cannot hold buttons: "showcase: Champion, Veteran" from `[{ code, tier, discipline }]` in
 * display order, badge names only. A code the front does not know (a newer server) is left
 * out, and an empty showcase (or none, from an older server) gives '' so nothing is added.
 */
export function showcaseLabel(showcase, locale) {
	const names = (showcase ?? []).filter(isKnownBadge).map((badge) => t(locale, `badge.${badge.code}.name`));
	return names.length ? t(locale, 'showcase.spoken', { badges: names.join(', ') }) : '';
}
