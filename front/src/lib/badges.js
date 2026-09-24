import { iconFor } from './icons.js';
import { disciplineName } from './i18n';
import fallback from './img/icons/default.svg?url';

/**
 * The badge catalogue, in catalogue order (Badge.Codes on the server; badges.test.js
 * mirrors it): each code's metal, or 'tiers' when the tier picks it (1 bronze, 2 silver,
 * 3 gold). See the player badges design spec under docs/superpowers/specs/.
 */
export const BADGES = {
	champion: 'gold',
	'runner-up': 'silver',
	bronze: 'bronze',
	chocolate: 'plain',
	'wooden-spoon': 'plain',
	'back-to-back': 'gold',
	threepeat: 'gold',
	dynasty: 'gold',
	phoenix: 'gold',
	legend: 'gold',
	'podium-regular': 'silver',
	'full-set': 'gold',
	'eternal-second': 'silver',
	janus: 'plain',
	comeback: 'silver',
	'on-the-rise': 'bronze',
	icarus: 'plain',
	'lucky-charm': 'silver',
	rookie: 'plain',
	veteran: 'tiers',
	argonaut: 'gold',
	'ever-present': 'tiers',
	homecoming: 'plain',
	globetrotter: 'bronze',
	comrades: 'silver',
	networker: 'tiers',
	goat: 'gold',
	'alone-at-the-top': 'gold',
	'hall-of-fame-podium': 'silver',
	'hall-of-famer': 'bronze',
	reign: 'gold',
	kingslayer: 'gold',
	rocket: 'bronze',
	specialist: 'tiers',
	'all-rounder': 'tiers',
	decathlete: 'gold',
	'brains-and-brawn': 'silver',
	'clean-sweep': 'gold',
	metronome: 'gold',
	uncrowned: 'plain',
	'photo-finish': 'silver',
	athena: 'bronze',
	apollo: 'bronze',
	artemis: 'bronze',
	hermes: 'bronze',
	heracles: 'bronze',
	theseus: 'bronze',
	ares: 'bronze',
	hades: 'bronze',
	dionysus: 'bronze',
	olympus: 'gold',
	unbeaten: 'silver',
	'perfect-run': 'gold',
	shutout: 'bronze',
	steamroller: 'silver',
	'golden-whistle': 'tiers',
	'perfect-pitch': 'gold',
	mvp: 'gold',
	'fair-play': 'silver',
	hype: 'plain',
	costume: 'plain',
	wounded: 'plain',
	torchbearer: 'gold'
};

const TIER_METALS = ['bronze', 'silver', 'gold'];

/** Every SVG in ./img/badges, bundled; the file stem is the badge code. */
const files = import.meta.glob('./img/badges/*.svg', { eager: true, query: '?url', import: 'default' });
const glyphs = Object.fromEntries(
	Object.entries(files).map(([path, url]) => [path.slice('./img/badges/'.length, -'.svg'.length), url])
);

const hasOwn = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);

/** Whether the front knows this badge's code (a newer server may send one it does not). */
export const isKnownBadge = (badge) => hasOwn(BADGES, badge.code);

export const isTiered = (code) => BADGES[code] === 'tiers';

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
 * The text parts of a profile tile's detail line, which the page joins with ' · '. The
 * discipline comes first whenever the badge has one (specialist, unbeaten, perfect-run,
 * steamroller), so two tiles of one code tell their disciplines apart. Then a tiered badge
 * gives ['Tier 2', year reached]; comrades gives [year], the page writing the partner link
 * before it; any other badge gives ['×2', ...years] when earned more than once, else
 * [year]. No year gives no part (the page then leaves the line, or its separator, out).
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
	return years.length > 1 ? [...parts, t('badge.times', { n: years.length }), ...years] : [...parts, ...years];
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
	{ key: 'loyalty', codes: ['rookie', 'veteran', 'argonaut', 'ever-present', 'homecoming', 'globetrotter'] },
	{ key: 'teammates', codes: ['comrades', 'networker'] },
	{
		key: 'hall-of-fame',
		codes: ['goat', 'alone-at-the-top', 'hall-of-fame-podium', 'hall-of-famer', 'reign', 'kingslayer', 'rocket']
	},
	{
		key: 'disciplines',
		codes: [
			'specialist', 'all-rounder', 'decathlete', 'brains-and-brawn', 'clean-sweep', 'metronome',
			'uncrowned', 'photo-finish'
		]
	},
	{
		key: 'olympus',
		codes: ['athena', 'apollo', 'artemis', 'hermes', 'heracles', 'theseus', 'ares', 'hades', 'dionysus', 'olympus']
	},
	{ key: 'games', codes: ['unbeaten', 'perfect-run', 'shutout', 'steamroller', 'golden-whistle', 'perfect-pitch'] },
	{ key: 'awards', codes: ['mvp', 'fair-play', 'hype', 'costume', 'wounded', 'torchbearer'] }
];

/**
 * The tier thresholds of the six tiered codes, mirroring `badges.py`. Tuning a threshold
 * means changing `badges.py`, both dictionaries' `badge.<code>.rule` and this table
 * together (see the design spec, "Tier thresholds").
 */
export const TIER_THRESHOLDS = {
	veteran: [3, 5, 10],
	'ever-present': [4, 6, 8],
	networker: [20, 40, 60],
	specialist: [2, 3, 4],
	'all-rounder': [3, 5, 8],
	'golden-whistle': [5, 10, 20]
};

/**
 * The threshold tier `tier + 1` needs, or null at tier 3 or for an untiered code. A
 * locked tiered slot passes `tier: 0`, so it gets the tier-1 threshold back.
 */
export function nextThreshold(code, tier) {
	return TIER_THRESHOLDS[code]?.[tier] ?? null;
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
