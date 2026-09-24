import { iconFor } from './icons.js';
import { disciplineName } from './i18n';
import { BADGES, isKnownBadge, isTiered } from './badge-codes.js';
import fallback from './img/icons/default.svg?url';

// The catalogue lives in the glyph-free badge-codes.js; importing it from here still works.
export { BADGES, isKnownBadge, isTiered };

const TIER_METALS = ['bronze', 'silver', 'gold'];

/** Every SVG in ./img/badges, bundled; the file stem is the badge code. */
const files = import.meta.glob('./img/badges/*.svg', { eager: true, query: '?url', import: 'default' });
const glyphs = Object.fromEntries(
	Object.entries(files).map(([path, url]) => [path.slice('./img/badges/'.length, -'.svg'.length), url])
);

const hasOwn = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);

export const hasGlyph = (code) => hasOwn(glyphs, code);

/**
 * A tiered badge's tier, 1 to 3: a missing, zero or out-of-range tier is clamped, so the
 * metal, the pips and the « Niveau n » line always agree.
 */
export const badgeTier = (badge) => Math.min(Math.max(Number(badge.tier) || 1, 1), 3);

/** 'gold' | 'silver' | 'bronze' | 'plain': the ring colour. */
export function badgeMetal(badge) {
	const metal = hasOwn(BADGES, badge.code) ? BADGES[badge.code] : 'plain';
	return metal === 'tiers' ? TIER_METALS[badgeTier(badge) - 1] : metal;
}

/** The glyph URL: the discipline's own icon for specialist. */
export function badgeGlyph(badge) {
	if (badge.code === 'specialist') return iconFor(badge.discipline ?? '');
	return glyphs[badge.code] ?? fallback;
}

/**
 * The text parts of a badge sheet's entry line, which BadgeSheet (its only caller) joins
 * with ' · '. The discipline comes first whenever the badge has one (specialist, master,
 * unbeaten, perfect-run, steamroller), so two entries of one code tell their disciplines
 * apart. Then a tiered badge gives ['Tier 2', year reached]; comrades gives [year], the
 * sheet writing the partner link before it; master, a title held until lost, gives
 * ['since 2022']; any other badge gives its years, in order. No year gives no
 * part (the sheet then leaves the line, or its separator, out). The repeat count itself is
 * not here: BadgeSheet's status line says it once, from the slot's own count.
 */
export function badgeDetail(badge, t, locale) {
	const years = badge.years.map(String);
	const parts = badge.discipline ? [disciplineName(locale, badge.discipline)] : [];
	if (isTiered(badge.code)) {
		parts.push(t('badge.level', { tier: badgeTier(badge) }));
		if (years.length) parts.push(years[years.length - 1]);
		return parts;
	}
	if (badge.code === 'comrades') return [...parts, ...years.slice(-1)];
	if (badge.code === 'master') {
		if (years.length) parts.push(t('badge.since', { year: years[0] }));
		return parts;
	}
	return [...parts, ...years];
}

/**
 * A slot button's accessible name: "<name>, <earned|locked>" or, above ×1, "<name>, badge
 * earned N times" (a plural key, so a screen reader never hears "×2"). Shared by the
 * collection's slots and the showcase's medallions, which open the same sheet.
 */
export function slotLabel(slot, t) {
	const name = t(`badge.${slot.code}.name`);
	if (!slot.earned) return `${name}, ${t('badge.locked')}`;
	if (slot.count > 1) return `${name}, ${t('badge.earnedTimes', { n: slot.count })}`;
	return `${name}, ${t('badge.earned')}`;
}

/**
 * The catalogue split into nine families, in catalogue order, one entry per BADGES code:
 * badges.test.js checks every code appears exactly once, in catalogue order inside its
 * family. Mirrors the "Families" table of the badge collection design spec.
 */
