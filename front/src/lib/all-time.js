import { disciplinePath } from '$lib/edition';
import { disciplineName } from '$lib/i18n';

/**
 * Helpers for the disciplines page's deck of every discipline ever held (from
 * /disciplines/all-time/), each card leading to the discipline's all-time table, the
 * « Palmarès » tab of one of its editions' pages. Pure; anything but `en` is French.
 */

/** The held disciplines sorted by the name shown in `locale`: the server sorts database names. */
export function byShownName(held, locale) {
	return [...held].sort((a, b) =>
		disciplineName(locale, a.name).localeCompare(disciplineName(locale, b.name), locale)
	);
}

/** "2021–2026" for the years a discipline was held (oldest first), "2026" for a single one. */
export function yearSpan(years) {
	if (years.length === 0) return '';
	const first = years[0];
	const last = years[years.length - 1];
	return first === last ? String(first) : `${first}–${last}`;
}

/**
 * Where a held discipline's card leads: the « Palmarès » tab of its page in `year` when that
 * edition held it, so the visitor stays in the year they browse, else of its newest edition.
 * The table is the same on every edition's page.
 */
export function allTimePath(discipline, year) {
	const editions = discipline.editions;
	const edition = editions.find((e) => e.year === Number(year)) ?? editions[editions.length - 1];
	return disciplinePath(edition.year, edition.discipline, true);
}
