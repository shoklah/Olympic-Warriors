/**
 * Formatting for the players leaderboard and profiles. Pure and locale-aware: anything
 * but `en` is French, like `t` and `ordinal`. A missing figure prints as a dash.
 */
const tag = (locale) => (locale === 'en' ? 'en' : 'fr');
const missing = (value) => value === null || value === undefined;

/** A mean rank with one decimal: 2.5 in English, 2,5 in French. */
export function formatAverage(value, locale) {
	if (missing(value)) return '—';
	return new Intl.NumberFormat(tag(locale), {
		minimumFractionDigits: 1,
		maximumFractionDigits: 1
	}).format(value);
}

/** A whole percentage (0 to 100): 71% in English, 71 % in French. */
export function formatShare(value, locale) {
	if (missing(value)) return '—';
	return new Intl.NumberFormat(tag(locale), { style: 'percent', maximumFractionDigits: 0 }).format(
		value / 100
	);
}

/** How a profile's edition row reads: ranked, still running, or over without a rank. */
export function editionStatus(participation) {
	if (!participation.finished) return 'inProgress';
	return participation.rank === null ? 'unranked' : 'ranked';
}