export const FAMILIES = [
	{ key: 'podiums', codes: ['champion', 'runner-up', 'bronze', 'chocolate', 'wooden-spoon'] },
	{
		key: 'streaks',
		codes: [
			'back-to-back', 'threepeat', 'dynasty', 'phoenix', 'legend', 'podium-regular', 'full-set',
			'eternal-second', 'janus', 'comeback', 'on-the-rise', 'icarus', 'lucky-charm'
		]
	},
	{ key: 'loyalty', codes: ['rookie', 'veteran', 'argonaut', 'ever-present', 'homecoming'] },
	{ key: 'teammates', codes: ['comrades', 'networker'] },
	{
		key: 'hall-of-fame',
		codes: ['goat', 'alone-at-the-top', 'hall-of-fame-podium', 'hall-of-famer', 'reign', 'kingslayer', 'rocket']
	},
	{
		key: 'disciplines',
		codes: [
			'specialist', 'master', 'all-rounder', 'decathlete', 'brains-and-brawn', 'clean-sweep',
			'metronome', 'uncrowned', 'photo-finish'
		]
	},
	{
		key: 'olympus',
		codes: ['athena', 'apollo', 'artemis', 'hermes', 'heracles', 'theseus', 'ares', 'hades', 'dionysus', 'olympus']
	},
	{ key: 'games', codes: ['unbeaten', 'perfect-run', 'shutout', 'steamroller', 'perfect-pitch'] },
	{ key: 'awards', codes: ['mvp', 'fair-play', 'hype', 'costume', 'wounded', 'torchbearer'] }
];

/**
 * The tier thresholds of the five tiered codes, mirroring `badges.py`. Tuning a threshold
 * means changing `badges.py`, both dictionaries' `badge.<code>.rule` and this table
 * together (see the design spec, "Tier thresholds").
 */
export const TIER_THRESHOLDS = {
	veteran: [3, 5, 10],
	'ever-present': [4, 6, 8],
	networker: [5, 10, 20],
	specialist: [2, 3, 4],
	'all-rounder': [3, 5, 8]
};

/**
 * The threshold tier `tier + 1` needs, or null at tier 3 or for an untiered code. A
 * locked tiered slot passes `tier: 0`, so it gets the tier-1 threshold back.
 */
export function nextThreshold(code, tier) {
	return TIER_THRESHOLDS[code]?.[tier] ?? null;
}

/**
 * The share of players holding `code`, from the profile's `badge_stats`
 * (`{ players, holders: {code: n}, tiers: {code: [n1, n2, n3]} }`, see the design spec's
 * "Rarity"): `{ holders, players, percent }`, `percent` rounded to the nearest whole
 * number. With `tier` (1 to 3), `holders` is the at-least-that-tier count from
 * `stats.tiers[code]` instead of the overall `stats.holders[code]`; either is 0 when the
 * code (or that tier) isn't listed, which means no one holds it. Null when `stats` is
 * missing (an older API) or `players` is 0.
 */
export function badgeRarity(stats, code, tier = 0) {
	if (!stats || !stats.players) return null;
	const players = stats.players;
	const holders = tier > 0 ? (stats.tiers?.[code]?.[tier - 1] ?? 0) : (stats.holders?.[code] ?? 0);
	return { holders, players, percent: Math.round((100 * holders) / players) };
}

/** The medal stub a locked slot shows: no entry to draw, so `Badge.svelte` gets zeros. */
const lockedMedal = (code) => ({ code, tier: 0, years: [], discipline: null, partner: null });

/**
 * How many times an entry counts towards its slot's "×N": a tiered entry counts 1 (the
 * tier itself already says how many wins it took), any other entry counts
 * `max(1, years.length)` so a badge with no year still counts once.
 */
const entryCount = (entry) => (isTiered(entry.code) ? 1 : Math.max(1, entry.years.length));

/**
 * The collection view of a profile's `badges`, one slot per catalogue code, grouped into
 * `FAMILIES`. Codes the front doesn't know (`isKnownBadge` false) are ignored, as
 * elsewhere. See the design spec, "Definitions", for the count and medal rules.
 * @returns {{earned: number, total: number, families: Array}}
 */
export function badgeCollection(badges) {
	const byCode = new Map();
	for (const entry of badges) {
		if (!isKnownBadge(entry)) continue;
		if (!byCode.has(entry.code)) byCode.set(entry.code, []);
		byCode.get(entry.code).push(entry);
	}

	const buildSlot = (code) => {
		const entries = byCode.get(code) ?? [];
		const earned = entries.length > 0;
		// Earned: the entry with the highest tier for a tiered code (so the medallion draws
		// the best tier reached), else the first entry recorded.
		const medal = !earned
			? lockedMedal(code)
			: isTiered(code)
				? entries.reduce((best, e) => (badgeTier(e) > badgeTier(best) ? e : best))
				: entries[0];
		const count = entries.reduce((n, e) => n + entryCount(e), 0);
		return { code, entries, count, earned, medal };
	};

	const families = FAMILIES.map(({ key, codes }) => {
		const slots = codes.map(buildSlot);
		return { key, earned: slots.filter((s) => s.earned).length, total: slots.length, slots };
	});

	return {
		earned: families.reduce((n, f) => n + f.earned, 0),
		total: families.reduce((n, f) => n + f.total, 0),
		families
	};
}
