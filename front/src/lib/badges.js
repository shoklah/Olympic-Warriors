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
 * discipline comes first whenever the badge has one (specialist, unbeaten, perfect-run),
 * so two tiles of one code tell their disciplines apart. Then a tiered badge gives
 * ['Tier 2', year reached]; comrades gives [year], the page writing the partner link
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
